# -*- coding: utf-8 -*-

from odoo import models, fields, api


class ResPartner(models.Model):
    _inherit = 'res.partner'

    badge_code = fields.Char(
        string='Badge Code',
        help='Badge code voor scanner/barcode functionaliteit',
        index=True
    )

    role = fields.Selection([
        ('student', 'Student'),
        ('staff', 'Staff'),
        ('guest', 'Guest'),
        ('admin', 'Admin')
    ], string='Role', default='guest', required=True)

    company_id_custom = fields.Char(
        string='Company ID',
        help='Optioneel company ID voor klant'
    )
