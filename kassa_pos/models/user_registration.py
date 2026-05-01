# -*- coding: utf-8 -*-
"""
User creation handler for POS User Registration feature.

Handles form submissions from the POS "Add User" modal and:
1. Creates contacts in Odoo
2. Publishes KassaUserCreated messages to RabbitMQ via kassa_pos.utils.rabbitmq_sender
3. Implements fallback queue for offline scenarios

Architecture note
-----------------
Publishing is done via kassa_pos/utils/rabbitmq_sender.py which is fully
self-contained inside this Odoo addon (only depends on pika and env vars).
We intentionally do NOT import from src.* here because src is a separate
Python package that lives outside the Odoo addon tree and is not reliably on
sys.path in all deployment environments (local dev vs. VM container).
"""

from odoo import models, fields, api
from odoo.exceptions import ValidationError
import logging

logger = logging.getLogger(__name__)


class UserMessageQueue(models.Model):
    """Queue for storing pending user messages when RabbitMQ is offline."""

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
        """Re-send a queued message to RabbitMQ."""
        from kassa_pos.utils.rabbitmq_sender import send_kassa_user_created

        for message in self:
            try:
                if message.message_type == 'UserCreated':
                    # payload is the raw XML string — wrap it in a dict so the
                    # sender can rebuild it.  Simpler: call _publish_to_topic_exchange
                    # directly with the stored XML.
                    from kassa_pos.utils.rabbitmq_sender import (
                        _publish_to_topic_exchange,
                        ROUTING_KEY_KASSA_USER_CREATED,
                    )
                    ok = _publish_to_topic_exchange(
                        ROUTING_KEY_KASSA_USER_CREATED, message.payload
                    )
                else:
                    logger.warning(
                        "action_send: unsupported message type '%s' [id=%d]",
                        message.message_type, message.id
                    )
                    continue

                if ok:
                    message.write({'status': 'sent', 'last_error': ''})
                    logger.info(
                        "Queued message sent successfully [id=%d user_id=%s type=%s]",
                        message.id, message.user_id_custom, message.message_type
                    )
                else:
                    message.retry_count += 1
                    message.write({
                        'status': 'failed',
                        'last_error': 'publish returned False',
                        'retry_count': message.retry_count,
                    })

            except Exception as e:
                message.retry_count += 1
                message.write({
                    'status': 'failed',
                    'last_error': str(e),
                    'retry_count': message.retry_count,
                })
                logger.error(
                    "Failed to send queued message [id=%d user_id=%s error=%s]",
                    message.id, message.user_id_custom, str(e)
                )


class PosSession(models.Model):
    """Extend POS Session to handle user creation and RabbitMQ publishing."""

    _inherit = 'pos.session'

    @api.model
    def create_and_publish_user(self, user_data):
        """
        Create a new contact and publish a KassaUserCreated message to RabbitMQ.

        Called from the POS frontend when the user registration form is submitted.

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
            dict: Result with contact_id and message_sent flag
        """
        try:
            self._validate_user_data(user_data)

            contact = self._create_contact(user_data)
            logger.info(
                "Contact created [id=%d user_id=%s email=%s]",
                contact.id, user_data['userId'], user_data['email']
            )

            message_result = self._publish_user_message(user_data)

            return {
                'contact_id': contact.id,
                'user_id': user_data['userId'],
                'message_sent': message_result['sent'],
                'message_id': message_result.get('message_id'),
            }

        except ValidationError:
            raise
        except Exception as e:
            logger.error("Error in create_and_publish_user: %s", str(e), exc_info=True)
            raise ValidationError(f"Error creating user: {str(e)}")

    def _validate_user_data(self, user_data):
        """Validate required fields on the incoming user_data dict."""
        required_fields = ['userId', 'firstName', 'lastName', 'email', 'role', 'badgeCode']
        for field in required_fields:
            if not user_data.get(field):
                raise ValidationError(f"{field} is required")

    def _create_contact(self, user_data):
        """Create a res.partner contact in Odoo."""
        ResPartner = self.env['res.partner']

        existing = ResPartner.search([('email', '=', user_data['email'])])
        if existing:
            raise ValidationError(
                f"Contact with email '{user_data['email']}' already exists"
            )

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
            'is_company': False,
            'company_type': 'person',
            'customer_rank': 1,
            'active': True,
        }

        return ResPartner.create(contact_values)

    def _publish_user_message(self, user_data):
        """
        Publish a KassaUserCreated message to the user.topic RabbitMQ exchange.

        Uses kassa_pos.utils.rabbitmq_sender which is self-contained inside the
        Odoo addon and only requires pika + environment variables.  Falls back to
        the user.message.queue model if RabbitMQ is unreachable.
        """
        try:
            from kassa_pos.utils.rabbitmq_sender import send_kassa_user_created

            logger.debug(
                "Publishing KassaUserCreated for user_id=%s", user_data['userId']
            )
            ok = send_kassa_user_created(user_data)

            if ok:
                logger.info(
                    "KassaUserCreated published [user_id=%s email=%s]",
                    user_data['userId'], user_data['email']
                )
                return {'sent': True, 'message_id': user_data['userId']}
            else:
                raise RuntimeError("send_kassa_user_created returned False")

        except Exception as e:
            logger.warning(
                "Failed to publish KassaUserCreated, queuing for retry "
                "[user_id=%s error=%s]",
                user_data['userId'], str(e)
            )
            self._queue_user_message(user_data, str(e))
            return {'sent': False, 'message_id': user_data['userId'], 'queued': True}

    def _queue_user_message(self, user_data, error_msg):
        """Store a failed publish in user.message.queue for later retry."""
        from kassa_pos.utils.rabbitmq_sender import _build_kassa_user_created_xml
        try:
            xml_payload = _build_kassa_user_created_xml(user_data)
            self.env['user.message.queue'].create({
                'user_id_custom': user_data['userId'],
                'message_type': 'UserCreated',
                'payload': xml_payload,
                'status': 'pending',
                'retry_count': 0,
                'last_error': error_msg,
            })
            logger.info(
                "KassaUserCreated queued for retry [user_id=%s]", user_data['userId']
            )
        except Exception as queue_error:
            logger.error("Failed to queue message: %s", str(queue_error))


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
