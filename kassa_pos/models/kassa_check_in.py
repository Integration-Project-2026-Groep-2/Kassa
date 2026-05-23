# -*- coding: utf-8 -*-
from odoo import api, models


class KassaCheckIn(models.Model):
    _name = "kassa.check.in"
    _description = "Kassa IoT Check-In Brug"

    @api.model
    def notify_pos(self, partner_id):
        """Stuur een bus-notificatie naar alle verbonden POS-clients voor deze check-in."""
        partner = self.env["res.partner"].browse(partner_id)
        if not partner.exists():
            return False
        self.env["bus.bus"]._sendone(
            "kassa_check_in",
            "check_in",
            {"partner_id": partner.id, "partner_name": partner.name},
        )
        return True
