# -*- coding: utf-8 -*-

import uuid
import logging
from odoo import models, fields, api
from ..utils import rabbitmq_sender

_logger = logging.getLogger(__name__)


class PosOrder(models.Model):
    _inherit = 'pos.order'

    order_id_custom = fields.Char(
        string='Order ID (UUID)',
        help='UUID voor RabbitMQ integratie',
        readonly=True,
        copy=False,
        index=True
    )

    payment_type = fields.Selection([
        ('Direct', 'Direct'),
        ('Invoice', 'Invoice')
    ], string='Payment Type', compute='_compute_payment_type', store=True, readonly=True)

    @api.depends('payment_ids', 'payment_ids.payment_method_id')
    def _compute_payment_type(self):
        """
        Bepaal payment type op basis van payment methods:
        - Cash of Bancontact = Direct
        - Invoice = Invoice
        """
        for order in self:
            payment_type = 'Direct'  # Default

            if order.payment_ids:
                for payment in order.payment_ids:
                    if payment.payment_method_id:
                        payment_name = payment.payment_method_id.name.lower()
                        if 'invoice' in payment_name:
                            payment_type = 'Invoice'
                            break

            order.payment_type = payment_type

    @api.model_create_multi
    def create(self, vals_list):
        """Override create om UUID te genereren voor order_id_custom."""
        for vals in vals_list:
            if not vals.get('order_id_custom'):
                vals['order_id_custom'] = str(uuid.uuid4())

        return super(PosOrder, self).create(vals_list)

    def _build_payment_confirmed_data(self):
        """
        Bouw het data-dict voor Contract 16 (PaymentConfirmed → CRM).

        Verplichte velden: email, amount, currency, paidAt
        Optionele velden: userId
        """
        self.ensure_one()

        partner = self.partner_id

        return {
            'userId': partner.user_id_custom if partner else None,
            'email': partner.email if partner else '',
            'amount': self.amount_total,
            'currency': 'EUR',
            'paidAt': self.date_order.strftime('%Y-%m-%dT%H:%M:%SZ') if self.date_order else None,
        }

    def _build_invoice_requested_data(self):
        """
        Bouw het data-dict voor Contract K-01 (InvoiceRequested → Facturatie).
        Nu voor private individuals (US-11) inclusief volledige gebruikersdata.

        Verplichte velden: orderId, user (nested), amount, currency, orderedAt, items
        """
        self.ensure_one()

        partner = self.partner_id
        names = (partner.name or "").split(" ", 1)
        first_name = names[0]
        last_name = names[1] if len(names) > 1 else ""

        raw_role = partner.role or 'VISITOR'
        # Map 'Customer' naar een geldige waarde conform XSD schema
        if raw_role == 'Customer':
            role = 'COMPANY_CONTACT' if partner.company_id_custom else 'VISITOR'
        else:
            role = raw_role

        user_data = {
            'userId': partner.user_id_custom or '',
            'firstName': first_name,
            'lastName': last_name,
            'email': partner.email or '',
            'badgeCode': partner.badge_code or '',
            'role': role,
        }

        items = []
        for line in self.lines:
            items.append({
                'productName': line.product_id.name,
                'quantity': int(line.qty),
                'unitPrice': line.price_unit,
            })

        return {
            'orderId': self.order_id_custom,
            'user': user_data,
            'amount': self.amount_total,
            'currency': 'EUR',
            'orderedAt': self.date_order.strftime('%Y-%m-%dT%H:%M:%SZ') if self.date_order else None,
            'items': items,
        }

    @api.model
    def create_from_ui(self, orders, draft=False):
        """
        Override van de POS frontend call.
        Na het verwerken van de order → stuur berichten naar RabbitMQ en verwerk saldo.
        """
        order_ids = super().create_from_ui(orders, draft=draft)

        for order_info in order_ids:
            order = self.browse(order_info['id'])

            if order.state in ('paid', 'done', 'invoiced'):
                self._trigger_rabbitmq_messages(order)
                self._process_balance_payment(order)

        return order_ids

    def _process_balance_payment(self, order):
        """Verwerk saldo-betalingen: deducteer van partner balance en sla transactie op."""
        if not order.partner_id:
            return
        partner = order.partner_id

        # Process payments sequentially; if a Top Up payment exceeds the available
        # balance, deduct only the available amount and create a new payment for
        # the remainder using a non-Top Up payment method from the POS config.
        for payment in order.payment_ids.sorted(key=lambda r: r.id):
            if not payment.payment_method_id:
                continue

            payment_name = (payment.payment_method_id.name or '').lower()
            if 'saldo' not in payment_name and 'top up' not in payment_name:
                continue

            available = float(partner.balance or 0.0)
            requested = float(payment.amount or 0.0)

            # Determine how much to deduct from balance
            if available <= 0.0:
                deduct = 0.0
                remaining = requested
            elif requested <= available:
                deduct = requested
                remaining = 0.0
            else:
                deduct = available
                remaining = requested - deduct

            # Apply deduction (if any)
            if deduct > 0.0:
                new_balance = round(available - deduct, 2)
                partner.write({'balance': new_balance})
                self.env['balance.transaction'].create({
                    'partner_id': partner.id,
                    'amount': -deduct,
                    'transaction_type': 'payment',
                    'payment_method': 'balance',
                    'note': f'Top Up betaling — order {order.name}',
                    'pos_order_id': order.id,
                    'balance_after': new_balance,
                })
                try:
                    payment.write({'amount': deduct})
                except Exception:
                    _logger.exception('Failed to adjust Top Up payment amount for order %s', order.name)

            # If there's a remainder, create a new payment using another payment method
            if remaining > 0.0:
                _logger.info('Top Up balance insufficient for order %s: deduct=%.2f remaining=%.2f', order.name, deduct, remaining)

                # Try to find an alternative payment method from the POS config
                alt_method = None
                try:
                    config = getattr(order.session_id, 'config_id', None) or getattr(order.session_id, 'config', None)
                    if config and getattr(config, 'payment_method_ids', False):
                        for m in config.payment_method_ids:
                            mname = (m.name or '').lower()
                            if 'saldo' in mname or 'top up' in mname:
                                continue
                            alt_method = m
                            break

                    if not alt_method:
                        # Fallback: first non-Top Up method in system
                        alt_method = self.env['pos.payment.method'].search([('name', 'not ilike', 'top up')], limit=1)
                except Exception:
                    _logger.exception('Error selecting alternative payment method for order %s', order.name)

                if not alt_method or not alt_method.id:
                    _logger.warning('No alternative payment method found for order %s; remaining amount %.2f will stay as unpaid', order.name, remaining)
                else:
                    try:
                        self.env['pos.payment'].create({
                            'order_id': order.id,
                            'amount': remaining,
                            'payment_method_id': alt_method.id,
                            'journal_id': getattr(alt_method, 'journal_id', False) and alt_method.journal_id.id or False,
                        })
                        _logger.info('Created fallback payment (%.2f) using %s for order %s', remaining, alt_method.name, order.name)
                    except Exception:
                        _logger.exception('Failed to create fallback payment for order %s', order.name)

    def _trigger_rabbitmq_messages(self, order):
        """
        Stuur de correcte berichten naar RabbitMQ op basis van paymentType:

        - PaymentConfirmed → kassa.payment.confirmed (Contract 16, naar CRM)
          ALTIJD voor bezoekers, BEHALVE bij 'Invoice' (dat gaat via K-01).
        - InvoiceRequested → kassa.invoice.requested (Contract K-01, naar Facturatie)
          Alleen bij 'Invoice' voor bezoekers (US-11).
        """
        # Contract 16 — alleen voor bezoekers en NIET bij Invoice
        payment_data = order._build_payment_confirmed_data()
        if payment_data.get('email') and not order.partner_id.company_id_custom and order.payment_type != 'Invoice':
            rabbitmq_sender.send_payment_confirmed(payment_data)

        # Contract K-01 — US-11: factuurverzoek voor privépersonen (geen bedrijfskoppeling)
        if order.payment_type == 'Invoice' and order.partner_id and not order.partner_id.company_id_custom:
            invoice_data = order._build_invoice_requested_data()
            rabbitmq_sender.send_invoice_requested(invoice_data)

    @api.model
    def close_daily_batch(self, session=None, session_id=None) -> dict:
        """
        Afsluitknop: Collect today's transactions and send to facturatie.
        
        Args:
            session: Optional pos.session record
            session_id: Optional ID of the session (passed from JS UI)
        """
        import logging
        _logger = logging.getLogger(__name__)
        
        try:
            # Resolve session
            if not session and session_id:
                session = self.env['pos.session'].browse(session_id)
            
            if not session:
                # Fallback: try to find the current active session for this user
                session = self.env['pos.session'].search([
                    ('state', 'in', ['opened', 'closing_control']),
                    ('user_id', '=', self.env.uid)
                ], limit=1)
            
            if not session or not session.exists():
                return {
                    'success': False,
                    'message': 'Geen actieve POS sessie gevonden voor deze gebruiker. Controleer of de kassa open staat.',
                    'batch_id': None,
                    'orders_count': 0,
                    'total_amount': 0.0
                }
            
            # Use the batch service to close
            from ..services import PosOrderBatchService
            service = PosOrderBatchService(self.env)
            
            # Close the session
            success, error_msg, batch_data = service.close_session(session)
            
            if not success:
                return {
                    'success': False,
                    'message': f'Error closing batch: {error_msg}',
                    'batch_id': None,
                    'orders_count': 0,
                    'total_amount': 0.0
                }
            
            if not batch_data:
                # No qualifying orders
                return {
                    'success': True,
                    'message': 'No orders to process (all direct payments or unidentified customers)',
                    'batch_id': None,
                    'orders_count': 0,
                    'total_amount': 0.0
                }
            
            # Get the batch record for this batch
            batch_record = self.env['pos.order.batch'].get_batch_for_uuid(batch_data['batchId'])
            
            # Publish to RabbitMQ
            success, error_msg = service.publish_batch(batch_data, batch_record)
            
            if not success:
                return {
                    'success': False,
                    'message': f'Error publishing batch: {error_msg}',
                    'batch_id': batch_data['batchId'],
                    'orders_count': batch_data['totalOrders'],
                    'total_amount': batch_data['totalAmount']
                }
            
            _logger.info(f"Successfully closed batch {batch_record.name}")
            
            return {
                'success': True,
                'message': 'Batch closed and sent to facturatie system',
                'batch_id': batch_data['batchId'],
                'orders_count': batch_data['totalOrders'],
                'total_amount': batch_data['totalAmount']
            }
        
        except Exception as e:
            _logger.exception(f"Error in close_daily_batch: {str(e)}")
            return {
                'success': False,
                'message': f'Unexpected error: {str(e)}',
                'batch_id': None,
                'orders_count': 0,
                'total_amount': 0.0
            }

