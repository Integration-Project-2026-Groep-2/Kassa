# -*- coding: utf-8 -*-
"""
Unit tests for CRM user message consumption.

These tests exercise the real XML-to-UserStore path used by the contact.topic
consumer so regressions in queue handling are easier to spot.
"""

import unittest
from unittest.mock import Mock

from messaging.user_consumer import UserConsumer
from odoo.user_repository import OdooUserRepository
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

USER_DEACTIVATED_XML = """<?xml version="1.0" encoding="UTF-8"?>
<UserDeactivated>
    <id>8a9b2a3e-6d1f-4b58-8c20-2f5f3f5c4d11</id>
    <email>company.contact@gmail.com</email>
    <deactivatedAt>2026-03-28T11:30:00+00:00</deactivatedAt>
</UserDeactivated>"""


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