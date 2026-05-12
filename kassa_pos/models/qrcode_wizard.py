# -*- coding: utf-8 -*-

import logging
from odoo import models, fields

_logger = logging.getLogger(__name__)


class ResPartnerQRCodeWizard(models.TransientModel):
    _name = 'res.partner.qrcode.wizard'
    _description = 'QR Code Wizard for Partner Badge Code'

    partner_id = fields.Many2one('res.partner', string='Partner', readonly=True)
    badge_code = fields.Char(string='Badge Code', readonly=True)
    qr_code_image = fields.Binary(string='QR Code', readonly=True)

    def action_close(self):
        """Close the wizard."""
        return {'type': 'ir.actions.act_window_close'}
