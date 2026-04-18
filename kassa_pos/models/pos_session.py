# -*- coding: utf-8 -*-

import logging
from odoo import models, api

_logger = logging.getLogger(__name__)


class PosSession(models.Model):
    _inherit = 'pos.session'

    def action_pos_session_closing_control(self, bank_payment_method_diffs=None):
        """
        Override session closing control to trigger the daily batch close (Afsluitknop)
        This is called before the final session close
        """
        _logger.info('[Afsluitknop] Session %s closing control initiated', self.name)
        
        # Trigger the daily batch close
        try:
            # Get all orders for this session to close batch
            pos_order_model = self.env['pos.order']
            result = pos_order_model.close_daily_batch(session=self)
            
            if result.get('success'):
                _logger.info(
                    '[Afsluitknop] Batch closed successfully: batchId=%s, orders=%d, total=%.2f',
                    result.get('batch_id'),
                    result.get('orders_count'),
                    result.get('total_amount')
                )
            else:
                _logger.warning(
                    '[Afsluitknop] Batch close warning: %s',
                    result.get('message', 'Unknown error')
                )
        except Exception as e:
            _logger.exception('[Afsluitknop] Error during batch close: %s', str(e))
            # Don't prevent session close on error
        
        # Continue with normal session closing control, passing the parameter
        return super().action_pos_session_closing_control(bank_payment_method_diffs=bank_payment_method_diffs)

    def action_pos_session_close(self, balancing_account=None, amount_to_balance=None, bank_payment_method_diffs=None):
        """
        Override the main session close method to ensure batch is processed
        """
        _logger.info('[Afsluitknop] Session %s close initiated', self.name)
        
        # Try to close batch if not already done
        try:
            pos_order_model = self.env['pos.order']
            # Only process if there are unprocessed orders
            unprocessed = pos_order_model.search([
                ('session_id', '=', self.id),
                ('state', '!=', 'done'),
            ])
            
            if unprocessed:
                result = pos_order_model.close_daily_batch(session=self)
                _logger.info('[Afsluitknop] Pre-close batch processing: %s', result)
        except Exception as e:
            _logger.exception('[Afsluitknop] Error in pre-close batch: %s', str(e))
        
        # Continue with normal session close, passing all parameters
        return super().action_pos_session_close(balancing_account, amount_to_balance, bank_payment_method_diffs)
