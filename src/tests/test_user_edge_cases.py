# -*- coding: utf-8 -*-
"""Additional unittest coverage for user validation, Odoo compliance, consumer
robustness, and Kassa contract invariants.
"""

import os
import sys
import unittest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from models.user import User
from messaging.user_consumer import UserConsumer
from odoo_integration.odoo_connection import OdooConnection
from odoo_integration.user_repository import OdooUserRepository
from xml_validator import validate_kassa


VALID_USER_ID = '550e8400-e29b-41d4-a716-446655440000'
VALID_COMPANY_ID = '550e8400-e29b-41d4-a716-446655440001'
VALID_USER_CONFIRM_XML = """<?xml version="1.0" encoding="UTF-8"?>
<UserConfirmed>
    <id>550e8400-e29b-41d4-a716-446655440000</id>
    <email>company.contact@gmail.com</email>
    <firstName>Emma</firstName>
    <lastName>Janssens</lastName>
    <phone>+32471234567</phone>
    <role>COMPANY_CONTACT</role>
    <companyId>550e8400-e29b-41d4-a716-446655440001</companyId>
    <badgeCode>BADGE-00123</badgeCode>
    <isActive>true</isActive>
    <gdprConsent>true</gdprConsent>
    <confirmedAt>2026-03-28T10:15:30+00:00</confirmedAt>
</UserConfirmed>"""


def _build_user(**overrides):
    payload = {
        'userId': VALID_USER_ID,
        'firstName': 'Emma',
        'lastName': 'Janssens',
        'email': 'emma@example.com',
        'badgeCode': 'BADGE-00123',
        'role': 'COMPANY_CONTACT',
        'companyId': None,
    }
    payload.update(overrides)
    return User(**payload)


def _visible_partner_record(user, partner_id=42):
    return {
        'id': partner_id,
        'name': f'{user.firstName} {user.lastName}',
        'email': user.email,
        'active': True,
        'customer_rank': 1,
        'is_company': False,
        'company_id': False,
        'user_id_custom': user.userId,
        'badge_code': user.badgeCode,
    }


class TestUserModelEdgeCases(unittest.TestCase):
    def test_user_validation_name_exactly_80_characters(self):
        first_name = 'A' * 80
        last_name = 'B' * 80

        user = _build_user(firstName=first_name, lastName=last_name)
        valid, error = user.validate()

        self.assertTrue(valid)
        self.assertIsNone(error)

    def test_user_validation_name_exceeds_80_characters(self):
        first_name = 'A' * 81
        last_name = 'B' * 81

        with self.subTest(field='firstName'):
            user = _build_user(firstName=first_name)
            valid, error = user.validate()
            self.assertFalse(valid)
            self.assertIsNotNone(error)
            self.assertIn('firstname', error.lower())

        with self.subTest(field='lastName'):
            user = _build_user(lastName=last_name)
            valid, error = user.validate()
            self.assertFalse(valid)
            self.assertIsNotNone(error)
            self.assertIn('lastname', error.lower())

    def test_user_validation_empty_badge_code(self):
        with self.subTest(badge_code=''):
            user = _build_user(badgeCode='')
            valid, error = user.validate()
            self.assertFalse(valid)
            self.assertIsNotNone(error)
            self.assertIn('badgecode', error.lower())

        with self.subTest(badge_code='whitespace'):
            user = _build_user(badgeCode='   ')
            valid, error = user.validate()
            self.assertFalse(valid)
            self.assertIsNotNone(error)
            self.assertIn('badgecode', error.lower())

    def test_user_timestamp_is_utc_iso8601(self):
        user = _build_user()

        for field_name in ('createdAt', 'updatedAt'):
            value = getattr(user, field_name)
            self.assertIsInstance(value, str)
            self.assertRegex(value, r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|\+00:00)$')

            parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
            self.assertIsNotNone(parsed.tzinfo)
            self.assertEqual(parsed.utcoffset(), timedelta(0))


class TestOdooUserRepositoryCompliance(unittest.TestCase):
    def setUp(self):
        self.user = _build_user()
        self.company_linked_user = _build_user(companyId=VALID_COMPANY_ID)

    def _build_connection(self):
        connection = Mock(spec=OdooConnection)
        connection.is_connected.return_value = True
        connection.search.return_value = []
        connection.create.return_value = 42
        connection.read.return_value = [_visible_partner_record(self.user)]
        connection.write.return_value = True
        return connection

    def test_create_user_forces_global_company_visibility(self):
        connection = self._build_connection()
        repository = OdooUserRepository(connection)

        partner_id = repository.create_user(self.user)

        self.assertEqual(partner_id, 42)
        self.assertTrue(connection.create.called)
        created_values = connection.create.call_args[0][1]
        self.assertIs(created_values['company_id'], False)
        self.assertFalse(created_values['is_company'])
        self.assertEqual(created_values['customer_rank'], 1)

    def test_deactivate_user_does_not_hard_delete(self):
        connection = Mock(spec=OdooConnection)
        connection.is_connected.return_value = True
        connection.search.return_value = [99]
        connection.write.return_value = True

        repository = OdooUserRepository(connection)
        result = repository.deactivate_user(self.user.userId)

        self.assertTrue(result)
        connection.write.assert_called_once_with('res.partner', [99], {'active': False})
        connection.unlink.assert_not_called()

    def test_create_user_with_optional_company_link(self):
        connection = self._build_connection()
        repository = OdooUserRepository(connection)

        repository.create_user(self.company_linked_user)

        created_values = connection.create.call_args[0][1]
        self.assertEqual(created_values['company_id_custom'], VALID_COMPANY_ID)
        self.assertEqual(created_values['user_id_custom'], VALID_USER_ID)


