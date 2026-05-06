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

    balance = fields.Float(
        string='Saldo (€)',
        default=0.0,
        digits=(10, 2),
        help='Huidig saldo van de klant in euro'
    )

    @api.model_create_multi
    def create(self, vals_list):
        _logger.warning(
            "res.partner create called [records=%d]",
            len(vals_list),
        )

        records = super().create(vals_list)
        for record in records:
            _logger.warning(
                "Publishing created user event [partner_id=%s user_id_custom=%s]",
                record.id,
                record.user_id_custom,
            )
            record._publish_user_change('created')
        return records

    def write(self, vals):
        # Extract and remove CRM sync marker before processing
        # This prevents CRM-originated updates from triggering republish
        skip_publish = bool(self.env.context.get('crm_sync_skip_publish'))
        skip_publish = vals.pop('__crm_sync_skip_publish__', None) == 'true' or skip_publish
        vals.pop('crm_sync_skip_publish', None)
        
        watched_fields = {
            'name', 'email', 'phone', 'badge_code', 'role', 'company_id_custom',
        }

        previous_values = {}
        if not skip_publish and watched_fields.intersection(vals.keys()):
            for record in self:
                previous_values[record.id] = {
                    field_name: record[field_name]
                    for field_name in watched_fields
                }

        result = super().write(vals)

        if not skip_publish and watched_fields.intersection(vals.keys()):
            for record in self:
                # KassaUserUpdated must only be published after CRM confirms and
                # stores the canonical UUID in user_id_custom.
                if not record.user_id_custom:
                    _logger.info(
                        "Skipping update publish because user_id_custom is missing [partner_id=%s vals=%s]",
                        record.id,
                        sorted(vals.keys()),
                    )
                    continue

                before_values = previous_values.get(record.id, {})
                changed = False
                for field_name in watched_fields:
                    if field_name in vals and before_values.get(field_name) != record[field_name]:
                        changed = True
                        break

                if changed:
                    _logger.info(
                        "Publishing updated user event [partner_id=%s user_id_custom=%s changed_fields=%s]",
                        record.id,
                        record.user_id_custom,
                        [field_name for field_name in watched_fields if field_name in vals],
                    )
                    record._publish_user_change('updated')
                else:
                    _logger.info(
                        "Skipping update publish because watched values did not change [partner_id=%s user_id_custom=%s vals=%s]",
                        record.id,
                        record.user_id_custom,
                        sorted(vals.keys()),
                    )
        elif skip_publish:
            # CRM-originated sync detected - log for traceability but DO NOT publish
            for record in self:
                _logger.info(
                    "Skipping user republish for CRM-originated sync [partner_id=%s user_id_custom=%s changed_fields=%s]",
                    record.id,
                    record.user_id_custom,
                    [f for f in vals.keys() if f in watched_fields],
                )

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
            _logger.info(
                "Publishing deactivated user event [user_id_custom=%s email=%s]",
                candidate['user_id_custom'],
                candidate['email'],
            )
            self._publish_user_deleted(candidate['user_id_custom'], candidate['email'])

        return result

    def _publish_user_change(self, operation):
        self.ensure_one()

        if operation not in ('created', 'updated'):
            return

        user_data = self._build_user_data_dict()
        publish_identity = str(self.id) if operation == 'created' else self.user_id_custom
        if operation == 'created':
            # Contract 36 now uses local Odoo partner id for created events only.
            user_data['userId'] = self.id

        self._publish_with_fallback(
            operation=operation,
            user_data=user_data,
            user_id_custom=publish_identity,
        )

    def _publish_user_deleted(self, user_id_custom, email=''):
        if not user_id_custom:
            _logger.info("Skipping user deactivated publish because user_id_custom is missing")
            return

        self._publish_deactivated_with_fallback(
            user_email=email,
            user_id_custom=user_id_custom,
        )

    def _publish_with_fallback(self, operation, user_data, user_id_custom):
        try:
            from ..utils.rabbitmq_sender import send_user_created, send_user_updated

            if operation == 'created':
                _logger.info(
                    "Creating KassaUserCreated payload [partner_id=%s publish_identity=%s]",
                    self.id,
                    user_id_custom,
                )
                sent = send_user_created(user_data)
            elif operation == 'updated':
                _logger.info(
                    "Creating KassaUserUpdated payload [partner_id=%s user_id_custom=%s]",
                    self.id,
                    user_id_custom,
                )
                sent = send_user_updated(user_data)
            else:
                return

            if not sent:
                raise RuntimeError('RabbitMQ sender returned False')

            _logger.warning(
                "User event published [operation=%s user_id_custom=%s]",
                operation,
                user_id_custom,
            )

        except Exception as exc:
            _logger.warning(
                "Failed to publish user event, queueing locally [operation=%s user_id_custom=%s error=%s]",
                operation,
                user_id_custom,
                str(exc),
            )
            queue_message_type = 'UserCreated' if operation == 'created' else 'UserUpdated'
            payload = self._build_user_created_payload_xml(user_data) if operation == 'created' else self._build_user_updated_payload_xml(user_data)
            self._enqueue_user_message(user_id_custom, queue_message_type, payload, str(exc))

    def _publish_deactivated_with_fallback(self, user_email, user_id_custom):
        try:
            from ..utils.rabbitmq_sender import send_user_deactivated

            sent = send_user_deactivated(user_email, user_id_custom)

            if not sent:
                raise RuntimeError('RabbitMQ sender returned False')

            _logger.info(
                "User deactivated event published [user_id_custom=%s]",
                user_id_custom,
            )

        except Exception as exc:
            _logger.exception(
                "Failed to publish user deactivated event, queueing locally [user_id_custom=%s error=%s]",
                user_id_custom,
                str(exc),
            )
            payload = self._build_user_deactivated_payload(user_id_custom, user_email)
            self._enqueue_user_message(user_id_custom, 'UserDeactivated', payload, str(exc))

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
    def _build_user_deactivated_payload(user_id_custom, email=''):
        # Match Contract 38 payload shape for retry queue as well.
        root = ET.Element('UserDeactivated')
        ET.SubElement(root, 'id').text = str(user_id_custom)
        ET.SubElement(root, 'email').text = str(email or '')
        ET.SubElement(root, 'deactivatedAt').text = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')
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
