# -*- coding: utf-8 -*-

import uuid
import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime

_logger = logging.getLogger(__name__)


class PosOrderBatchService:
    """
    Service for closing POS batches and sending to RabbitMQ.
    
    Responsibilities:
    - Collect orders for the batch (by session or date)
    - Filter orders: only Invoice payment type, identified users
    - Build XML batch message
    - Publish to RabbitMQ with error handling
    - Track batch history for idempotency and retry
    """
    
    def __init__(self, env):
        """
        Initialize the service with Odoo environment.
        
        Args:
            env: Odoo environment object
        """
        self.env = env
        self.PosOrderBatch = env['pos.order.batch']
        self.PosOrder = env['pos.order']
        self.Company = env['res.company']
    
    def close_session(self, session) -> Tuple[bool, Optional[str], Optional[Dict]]:
        """
        Close a POS session and aggregate orders into a batch.
        
        Args:
            session: pos.session record to close
        
        Returns:
            (success: bool, error_msg: Optional[str], batch_data: Optional[Dict])
        """
        try:
            # 1. Collect orders from this session
            orders = self._get_orders_for_session(session)
            
            if not orders:
                _logger.info(f"No orders found for session {session.id}")
                return True, None, None
            
            # 2. Filter: only Invoice payment type + identified users
            filtered_orders = self._filter_orders(orders)
            
            if not filtered_orders:
                _logger.info(f"No qualifying orders (Invoice + identified user) for session {session.id}")
                return True, None, None
            
            # 3. Aggregate: group by user, sum items and amounts
            batch_data = self._build_batch_data(filtered_orders, session)
            
            # 4. Create batch record (for tracking and idempotency)
            batch_record = self._create_batch_record(session, filtered_orders, batch_data)
            
            # 5. Build XML and validate
            from src.messaging.message_builders import build_batch_closed_xml
            from src.xml_validator import validate_xml_against_schema
            
            xml_payload = build_batch_closed_xml(batch_data)
            batch_data['xml_payload'] = xml_payload
            
            # Validate XML
            schema_path = '/mnt/extra-addons/kassa_pos/../../../src/schema/kassa-closed-batch.xsd'
            is_valid, error_msg = validate_xml_against_schema(xml_payload, schema_path)
            if not is_valid:
                batch_record.action_mark_failed(f"XML validation failed: {error_msg}")
                return False, f"XML validation failed: {error_msg}", None
            
            # Store XML in batch record
            batch_record.write({'xml_payload': xml_payload})
            
            return True, None, batch_data
        
        except Exception as e:
            error_msg = f"Error closing session: {str(e)}"
            _logger.exception(error_msg)
            return False, error_msg, None
    
    def _get_orders_for_session(self, session) -> List:
        """Get all orders for a POS session."""
        orders = self.PosOrder.search([
            ('session_id', '=', session.id),
            ('state', 'in', ['paid', 'invoiced'])  # Only completed orders
        ])
        _logger.debug(f"Found {len(orders)} completed orders for session {session.id}")
        return orders
    
    def _filter_orders(self, orders: List) -> List:
        """
        Filter orders: only Invoice payment type + identified users (UUID).
        
        Args:
            orders: List of pos.order records
        
        Returns:
            Filtered list of qualifying orders
        """
        filtered = []
        for order in orders:
            # Check 1: payment_type must be 'Invoice'
            if order.payment_type != 'Invoice':
                continue
            
            # Check 2: must have order_id_custom (UUID for identified user)
            if not order.order_id_custom:
                continue
            
            filtered.append(order)
        
        _logger.debug(f"Filtered {len(filtered)} orders (Invoice + identified user)")
        return filtered
    
    def _build_batch_data(self, orders: List, session) -> Dict:
        """
        Build batch data structure from orders.
        
        Aggregates by userId, groups items, sums amounts.
        
        Returns:
            {
                'batchId': UUID,
                'closedAt': ISO8601,
                'currency': 'EUR',
                'users': [
                    {
                        'userId': UUID,
                        'items': [
                            {
                                'productName': str,
                                'quantity': int,
                                'unitPrice': float,
                                'totalPrice': float
                            }
                        ],
                        'totalAmount': float
                    }
                ],
                'totalOrders': int,
                'totalAmount': float,
                'orderIds': [UUID, ...]
            }
        """
        batch_id = str(uuid.uuid4())
        closed_at = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')
        
        # Group orders by userId
        users_dict = {}
        total_amount = 0.0
        order_ids = []
        
        for order in orders:
            user_id = order.order_id_custom
            
            if user_id not in users_dict:
                users_dict[user_id] = {
                    'userId': user_id,
                    'items': [],
                    'totalAmount': 0.0
                }
            
            # Add order lines as items
            for line in order.lines:
                item = {
                    'productName': line.product_id.name or 'Unknown',
                    'quantity': int(line.qty),
                    'unitPrice': float(line.price_unit),
                    'totalPrice': float(line.price_subtotal)
                }
                users_dict[user_id]['items'].append(item)
                users_dict[user_id]['totalAmount'] += item['totalPrice']
            
            total_amount += order.amount_total
            order_ids.append(order.order_id_custom)
        
        batch_data = {
            'batchId': batch_id,
            'closedAt': closed_at,
            'currency': 'EUR',
            'users': list(users_dict.values()),
            'totalOrders': len(orders),
            'totalAmount': total_amount,
            'orderIds': order_ids
        }
        
        _logger.debug(f"Built batch data: {len(orders)} orders, {len(users_dict)} users, €{total_amount}")
        return batch_data
    
    def _create_batch_record(self, session, orders: List, batch_data: Dict):
        """
        Create a PosOrderBatch record for tracking.
        
        Args:
            session: pos.session
            orders: List of pos.order records
            batch_data: Batch data dictionary
        
        Returns:
            Created PosOrderBatch record
        """
        batch_record = self.PosOrderBatch.create({
            'batch_uuid': batch_data['batchId'],
            'pos_session_id': session.id,
            'closed_date': batch_data['closedAt'],
            'total_orders': batch_data['totalOrders'],
            'total_amount': batch_data['totalAmount'],
            'status': 'draft',
        })
        
        # Link orders to batch
        batch_record.write({'order_ids': [(6, 0, orders.ids)]})
        
        _logger.info(f"Created batch record {batch_record.name}")
        return batch_record
    
    def publish_batch(self, batch_data: Dict, batch_record) -> Tuple[bool, Optional[str]]:
        """
        Publish batch to RabbitMQ.
        
        Args:
            batch_data: Batch data dictionary (with xml_payload)
            batch_record: PosOrderBatch record
        
        Returns:
            (success: bool, error_msg: Optional[str])
        """
        try:
            from src.messaging.producer import KassaProducer
            import os
            
            # Get RabbitMQ connection details
            rabbit_host = os.environ.get('RABBIT_HOST', 'rabbitmq')
            rabbit_port = int(os.environ.get('RABBIT_PORT', 5672))
            
            # Create producer and publish
            producer = KassaProducer(host=rabbit_host)
            producer.connect()
            
            xml_payload = batch_data.get('xml_payload', '')
            producer.publish(
                payload=xml_payload,
                routing_key='kassa.closed',
                exchange='kassa.topic'
            )
            
            producer.close()
            
            # Mark batch as sent
            batch_record.action_mark_sent()
            
            _logger.info(f"Batch {batch_record.name} published to RabbitMQ")
            return True, None
        
        except Exception as e:
            error_msg = f"Error publishing batch: {str(e)}"
            _logger.exception(error_msg)
            
            # Mark batch as failed
            batch_record.action_mark_failed(error_msg)
            
            return False, error_msg
    
    def get_failed_batches(self) -> List:
        """Get all batches that failed to send."""
        return self.PosOrderBatch.search([
            ('status', 'in', ['failed', 'retry'])
        ])
    
    def retry_failed_batch(self, batch_record) -> Tuple[bool, Optional[str]]:
        """
        Retry sending a failed batch.
        
        Args:
            batch_record: PosOrderBatch record to retry
        
        Returns:
            (success: bool, error_msg: Optional[str])
        """
        if not batch_record.xml_payload:
            error_msg = "No XML payload found for this batch"
            batch_record.action_mark_failed(error_msg)
            return False, error_msg
        
        batch_data = {
            'xml_payload': batch_record.xml_payload
        }
        
        success, error_msg = self.publish_batch(batch_data, batch_record)
        return success, error_msg
