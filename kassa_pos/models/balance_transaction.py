# -*- coding: utf-8 -*-

from odoo import models, fields


class BalanceTransaction(models.Model):
    _name = 'balance.transaction'
    _description = 'Saldo Transactie'
    _order = 'create_date desc'

    partner_id = fields.Many2one(
        'res.partner', string='Klant', required=True, ondelete='restrict', index=True
    )
    amount = fields.Float(string='Bedrag (€)', required=True, digits=(10, 2))
    transaction_type = fields.Selection([
        ('topup', 'Saldo Opladen'),
        ('payment', 'Betaling'),
    ], string='Type', required=True)
    payment_method = fields.Selection([
        ('cash', 'Cash'),
        ('card', 'Kaart'),
        ('balance', 'Saldo'),
    ], string='Betaalmethode')
    note = fields.Char(string='Notitie')
    pos_order_id = fields.Many2one('pos.order', string='POS Order', ondelete='set null')
    balance_after = fields.Float(string='Saldo na transactie (€)', digits=(10, 2))
