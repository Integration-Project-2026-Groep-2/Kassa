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
        Alleen aanroepen als paymentType=Invoice en klant gelinkt aan een bedrijf.

        Verplichte velden: orderId, userId, companyId, amount, currency, orderedAt, items
        """
        self.ensure_one()

        partner = self.partner_id

        items = []
        for line in self.lines:
            items.append({
                'productName': line.product_id.name,
                'quantity': int(line.qty),
                'unitPrice': line.price_unit,
            })

        company = partner.parent_id if (partner and partner.parent_id) else None

        return {
            'orderId': self.order_id_custom,
            'userId': partner.user_id_custom if partner else '',
            'companyId': partner.company_id_custom if partner else '',
            'amount': self.amount_total,
            'currency': 'EUR',
            'orderedAt': self.date_order.strftime('%Y-%m-%dT%H:%M:%SZ') if self.date_order else None,
            'items': items,
            'email': partner.email if partner else None,
            'companyName': company.name if company else None,
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

        - Altijd: PaymentConfirmed → kassa.payment.confirmed (Contract 16, naar CRM)
        - Alleen bij Invoice + bedrijfskoppeling:
          InvoiceRequested → kassa.invoice.requested (Contract K-01, naar Facturatie)
        """
        # Contract 16 — altijd versturen bij betaalde order
        payment_data = order._build_payment_confirmed_data()
        if payment_data.get('email'):
            rabbitmq_sender.send_payment_confirmed(payment_data)

        # Contract K-01 — alleen bij Invoice-betaling gelinkt aan een bedrijf
        if order.payment_type == 'Invoice' and order.partner_id and order.partner_id.company_id_custom:
            invoice_data = order._build_invoice_requested_data()
            rabbitmq_sender.send_invoice_requested(invoice_data)

    @api.model
    def close_daily_batch(self, session=None) -> dict:
        """
        Afsluitknop: Collect today's transactions and send to facturatie.
        
        This is called when the POS manager closes the daily session.
        It aggregates all orders with:
        - paymentType = 'Invoice'
        - Identified customer (UUID in order_id_custom)
        
        And sends them as a BatchClosed message to RabbitMQ.
        
        Args:
            session: Optional pos.session record to close.
                    If not provided, uses the current active session.
        
        Returns:
            {
                'success': bool,
                'message': str,
                'batch_id': Optional[str],
                'orders_count': int,
                'total_amount': float
            }
        """
        import logging
        _logger = logging.getLogger(__name__)
        
        try:
            # Get the session to close
            if not session:
                # Try to find the current active session
                PosSession = self.env['pos.session']
                session = PosSession.search([
                    ('state', '=', 'opened')
                ], limit=1)
            
            if not session:
                return {
                    'success': False,
                    'message': 'No active POS session found',
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

