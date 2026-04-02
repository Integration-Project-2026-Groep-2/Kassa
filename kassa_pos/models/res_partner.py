# -*- coding: utf-8 -*-

from odoo import models, fields, api


class ResPartner(models.Model):
    _inherit = 'res.partner'

    user_id_custom = fields.Char(
        string='User ID',
        help='UUID voor user identificatie',
        index=True
    )

    badge_code = fields.Char(
        string='Badge Code',
        help='Badge code voor scanner/barcode functionaliteit',
        index=True
    )

    role = fields.Selection([
        ('Customer', 'Customer'),
        ('Cashier', 'Cashier'),
        ('Admin', 'Admin')
    ], string='Role', default='Customer', required=True)

    company_id_custom = fields.Char(
        string='Company ID',
        help='Optioneel company ID (UUID format) voor klant'
    )
