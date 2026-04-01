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