class TestUserConsumerRobustness(unittest.TestCase):
    def setUp(self):
        self.error_callback = Mock()

    def test_process_user_message_malformed_xml_returns_false(self):
        repo = Mock(spec=OdooUserRepository)
        repo.create_user = Mock(return_value=1)
        repo.update_user = Mock(return_value=True)
        repo.deactivate_user = Mock(return_value=True)
        consumer = UserConsumer(repo, on_error=self.error_callback)

        malformed_xml = '<UserConfirmed><id>550e8400-e29b-41d4-a716-446655440000</id>'

        with patch('messaging.user_consumer.validate_xml', return_value=(True, None)):
            success = consumer.process_user_message(malformed_xml)

        self.assertFalse(success)
        self.error_callback.assert_called_once()
        self.assertEqual(self.error_callback.call_args[0][0], 'User')
        self.assertIn('Failed to parse user message XML', self.error_callback.call_args[0][1])

    def test_process_user_message_missing_critical_tags(self):
        connection = Mock(spec=OdooConnection)
        connection.is_connected.return_value = True
        repository = OdooUserRepository(connection)
        consumer = UserConsumer(repository, on_error=self.error_callback)

        missing_tags_xml = """<?xml version="1.0" encoding="UTF-8"?>
<UserConfirmed>
    <id>550e8400-e29b-41d4-a716-446655440000</id>
    <firstName>Emma</firstName>
    <lastName>Janssens</lastName>
    <companyId>550e8400-e29b-41d4-a716-446655440001</companyId>
    <badgeCode>BADGE-00123</badgeCode>
    <isActive>true</isActive>
    <gdprConsent>true</gdprConsent>
    <confirmedAt>2026-03-28T10:15:30+00:00</confirmedAt>
</UserConfirmed>"""

        with patch('messaging.user_consumer.validate_xml', return_value=(True, None)):
            success = consumer.process_user_message(missing_tags_xml)

        self.assertFalse(success)
        self.error_callback.assert_called_once()
        self.assertEqual(self.error_callback.call_args[0][0], 'UserConfirmed')
        connection.search.assert_not_called()

    def test_idempotent_processing_of_duplicate_messages(self):
        connection = Mock(spec=OdooConnection)
        connection.is_connected.return_value = True
        connection.search.side_effect = [[], [42], [42]]
        connection.create.return_value = 42
        connection.read.return_value = [_visible_partner_record(_build_user(), partner_id=42)]
        connection.write.return_value = True

        repository = OdooUserRepository(connection)
        consumer = UserConsumer(repository, on_error=self.error_callback)

        with patch('messaging.user_consumer.validate_xml', return_value=(True, None)):
            first = consumer.process_user_message(VALID_USER_CONFIRM_XML)
            second = consumer.process_user_message(VALID_USER_CONFIRM_XML)

        self.assertTrue(first)
        self.assertTrue(second)
        connection.create.assert_called_once()
        connection.write.assert_called_once()
        self.error_callback.assert_not_called()


class TestKassaContractInvariants(unittest.TestCase):
    def test_contract_c38_strict_root_id_tag(self):
        valid_xml = """<UserDeactivated>
    <id>550e8400-e29b-41d4-a716-446655440000</id>
    <email>jan@example.com</email>
    <deactivatedAt>2026-04-18T10:00:00Z</deactivatedAt>
</UserDeactivated>"""

        invalid_xml = """<UserDeactivated>
    <userId>550e8400-e29b-41d4-a716-446655440000</userId>
    <email>jan@example.com</email>
    <deactivatedAt>2026-04-18T10:00:00Z</deactivatedAt>
</UserDeactivated>"""

        valid, error = validate_kassa(valid_xml)
        self.assertTrue(valid)
        self.assertIsNone(error)

        valid, error = validate_kassa(invalid_xml)
        self.assertFalse(valid)
        self.assertIsNotNone(error)

    def test_contract_c36_numeric_id_validation(self):
        numeric_id_xml = """<KassaUserCreated>
    <userId>81</userId>
    <firstName>Jan</firstName>
    <lastName>Peeters</lastName>
    <email>jan@example.com</email>
    <badgeCode>BADGE001</badgeCode>
    <role>VISITOR</role>
    <createdAt>2026-04-18T10:00:00Z</createdAt>
</KassaUserCreated>"""

        uuid_id_xml = """<KassaUserCreated>
    <userId>550e8400-e29b-41d4-a716-446655440000</userId>
    <firstName>Jan</firstName>
    <lastName>Peeters</lastName>
    <email>jan@example.com</email>
    <badgeCode>BADGE001</badgeCode>
    <role>VISITOR</role>
    <createdAt>2026-04-18T10:00:00Z</createdAt>
</KassaUserCreated>"""

        valid, error = validate_kassa(numeric_id_xml)
        self.assertTrue(valid)
        self.assertIsNone(error)

        valid, error = validate_kassa(uuid_id_xml)
        self.assertFalse(valid)
        self.assertIsNotNone(error)


if __name__ == '__main__':
    unittest.main()