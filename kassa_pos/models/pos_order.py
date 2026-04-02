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
        - Cash of Card = Direct
        - Invoice = Invoice
        """
        for order in self:
            payment_type = 'Direct'  # Default

            if order.payment_ids:
                # Check alle payment methods van deze order
                for payment in order.payment_ids:
                    if payment.payment_method_id:
                        payment_name = payment.payment_method_id.name.lower()

                        # Als één van de payments "invoice" is, dan is hele order Invoice type
                        if 'invoice' in payment_name:
                            payment_type = 'Invoice'
                            break

            order.payment_type = payment_type

    @api.model_create_multi
    def create(self, vals_list):
        """
        Override create om UUID te genereren voor order_id_custom
        """
        for vals in vals_list:
            if not vals.get('order_id_custom'):
                vals['order_id_custom'] = str(uuid.uuid4())

        return super(PosOrder, self).create(vals_list)

    def _export_for_rabbitmq(self):
        """
        Helper method om order data te exporteren in formaat voor RabbitMQ
        Deze methode kan door Developer 2 worden gebruikt

        Returns dict met structuur zoals in ConsumptionOrder.xml
        """
        self.ensure_one()

        # Get user/customer data
        partner = self.partner_id
        user_id = partner.user_id_custom if partner else None

        # Get order items
        items = []
        for line in self.lines:
            items.append({
                'productName': line.product_id.name,
                'quantity': line.qty,
                'price': line.price_unit,
            })

        # Build order data structure
        order_data = {
            'orderId': self.order_id_custom,
            'userId': user_id,
            'items': items,
            'totalAmount': self.amount_total,
            'paymentType': self.payment_type,
            'timestamp': self.date_order.isoformat() if self.date_order else None,
        }

        return order_data

    def _export_payment_for_rabbitmq(self):
        """
        Helper method om payment data te exporteren voor RabbitMQ
        Deze methode kan door Developer 2 worden gebruikt

        Returns dict met structuur zoals in PaymentCompleted.xml
        """
        self.ensure_one()

        # Get primary payment (kan meerdere zijn, neem eerste)
        payment = self.payment_ids[0] if self.payment_ids else None

        if not payment:
            return None

        partner = self.partner_id
        user_id = partner.user_id_custom if partner else None

        # Determine payment method name
        payment_method_name = payment.payment_method_id.name if payment.payment_method_id else 'Unknown'

        # Clean up payment method name (remove "(Direct)" suffix etc)
        if '(' in payment_method_name:
            payment_method_name = payment_method_name.split('(')[0].strip()

        payment_data = {
            'paymentId': str(uuid.uuid4()),  # Generate payment UUID
            'orderId': self.order_id_custom,
            'userId': user_id,
            'paymentMethod': payment_method_name,
            'amount': self.amount_total,
            'timestamp': self.date_order.isoformat() if self.date_order else None,
        }

        return payment_data

    @api.model
    def create_from_ui(self, orders, draft=False):
        """
        Override van de POS frontend call.
        Na het verwerken van de order → stuur berichten naar RabbitMQ.
        """
        order_ids = super().create_from_ui(orders, draft=draft)

        for order_info in order_ids:
            order = self.browse(order_info['id'])

            # Alleen versturen als de order betaald/afgerond is (niet bij drafts)
            if order.state in ('paid', 'done', 'invoiced'):
                self._trigger_rabbitmq_messages(order)

        return order_ids

    def _trigger_rabbitmq_messages(self, order):
        """
        Stuur ConsumptionOrder en PaymentCompleted berichten naar RabbitMQ.
        """
        consumption_data = order._export_for_rabbitmq()
        if consumption_data:
            rabbitmq_sender.send_consumption_order(consumption_data)

        payment_data = order._export_payment_for_rabbitmq()
        if payment_data:
            rabbitmq_sender.send_payment_completed(payment_data)
