# -*- coding: utf-8 -*-
"""
Unit tests for CRM user message consumption.

These tests exercise the real XML-to-UserStore path used by the contact.topic
consumer so regressions in queue handling are easier to spot.
"""

import unittest
from unittest.mock import Mock

from messaging.user_consumer import UserConsumer
from odoo_integration.user_repository import OdooUserRepository
from models.user import User


USER_CONFIRMED_XML = """<?xml version="1.0" encoding="UTF-8"?>
<UserConfirmed>
    <id>8a9b2a3e-6d1f-4b58-8c20-2f5f3f5c4d11</id>
    <email>company.contact@gmail.com</email>
    <firstName>Emma</firstName>
    <lastName>Janssens</lastName>
    <phone>+32471234567</phone>
    <role>COMPANY_CONTACT</role>
    <companyId>9a33a76e-2c43-407b-8eee-48d141b2de80</companyId>
    <badgeCode>BADGE-00123</badgeCode>
    <isActive>true</isActive>
    <gdprConsent>true</gdprConsent>
    <confirmedAt>2026-03-28T10:15:30+00:00</confirmedAt>
</UserConfirmed>"""


USER_UPDATED_XML = """<?xml version="1.0" encoding="UTF-8"?>
<UserUpdated>
    <id>8a9b2a3e-6d1f-4b58-8c20-2f5f3f5c4d11</id>
    <email>company.contact@gmail.com</email>
    <firstName>New</firstName>
    <lastName>Updated</lastName>
    <phone>+32471234567</phone>
    <role>COMPANY_CONTACT</role>
    <companyId>9a33a76e-2c43-407b-8eee-48d141b2de80</companyId>
    <badgeCode>BADGE-00123</badgeCode>
    <isActive>true</isActive>
    <gdprConsent>true</gdprConsent>
    <updatedAt>2026-03-28T10:15:30+00:00</updatedAt>
</UserUpdated>"""

USER_UPDATED_INVALID_ID_XML = """<?xml version="1.0" encoding="UTF-8"?>
<UserUpdated>
    <id>81</id>
    <email>company.contact@gmail.com</email>
    <firstName>New</firstName>
    <lastName>Updated</lastName>
    <phone>+32471234567</phone>
    <role>COMPANY_CONTACT</role>
    <companyId>9a33a76e-2c43-407b-8eee-48d141b2de80</companyId>
    <badgeCode>BADGE-00123</badgeCode>
    <isActive>true</isActive>
    <gdprConsent>true</gdprConsent>
    <updatedAt>2026-03-28T10:15:30+00:00</updatedAt>
</UserUpdated>"""

USER_DEACTIVATED_XML = """<?xml version="1.0" encoding="UTF-8"?>
<UserDeactivated>
    <id>8a9b2a3e-6d1f-4b58-8c20-2f5f3f5c4d11</id>
    <email>company.contact@gmail.com</email>
    <deactivatedAt>2026-03-28T11:30:00+00:00</deactivatedAt>
</UserDeactivated>"""


class DummyOdooConnection:
    def __init__(self, existing_ids=None):
        self.existing_ids = existing_ids or []
        self.created_values = None
        self.written_values = None

    def is_connected(self):
        return True

    def search(self, model, domain, **kwargs):
        return list(self.existing_ids)

    def create(self, model, values):
        self.created_values = values
        return 42

    def read(self, model, ids, fields=None):
        source_values = self.written_values or self.created_values
        if source_values is None:
            return []

        return [{
            'id': 42,
            'name': source_values.get('name'),
            'email': source_values.get('email'),
            'active': source_values.get('active', True),
            'customer_rank': source_values.get('customer_rank', 1),
            'is_company': source_values.get('is_company', False),
            'company_id': source_values.get('company_id', False),
            'user_id_custom': source_values.get('user_id_custom'),
            'badge_code': source_values.get('badge_code'),
        }]

    def write(self, model, ids, values, **kwargs):
        self.written_values = values
        return True


