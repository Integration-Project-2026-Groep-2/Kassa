# -*- coding: utf-8 -*-

import logging
from datetime import datetime
import xml.etree.ElementTree as ET

from odoo import models, fields, api


_logger = logging.getLogger(__name__)


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

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for record in records:
            if record.user_id_custom:
                record._publish_user_change('created')
        return records

    def write(self, vals):
        result = super().write(vals)

        watched_fields = {
            'name',
            'email',
            'phone',
            'badge_code',
            'role',
            'company_id_custom',
            'user_id_custom',
        }
        if watched_fields.intersection(vals.keys()):
            for record in self:
                if record.user_id_custom:
                    record._publish_user_change('updated')

        return result

    def unlink(self):
        delete_candidates = [
            {
                'user_id_custom': record.user_id_custom,
                'email': record.email or '',
            }
            for record in self
            if record.user_id_custom
        ]

        result = super().unlink()

        for candidate in delete_candidates:
            self._publish_user_deleted(
                candidate['user_id_custom'],
                candidate['email'],
            )

        return result

    def _publish_user_change(self, operation):
        self.ensure_one()

        if operation not in ('created', 'updated'):
            return

        routing_key = f'integration.user.{operation}'
        user_data = self._build_user_data_dict()

        if operation == 'created':
            queue_message_type = 'UserCreated'
            payload = self._build_user_created_payload_xml(user_data)
        else:
            queue_message_type = 'UserUpdatedIntegration'
            payload = self._build_user_updated_payload_xml(user_data)

        # 1. Interne integration-service queue (integration.user.*)
        self._publish_with_fallback(
            payload=payload,
            operation=operation,
            user_data=user_data,
            routing_key=routing_key,
            queue_message_type=queue_message_type,
            user_id_custom=self.user_id_custom,
        )

        # 2. CRM user.topic exchange (C36 / C37)
        self._publish_to_crm(operation, user_data)

    def _publish_user_deleted(self, user_id_custom, email=''):
        if not user_id_custom:
            return

        # 1. Interne integration-service queue (integration.user.deleted)
        payload = self._build_user_deleted_payload(user_id_custom)
        self._publish_with_fallback(
            payload=payload,
            operation='deleted',
            user_data={'userId': user_id_custom},
            routing_key='integration.user.deleted',
            queue_message_type='UserDeleted',
            user_id_custom=user_id_custom,
        )

        # 2. CRM user.topic exchange (C38 — UserDeactivated)
        if email:
            try:
                from ..utils.rabbitmq_sender import send_kassa_user_deactivated
                sent = send_kassa_user_deactivated(user_id_custom, email)
                if not sent:
                    _logger.warning(
                        "C38 UserDeactivated niet verzonden naar CRM [user_id=%s]",
                        user_id_custom,
                    )
            except Exception as exc:
                _logger.warning(
                    "C38 UserDeactivated: fout bij publiceren naar CRM [user_id=%s error=%s]",
                    user_id_custom, str(exc),
                )
        else:
            _logger.warning(
                "C38 UserDeactivated: email ontbreekt, bericht niet verzonden naar CRM [user_id=%s]",
                user_id_custom,
            )

    def _publish_with_fallback(self, payload, operation, user_data, routing_key, queue_message_type, user_id_custom):
        try:
            from ..utils.rabbitmq_sender import send_user_created, send_user_updated, send_user_deleted

            if operation == 'created':
                sent = send_user_created(user_data)
            elif operation == 'updated':
                sent = send_user_updated(user_data)
            else:
                sent = send_user_deleted(user_data.get('userId', ''))

            if not sent:
                raise RuntimeError('RabbitMQ sender returned False')

            _logger.info(
                "User event published [routing_key=%s user_id=%s]",
                routing_key,
                user_id_custom,
            )

        except Exception as exc:
            _logger.warning(
                "Failed to publish user event, queueing locally [routing_key=%s user_id=%s error=%s]",
                routing_key,
                user_id_custom,
                str(exc),
            )
            self._enqueue_user_message(user_id_custom, queue_message_type, payload, str(exc))

    def _publish_to_crm(self, operation, user_data):
        """
        Publiceer een user CRUD event naar CRM via user.topic exchange.

        operation='created' → C36 KassaUserCreated  (routing key: kassa.user.created)
        operation='updated' → C37 KassaUserUpdated   (routing key: kassa.user.updated)
        """
        self.ensure_one()
        try:
            from ..utils.rabbitmq_sender import send_kassa_user_created, send_kassa_user_updated

            if operation == 'created':
                sent = send_kassa_user_created(user_data)
            else:
                sent = send_kassa_user_updated(user_data)

            if not sent:
                _logger.warning(
                    "CRM user event niet verzonden [operation=%s user_id=%s]",
                    operation, self.user_id_custom,
                )
        except Exception as exc:
            _logger.warning(
                "CRM user event: fout bij publiceren [operation=%s user_id=%s error=%s]",
                operation, self.user_id_custom, str(exc),
            )

    def _enqueue_user_message(self, user_id_custom, message_type, payload, error_message=''):
        try:
            self.env['user.message.queue'].sudo().create({
                'user_id_custom': user_id_custom,
                'message_type': message_type,
                'payload': payload,
                'status': 'pending',
                'retry_count': 0,
                'last_error': error_message,
            })
        except Exception as queue_exc:
            _logger.error(
                "Failed to enqueue user event [user_id=%s type=%s error=%s]",
                user_id_custom,
                message_type,
                str(queue_exc),
            )

    def _build_user_data_dict(self):
        self.ensure_one()

        first_name, last_name = self._split_name(self.name or '')
        return {
            'userId': self.user_id_custom,
            'firstName': first_name,
            'lastName': last_name,
            'email': self.email or '',
            'badgeCode': self.badge_code or f'USER_{self.id}',
            'role': self._map_odoo_role_to_contract(self.role),
            'companyId': self.company_id_custom or None,
            'createdAt': self._to_iso(self.create_date),
            'updatedAt': self._to_iso(self.write_date),
        }

    @staticmethod
    def _build_user_created_payload_xml(user_data):
        """Bouw <UserCreated> XML conform kassa-schema-v1.xsd."""
        root = ET.Element('UserCreated')
        ET.SubElement(root, 'userId').text = str(user_data.get('userId', ''))
        ET.SubElement(root, 'firstName').text = str(user_data.get('firstName', ''))
        ET.SubElement(root, 'lastName').text = str(user_data.get('lastName', ''))
        ET.SubElement(root, 'email').text = str(user_data.get('email', ''))

        company_id = user_data.get('companyId')
        if company_id:
            ET.SubElement(root, 'companyId').text = str(company_id)

        ET.SubElement(root, 'badgeCode').text = str(user_data.get('badgeCode', ''))
        ET.SubElement(root, 'role').text = str(user_data.get('role', ''))
        ET.SubElement(root, 'createdAt').text = str(
            user_data.get('createdAt') or datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')
        )

        return ET.tostring(root, encoding='unicode')

    @staticmethod
    def _build_user_updated_payload_xml(user_data):
        """Bouw <UserUpdatedIntegration> XML conform kassa-schema-v1.xsd."""
        root = ET.Element('UserUpdatedIntegration')
        ET.SubElement(root, 'userId').text = str(user_data.get('userId', ''))
        ET.SubElement(root, 'firstName').text = str(user_data.get('firstName', ''))
        ET.SubElement(root, 'lastName').text = str(user_data.get('lastName', ''))
        ET.SubElement(root, 'email').text = str(user_data.get('email', ''))

        company_id = user_data.get('companyId')
        if company_id:
            ET.SubElement(root, 'companyId').text = str(company_id)

        ET.SubElement(root, 'badgeCode').text = str(user_data.get('badgeCode', ''))
        ET.SubElement(root, 'role').text = str(user_data.get('role', ''))
        ET.SubElement(root, 'updatedAt').text = str(
            user_data.get('updatedAt') or datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')
        )

        return ET.tostring(root, encoding='unicode')

    @staticmethod
    def _build_user_deleted_payload(user_id_custom):
        root = ET.Element('UserDeleted')
        ET.SubElement(root, 'userId').text = str(user_id_custom)
        ET.SubElement(root, 'deletedAt').text = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')
        return ET.tostring(root, encoding='unicode')

    @staticmethod
    def _split_name(full_name):
        full_name = (full_name or '').strip()
        if not full_name:
            return '', ''
        if ' ' not in full_name:
            return full_name, ''
        parts = full_name.split(' ', 1)
        return parts[0], parts[1]

    @staticmethod
    def _map_odoo_role_to_contract(role):
        role_map = {
            'Customer': 'VISITOR',
            'Cashier': 'CASHIER',
            'Admin': 'ADMIN',
        }
        return role_map.get(role, 'VISITOR')

    @staticmethod
    def _to_iso(dt_value):
        if not dt_value:
            return None
        if isinstance(dt_value, datetime):
            return dt_value.strftime('%Y-%m-%dT%H:%M:%SZ')
        return str(dt_value)
