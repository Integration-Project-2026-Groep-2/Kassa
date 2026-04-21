# -*- coding: utf-8 -*-

import uuid
from odoo import models, fields, api
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)


class PosOrderBatch(models.Model):
    """
    Track POS order batches (daily closing sessions).
    
    Used for:
    - Idempotency: prevent duplicate sending of the same batch
    - Retry logic: track failed batches for retry
    - Audit: maintain history of all closings
    """
    
    _name = 'pos.order.batch'
    _description = 'POS Order Batch (Afsluitknop)'
    _order = 'created_date DESC'
    
    name = fields.Char(
        string='Batch ID',
        readonly=True,
        copy=False,
        help='Unique identifier for this batch session'
    )
    
    batch_uuid = fields.Char(
        string='Batch UUID',
        readonly=True,
        copy=False,
        index=True,
        help='UUID used in the XML message for idempotency'
    )
    
    pos_session_id = fields.Many2one(
        'pos.session',
        string='POS Session',
        ondelete='restrict',
        help='Reference to the POS session that was closed'
    )
    
    created_date = fields.Datetime(
        string='Created',
        readonly=True,
        default=lambda self: fields.Datetime.now()
    )
    
    closed_date = fields.Datetime(
        string='Closed Date',
        help='Date/time when the batch was closed (ISO8601)'
    )
    
    status = fields.Selection([
        ('draft', 'Draft'),
        ('sent', 'Sent'),
        ('failed', 'Failed'),
        ('retry', 'Retry Pending'),
        ('confirmed', 'Confirmed'),
    ], string='Status', default='draft', index=True)
    
    total_orders = fields.Integer(
        string='Total Orders',
        help='Number of orders in this batch'
    )
    
    total_amount = fields.Float(
        string='Total Amount',
        digits=(12, 2),
        help='Total value of all orders in this batch'
    )
    
    order_ids = fields.Many2many(
        'pos.order',
        'pos_order_batch_rel',
        'batch_id',
        'order_id',
        string='Orders',
        readonly=True,
        help='Orders included in this batch'
    )
    
    xml_payload = fields.Text(
        string='XML Payload',
        readonly=True,
        help='The XML message sent to RabbitMQ'
    )
    
    error_message = fields.Text(
        string='Error Message',
        help='Error details if sending failed'
    )
    
    retry_count = fields.Integer(
        string='Retry Count',
        default=0,
        help='Number of times this batch has been retried'
    )
    
    next_retry_date = fields.Datetime(
        string='Next Retry Date',
        help='When to retry this batch if sending failed'
    )
    
    notes = fields.Text(
        string='Notes',
        help='Additional notes or comments about this batch'
    )
    
    _sql_constraints = [
        ('batch_uuid_unique', 'UNIQUE(batch_uuid)', 'Batch UUID must be unique'),
    ]
    
    @api.model
    def create(self, vals):
        """Override create to generate UUID if not provided."""
        if not vals.get('batch_uuid'):
            vals['batch_uuid'] = str(uuid.uuid4())
        
        if not vals.get('name'):
            vals['name'] = f"BATCH-{vals['batch_uuid'][:8].upper()}"
        
        return super().create(vals)
    
    def action_mark_sent(self):
        """Mark batch as sent (called after successful RabbitMQ publish)."""
        self.write({
            'status': 'sent',
        })
        _logger.info(f"Batch {self.name} marked as sent")
    
    def action_mark_failed(self, error_msg: str):
        """Mark batch as failed and store error message."""
        self.write({
            'status': 'failed',
            'error_message': error_msg,
        })
        _logger.warning(f"Batch {self.name} marked as failed: {error_msg}")
    
    def action_mark_retry(self, retry_date=None):
        """Mark batch for retry."""
        retry_count = self.retry_count + 1
        self.write({
            'status': 'retry',
            'retry_count': retry_count,
            'next_retry_date': retry_date,
        })
        _logger.info(f"Batch {self.name} marked for retry (attempt {retry_count})")
    
    def action_mark_confirmed(self):
        """Mark batch as confirmed (called when CRM/Facturatie system confirms receipt)."""
        self.write({
            'status': 'confirmed',
        })
        _logger.info(f"Batch {self.name} marked as confirmed")
    
    @api.model
    def get_batch_for_uuid(self, batch_uuid: str):
        """Get an existing batch by UUID (for idempotency check)."""
        return self.search([('batch_uuid', '=', batch_uuid)], limit=1)
    
    def action_view_orders(self):
        """Action to view orders in this batch."""
        return {
            'name': f'Orders in {self.name}',
            'type': 'ir.actions.act_window',
            'res_model': 'pos.order',
            'view_mode': 'tree,form',
            'domain': [('id', 'in', self.order_ids.ids)],
            'context': {'create': False},
        }