class TestUserConsumer(unittest.TestCase):
    def setUp(self):
        # Mock OdooUserRepository
        self.mock_odoo_repo = Mock(spec=OdooUserRepository)
        self.mock_odoo_repo.create_user = Mock(return_value=1)  # Return partner ID
        self.mock_odoo_repo.update_user = Mock(return_value=True)
        self.mock_odoo_repo.deactivate_user = Mock(return_value=True)
        
        self.consumer = UserConsumer(self.mock_odoo_repo)

    def test_process_user_confirmed_message_creates_user(self):
        """Test that UserConfirmed message calls create_user on OdooUserRepository."""
        success = self.consumer.process_user_message(USER_CONFIRMED_XML)

        self.assertTrue(success)
        # Verify that create_user was called once
        self.mock_odoo_repo.create_user.assert_called_once()
        
        # Verify the User object passed to create_user has correct data
        called_user = self.mock_odoo_repo.create_user.call_args[0][0]
        self.assertIsInstance(called_user, User)
        self.assertEqual(called_user.userId, "8a9b2a3e-6d1f-4b58-8c20-2f5f3f5c4d11")
        self.assertEqual(called_user.firstName, "Emma")
        self.assertEqual(called_user.lastName, "Janssens")
        self.assertEqual(called_user.badgeCode, "BADGE-00123")
        self.assertEqual(called_user.role, "COMPANY_CONTACT")
        self.assertEqual(called_user.companyId, "9a33a76e-2c43-407b-8eee-48d141b2de80")

    def test_process_user_updated_message_calls_create_user(self):
        """Test that UserUpdated message calls create_user on OdooUserRepository (idempotent)."""
        success = self.consumer.process_user_message(USER_UPDATED_XML)

        self.assertTrue(success)
        # Verify that create_user was called (repository handles create_or_update)
        self.mock_odoo_repo.create_user.assert_called_once()
        
        # Verify the User object has updated fields
        called_user = self.mock_odoo_repo.create_user.call_args[0][0]
        self.assertEqual(called_user.firstName, "New")
        self.assertEqual(called_user.lastName, "Updated")

    def test_process_user_updated_message_rejects_non_uuid_id(self):
        """Test that a numeric CRM id is rejected before persistence."""
        success = self.consumer.process_user_message(USER_UPDATED_INVALID_ID_XML)

        self.assertFalse(success)
        self.mock_odoo_repo.create_user.assert_not_called()

    def test_process_user_message_missing_critical_tags(self):
        """Test that missing required CRM fields fails cleanly and triggers on_error."""
        error_callback = Mock()
        repo = Mock(spec=OdooUserRepository)
        repo.create_user = Mock(side_effect=ValueError("Invalid user data: email must be valid: "))
        repo.update_user = Mock(return_value=True)
        repo.deactivate_user = Mock(return_value=True)
        consumer = UserConsumer(repo, on_error=error_callback)

        missing_tags_xml = """<?xml version="1.0" encoding="UTF-8"?>
<UserConfirmed>
    <id>8a9b2a3e-6d1f-4b58-8c20-2f5f3f5c4d11</id>
    <firstName>Emma</firstName>
    <lastName>Janssens</lastName>
    <badgeCode>BADGE-00123</badgeCode>
    <isActive>true</isActive>
    <gdprConsent>true</gdprConsent>
    <confirmedAt>2026-03-28T10:15:30+00:00</confirmedAt>
</UserConfirmed>"""

        success = consumer.process_user_message(missing_tags_xml)

        self.assertFalse(success)
        repo.create_user.assert_not_called()
        error_callback.assert_called_once()
        self.assertEqual(error_callback.call_args[0][0], 'User')
        self.assertIn('Element', error_callback.call_args[0][1])

    def test_idempotent_processing_of_duplicate_messages(self):
        """Test that duplicate CRM messages resolve to create once, then update once."""
        connection = DummyOdooConnection(existing_ids=[])
        repository = OdooUserRepository(connection)
        consumer = UserConsumer(repository)

        first = consumer.process_user_message(USER_CONFIRMED_XML)
        connection.existing_ids = [42]
        second = consumer.process_user_message(USER_CONFIRMED_XML)

        self.assertTrue(first)
        self.assertTrue(second)
        self.assertIsNotNone(connection.created_values)
        self.assertIsNotNone(connection.written_values)
        self.assertEqual(connection.created_values['user_id_custom'], "8a9b2a3e-6d1f-4b58-8c20-2f5f3f5c4d11")
        self.assertEqual(connection.written_values['user_id_custom'], "8a9b2a3e-6d1f-4b58-8c20-2f5f3f5c4d11")

    def test_idempotent_processing_of_duplicate_user_updated(self):
        """Test that duplicate UserUpdated messages perform update without duplication."""
        connection = DummyOdooConnection(existing_ids=[])
        repository = OdooUserRepository(connection)
        consumer = UserConsumer(repository)

        first = consumer.process_user_message(USER_UPDATED_XML)
        connection.existing_ids = [42]
        second = consumer.process_user_message(USER_UPDATED_XML)

        self.assertTrue(first)
        self.assertTrue(second)
        self.assertIsNotNone(connection.created_values)
        self.assertIsNotNone(connection.written_values)
        self.assertEqual(connection.written_values.get('user_id_custom'), "8a9b2a3e-6d1f-4b58-8c20-2f5f3f5c4d11")

    def test_idempotent_processing_of_duplicate_user_deactivated(self):
        """Test that duplicate UserDeactivated messages don't cause errors and set active=False."""
        connection = DummyOdooConnection(existing_ids=[42])
        repository = OdooUserRepository(connection)
        consumer = UserConsumer(repository)

        first = consumer.process_user_message(USER_DEACTIVATED_XML)
        second = consumer.process_user_message(USER_DEACTIVATED_XML)

        self.assertTrue(first)
        self.assertTrue(second)
        self.assertIsNotNone(connection.written_values)
        self.assertEqual(connection.written_values.get('active'), False)

    def test_process_user_deactivated_message_calls_deactivate_user(self):
        """Test that UserDeactivated message calls deactivate_user on OdooUserRepository."""
        success = self.consumer.process_user_message(USER_DEACTIVATED_XML)

        self.assertTrue(success)
        # Verify that deactivate_user was called with correct user_id
        self.mock_odoo_repo.deactivate_user.assert_called_once_with(
            "8a9b2a3e-6d1f-4b58-8c20-2f5f3f5c4d11"
        )

    def test_process_user_confirmed_error_handling(self):
        """Test that errors from create_user are handled gracefully."""
        # Simulate Odoo error
        self.mock_odoo_repo.create_user.side_effect = RuntimeError("Odoo connection failed")
        
        success = self.consumer.process_user_message(USER_CONFIRMED_XML)
        
        self.assertFalse(success)

    def test_process_user_deactivated_error_handling(self):
        """Test that errors from deactivate_user are handled gracefully."""
        # Simulate Odoo error
        self.mock_odoo_repo.deactivate_user.side_effect = RuntimeError("User not found in Odoo")
        
        success = self.consumer.process_user_message(USER_DEACTIVATED_XML)
        
        self.assertFalse(success)

    def test_error_callback_invoked_on_failure(self):
        """Test that on_error callback is invoked when processing fails."""
        error_callback = Mock()
        consumer = UserConsumer(self.mock_odoo_repo, on_error=error_callback)
        
        # Simulate error
        self.mock_odoo_repo.create_user.side_effect = RuntimeError("Test error")
        
        success = consumer.process_user_message(USER_CONFIRMED_XML)
        
        self.assertFalse(success)
        error_callback.assert_called_once()


if __name__ == "__main__":
    unittest.main()