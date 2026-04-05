# -*- coding: utf-8 -*-
"""
User creation handler for POS User Registration feature.

Handles form submissions from the POS "Add User" modal and:
1. Creates contacts in Odoo
2. Publishes User messages to RabbitMQ
3. Implements fallback queue for offline scenarios
"""

from odoo import models, fields, api
from odoo.exceptions import ValidationError
import logging
import uuid as uuid_lib
import xml.etree.ElementTree as ET
from datetime import datetime

logger = logging.getLogger(__name__)


class UserMessageQueue(models.Model):
    """Queue for storing pending user messages when Integration Service is offline."""
    
    _name = 'user.message.queue'
    _description = 'User Message Queue'
    
    user_id_custom = fields.Char(
        string='User ID',
        help='UUID of the user',
        required=True
    )
    message_type = fields.Selection([
        ('UserCreated', 'User Created'),
        ('UserUpdated', 'User Updated'),
        ('UserDeleted', 'User Deleted'),
    ], string='Message Type', required=True)
    
    payload = fields.Text(
        string='Message Payload',
        help='JSON or XML payload',
        required=True
    )
    
    status = fields.Selection([
        ('pending', 'Pending'),
        ('sent', 'Sent'),
        ('failed', 'Failed'),
    ], string='Status', default='pending', required=True)
    
    retry_count = fields.Integer(
        string='Retry Count',
        default=0,
        help='Number of failed attempts'
    )
    
    created_at = fields.Datetime(
        string='Created At',
        default=fields.Datetime.now
    )
    
    last_error = fields.Text(
        string='Last Error',
        help='Error message from last failed attempt'
    )
    
    def action_retry_all_pending(self):
        """Manually retry all pending messages."""
        pending_messages = self.search([('status', '=', 'pending')])
        for message in pending_messages:
            message.action_send()
    
    def action_send(self):
        """Send message to RabbitMQ."""
        try:
            from ..utils.rabbitmq_sender import send_user_created, send_user_updated, send_user_deleted
            
            for message in self:
                try:
                    if message.message_type == 'UserCreated':
                        sent = send_user_created(_parse_user_payload(message.payload))
                    elif message.message_type == 'UserUpdated':
                        sent = send_user_updated(_parse_user_payload(message.payload))
                    elif message.message_type == 'UserDeleted':
                        sent = send_user_deleted(message.user_id_custom)
                    else:
                        raise ValueError(f"Unsupported message type: {message.message_type}")

                    if not sent:
                        raise RuntimeError('RabbitMQ sender returned False')
                    
                    message.write({
                        'status': 'sent',
                        'last_error': '',
                    })
                    logger.info(
                        "User message sent successfully [user_id=%s type=%s]",
                        message.user_id_custom, message.message_type
                    )
                except Exception as e:
                    message.retry_count += 1
                    message.write({
                        'status': 'failed',
                        'last_error': str(e),
                    })
                    logger.error(
                        "Failed to send user message [user_id=%s retry=%d error=%s]",
                        message.user_id_custom, message.retry_count, str(e)
                    )
        
        except ImportError:
            logger.warning("RabbitMQ producer not available - message queued locally")


def _parse_user_payload(xml_payload):
    """Parse a User XML payload into dict expected by sender helpers."""
    try:
        root = ET.fromstring(xml_payload)
        return {
            'userId': root.findtext('userId', '').strip(),
            'firstName': root.findtext('firstName', '').strip(),
            'lastName': root.findtext('lastName', '').strip(),
            'email': root.findtext('email', '').strip(),
            'companyId': root.findtext('companyId', '').strip() or None,
            'badgeCode': root.findtext('badgeCode', '').strip(),
            'role': root.findtext('role', '').strip(),
            'createdAt': root.findtext('createdAt', '').strip() or None,
            'updatedAt': root.findtext('updatedAt', '').strip() or None,
        }
    except Exception:
        return {
            'userId': '',
            'firstName': '',
            'lastName': '',
            'email': '',
            'companyId': None,
            'badgeCode': '',
            'role': '',
            'createdAt': None,
            'updatedAt': None,
        }


