# -*- coding: utf-8 -*-

import uuid
from odoo import models, fields, api
from ..utils import rabbitmq_sender


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

    def _get_tax_rate_for_product(self, product):
        """
        Map product category to VAT rate (6% for Food, 21% for Drinks/other).
        
        Args:
            product: product.product record
            
        Returns:
            float: Tax rate (6.0 or 21.0)
        """
        if not product or not product.categ_id:
            return 21.0
        
        category_name = (product.categ_id.name or "").lower().strip()
        
        # Food → 6% VAT
        if category_name == "food":
            return 6.0
        
        # Drinks → 21% VAT (alcoholic beverages)
        if category_name == "drinks":
            return 21.0
        
        # Default to 21%
        return 21.0

    def _build_gks_vat_breakdown(self):
        """
        Bouw een VAT-breakdown payload geschikt voor het GKS ticket.

        Retourneert een dict met netto en btw bedragen per tarief (6% en 21%),
        plus totalen. Deze helper probeert eerst de tax info van de orderlijn
        te gebruiken (`line.tax_ids`), en valt terug naar product category mapping.

        Resultaatvoorbeeld:
        {
            'rates': {
                6: {'net': 3.5, 'vat': 0.21},
                21: {'net': 3.98, 'vat': 0.83}
            },
            'net_total': 7.48,
            'vat_total': 1.04,
            'gross_total': 8.52
        }
        """
        self.ensure_one()

        rates = {6: {'net': 0.0, 'vat': 0.0}, 21: {'net': 0.0, 'vat': 0.0}}
        net_total = 0.0
        vat_total = 0.0
        gross_total = 0.0

        for line in self.lines:
            try:
                qty = float(line.qty)
            except Exception:
                qty = 0.0

            try:
                unit_price = float(line.price_unit)
            except Exception:
                unit_price = 0.0

            # Calculation: Qty × Unit Price = Gross (including VAT)
            gross = unit_price * qty
            gross_total += gross

            # Determine VAT rate: 
            # 1) Prefer line.tax_ids if available
            rate = None
            if hasattr(line, 'tax_ids') and line.tax_ids:
                try:
                    rate = float(line.tax_ids[0].amount)
                except Exception:
                    rate = None
            
            # 2) Fallback to product category mapping
            if rate is None and line.product_id:
                rate = self._get_tax_rate_for_product(line.product_id)
            
            # 3) Default to 21% if all else fails
            if rate is None:
                rate = 21.0

            # Calculate net from gross: net = gross / (1 + rate/100)
            net = gross / (1.0 + (rate / 100.0)) if rate >= 0 else gross
            vat = gross - net

            # Aggregate by rate group
            key = 6 if int(round(rate)) == 6 else 21
            rates[key]['net'] += round(net, 2)
            rates[key]['vat'] += round(vat, 2)
            net_total += net
            vat_total += vat

        return {
            'rates': rates,
            'net_total': round(net_total, 2),
            'vat_total': round(vat_total, 2),
            'gross_total': round(gross_total, 2)
        }

    @api.model
    def create_from_ui(self, orders, draft=False):
        """
        Override van de POS frontend call.
        Na het verwerken van de order → stuur berichten naar RabbitMQ.
        """
        order_ids = super().create_from_ui(orders, draft=draft)

        for order_info in order_ids:
            order = self.browse(order_info['id'])

            if order.state in ('paid', 'done', 'invoiced'):
                self._trigger_rabbitmq_messages(order)

        return order_ids

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

