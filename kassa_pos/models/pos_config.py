# -*- coding: utf-8 -*-

import logging
from odoo import models, api

_logger = logging.getLogger(__name__)

class PosConfig(models.Model):
    _inherit = 'pos.config'

    @api.model
    def _register_hook(self):
        """
        Runs after the Odoo registry has loaded.
        Ensures the 'Kassa Main' POS configuration, journals, and payment methods exist.
        This provides a highly reliable fallback for when Odoo's initial post_init_hook is bypassed
        on subsequent startup cycles or when upgrading existing databases.
        """
        super()._register_hook()
        
        # Check if the 'Kassa Main' shop config already exists. If not, trigger post_init setup.
        try:
            existing = self.env['pos.config'].sudo().search([('name', '=', 'Kassa Main')], limit=1)
            if not existing:
                _logger.info("Kassa Main pos.config not found. Running post_init setup hook defensively...")
                from odoo.addons.kassa_pos import post_init
                post_init(self.env)
                _logger.info("Defensive post_init setup hook completed successfully.")
        except Exception as e:
            _logger.exception("Failed to run post_init hook defensively in pos.config _register_hook: %s", e)