class PosSession(models.Model):
    """Extend POS Session to handle user creation."""
    
    _inherit = 'pos.session'
    
    @api.model
    def create_and_publish_user(self, user_data):
        """
        Create a new user (contact) and publish to RabbitMQ.
        
        Called from frontend when user registration form is submitted.
        
        Args:
            user_data (dict): User information from the registration form
                - userId: UUID
                - firstName: First name
                - lastName: Last name
                - email: Email address
                - phone: Phone number (optional)
                - role: User role
                - companyId: Company UUID (optional)
                - badgeCode: Badge code
                - gdprConsent: Boolean
                - isActive: Boolean
                - confirmedAt: ISO timestamp
        
        Returns:
            dict: Result with contact_id and message_id
        
        Raises:
            ValidationError: If validation fails
        """
        try:
            # Validate required fields
            self._validate_user_data(user_data)
            
            # Create contact in Odoo
            contact = self._create_contact(user_data)
            logger.info(
                "Contact created [id=%d user_id=%s email=%s]",
                contact.id, user_data['userId'], user_data['email']
            )
            
            # Build and publish User message
            xml_message = self._build_user_xml(user_data)
            message_result = self._publish_user_message(
                user_data['userId'],
                xml_message
            )
            
            return {
                'contact_id': contact.id,
                'user_id': user_data['userId'],
                'message_sent': message_result['sent'],
                'message_id': message_result.get('message_id'),
            }
        
        except ValidationError:
            raise
        except Exception as e:
            logger.error("Error creating and publishing user: %s", str(e))
            raise ValidationError(f"Error creating user: {str(e)}")
    
    def _validate_user_data(self, user_data):
        """Validate user data from registration form."""
        from src.models.user import User
        
        required_fields = ['userId', 'firstName', 'lastName', 'email', 'role', 'badgeCode']
        for field in required_fields:
            if not user_data.get(field):
                raise ValidationError(f"{field} is required")
        
        # Use User model validation
        user = User(**user_data)
        valid, error = user.validate()
        if not valid:
            raise ValidationError(error)
    
    def _create_contact(self, user_data):
        """Create a contact in Odoo."""
        ResPartner = self.env['res.partner']
        
        # Check for duplicate email
        existing = ResPartner.search([('email', '=', user_data['email'])])
        if existing:
            raise ValidationError(
                f"Contact with email '{user_data['email']}' already exists"
            )
        
        # Map role to Odoo value
        role_map = {
            'VISITOR': 'Customer',
            'COMPANY_CONTACT': 'Customer',
            'SPEAKER': 'Customer',
            'EVENT_MANAGER': 'Customer',
            'CASHIER': 'Cashier',
            'BAR_STAFF': 'Customer',
            'ADMIN': 'Admin',
        }
        
        contact_values = {
            'name': f"{user_data['firstName']} {user_data['lastName']}",
            'email': user_data['email'],
            'phone': user_data.get('phone', ''),
            'user_id_custom': user_data['userId'],
            'badge_code': user_data.get('badgeCode', ''),
            'role': role_map.get(user_data['role'], 'Customer'),
            'company_id_custom': user_data.get('companyId'),
            'customer': True,
            'is_company': False,
        }
        
        contact = ResPartner.create(contact_values)
        return contact
    
    def _build_user_xml(self, user_data):
        """Build XML User message."""
        from src.messaging.message_builders import build_user_xml
        
        xml = build_user_xml(user_data)
        return xml
    
    def _publish_user_message(self, user_id, xml_message):
        """
        Publish User message to RabbitMQ.
        
        If Integration Service is offline, queue the message for retry.
        """
        try:
            from src.messaging.producer import KassaProducer
            
            producer = KassaProducer(host='localhost')
            producer.connect()
            
            try:
                producer.publish(xml_message, routing_key='integration.user.created')
                logger.info("User message published [user_id=%s]", user_id)
                return {
                    'sent': True,
                    'message_id': user_id,
                }
            finally:
                producer.close()
        
        except Exception as e:
            logger.warning(
                "Failed to publish user message, queuing for retry [user_id=%s error=%s]",
                user_id, str(e)
            )
            
            # Queue message for later retry
            try:
                self.env['user.message.queue'].create({
                    'user_id_custom': user_id,
                    'message_type': 'UserCreated',
                    'payload': xml_message,
                    'status': 'pending',
                    'retry_count': 0,
                })
            except Exception as queue_error:
                logger.error("Failed to queue message: %s", str(queue_error))
            
            # Still return success - message will be retried later
            return {
                'sent': False,
                'message_id': user_id,
                'queued': True,
            }


class PosConfig(models.Model):
    """Extend POS Config for user registration settings."""
    
    _inherit = 'pos.config'
    
    enable_user_registration = fields.Boolean(
        string='Enable User Registration',
        default=True,
        help='Show "Add User" button in POS'
    )
    
    user_registration_requires_approval = fields.Boolean(
        string='Require Approval',
        default=False,
        help='Require manager approval before user can be used'
    )
    
    user_registration_notify_crm = fields.Boolean(
        string='Notify CRM',
        default=True,
        help='Send user data to CRM system via RabbitMQ'
    )
