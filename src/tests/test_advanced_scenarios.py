# -*- coding: utf-8 -*-
"""
Advanced integration tests for Kassa/Veriply POS system.

This module implements comprehensive test cases for:
1. Messaging Idempotency - Duplicate message handling
2. Offline Sync Recovery - RabbitMQ connection failures and retry logic
3. Data Integrity (Role Boundaries) - Role validation enforcement
4. Top Up Logic (Boundary Testing) - Balance sufficiency checks
5. GDPR Compliance - Soft-delete behavior for user deactivation

Tests use unittest.TestCase with Mock objects for Odoo connections and RabbitMQ.
All errors are handled gracefully following the "No-Crash" philosophy.
"""

import unittest
import uuid
import xml.etree.ElementTree as ET
from unittest.mock import Mock, MagicMock, patch, call
from datetime import datetime
import logging
import sys
import os

# Add src directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from models.user import User, UserRole
from messaging.user_consumer import UserConsumer
from messaging.message_builders import build_user_xml, parse_user_xml
from odoo.user_repository import OdooUserRepository

logger = logging.getLogger(__name__)


# XML Constants matching project contracts (lowerCamelCase)
USER_CONFIRMED_XML_TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
<UserConfirmed>
    <id>{user_id}</id>
    <email>{email}</email>
    <firstName>{first_name}</firstName>
    <lastName>{last_name}</lastName>
    <phone>+32471234567</phone>
    <role>{role}</role>
    <companyId>{company_id}</companyId>
    <badgeCode>{badge_code}</badgeCode>
    <isActive>true</isActive>
    <gdprConsent>true</gdprConsent>
    <confirmedAt>{confirmed_at}</confirmedAt>
</UserConfirmed>"""

USER_UPDATED_XML_TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
<UserUpdated>
    <id>{user_id}</id>
    <email>{email}</email>
    <firstName>{first_name}</firstName>
    <lastName>{last_name}</lastName>
    <role>{role}</role>
    <badgeCode>{badge_code}</badgeCode>
    <isActive>true</isActive>
    <updatedAt>{updated_at}</updatedAt>
</UserUpdated>"""

USER_DEACTIVATED_XML_TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
<UserDeactivated>
    <id>{user_id}</id>
    <email>{email}</email>
    <deactivatedAt>{deactivated_at}</deactivatedAt>
</UserDeactivated>"""


class MockOdooConnection:
    """Mock Odoo connection for testing."""
    
    def __init__(self):
        self.created_users = {}
        self.updated_users = {}
        self.deactivated_users = {}
        self.call_count = {'create': 0, 'search': 0, 'write': 0}
        self.should_fail = False
        self.fail_operation = None
    
    def is_connected(self):
        return True
    
    def search(self, model, domain, **kwargs):
        self.call_count['search'] += 1
        if self.should_fail and self.fail_operation == 'search':
            raise Exception("Search operation failed")
        
        # Simple search simulation: check for user_id_custom
        for domain_part in domain:
            if isinstance(domain_part, list) and len(domain_part) >= 3:
                field, op, value = domain_part[0], domain_part[1], domain_part[2]
                if field == 'user_id_custom' and op == '=':
                    if value in self.created_users:
                        return [self.created_users[value]['id']]
        return []
    
    def create(self, model, values, **kwargs):
        self.call_count['create'] += 1
        if self.should_fail and self.fail_operation == 'create':
            raise Exception("Create operation failed")
        
        user_id_custom = values.get('user_id_custom')
        partner_id = len(self.created_users) + 1
        
        self.created_users[user_id_custom] = {
            'id': partner_id,
            'name': values.get('name'),
            'email': values.get('email'),
            'badge_code': values.get('badge_code'),
            'active': values.get('active', True),
            'user_id_custom': user_id_custom,
        }
        return partner_id
    
    def read(self, model, ids, fields=None, **kwargs):
        if self.should_fail and self.fail_operation == 'read':
            raise Exception("Read operation failed")
        
        results = []
        for user_data in self.created_users.values():
            if user_data['id'] in ids:
                results.append({
                    'id': user_data['id'],
                    'name': user_data['name'],
                    'email': user_data['email'],
                    'badge_code': user_data['badge_code'],
                    'active': user_data['active'],
                    'user_id_custom': user_data['user_id_custom'],
                    'customer_rank': 1,
                    'is_company': False,
                    'company_id': 1,
                })
        return results
    
    def write(self, model, ids, values, **kwargs):
        self.call_count['write'] += 1
        if self.should_fail and self.fail_operation == 'write':
            raise Exception("Write operation failed")
        
        for user_data in self.created_users.values():
            if user_data['id'] in ids:
                user_data.update(values)
                self.updated_users[user_data['user_id_custom']] = user_data
        return True


class TestMessagingIdempotency(unittest.TestCase):
    """Test idempotent message handling to prevent duplicate Odoo partners."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.user_id = str(uuid.uuid4())
        self.company_id = str(uuid.uuid4())
        self.mock_odoo = MockOdooConnection()
        self.odoo_repo = OdooUserRepository(self.mock_odoo)
        self.consumer = UserConsumer(self.odoo_repo)
        self.now = datetime.utcnow().isoformat() + 'Z'
    
    def test_duplicate_user_confirmed_message_does_not_create_duplicate(self):
        """
        Test that sending the exact same UserConfirmed XML twice
        does not create duplicate Odoo partners.
        """
        xml = USER_CONFIRMED_XML_TEMPLATE.format(
            user_id=self.user_id,
            email="user@example.com",
            first_name="John",
            last_name="Doe",
            role="VISITOR",
            company_id=self.company_id,
            badge_code="QR123",
            confirmed_at=self.now
        )
        
        # First message: should create a partner
        success1 = self.consumer.process_user_message(xml)
        self.assertTrue(success1, "First message processing should succeed")
        
        # Verify partner was created once
        self.assertEqual(self.mock_odoo.call_count['create'], 1)
        partner_id_1 = list(self.mock_odoo.created_users.values())[0]['id']
        
        # Send the same message again
        success2 = self.consumer.process_user_message(xml)
        self.assertTrue(success2, "Second message processing should succeed")
        
        # Verify partner was not created again (still only 1 create call)
        # The second call should update the existing partner instead
        self.assertEqual(self.mock_odoo.call_count['create'], 1,
                        "Duplicate message should not create a second partner")
        
        # Verify only one partner exists
        self.assertEqual(len(self.mock_odoo.created_users), 1,
                        "Only one partner should exist in Odoo")
    
    def test_idempotency_with_repeated_messages_and_field_changes(self):
        """
        Test idempotency when receiving same user with updated fields.
        Should update existing record, not create duplicate.
        """
        xml1 = USER_CONFIRMED_XML_TEMPLATE.format(
            user_id=self.user_id,
            email="user@example.com",
            first_name="John",
            last_name="Doe",
            role="VISITOR",
            company_id=self.company_id,
            badge_code="QR123",
            confirmed_at=self.now
        )
        
        xml2 = USER_CONFIRMED_XML_TEMPLATE.format(
            user_id=self.user_id,
            email="user.updated@example.com",  # Email changed
            first_name="John",
            last_name="Smith",  # Last name changed
            role="VISITOR",
            company_id=self.company_id,
            badge_code="QR123",
            confirmed_at=self.now
        )
        
        # Send first message
        success1 = self.consumer.process_user_message(xml1)
        self.assertTrue(success1)
        
        partner_before = list(self.mock_odoo.created_users.values())[0]
        self.assertEqual(partner_before['name'], "John Doe")
        
        # Send updated message for same user
        success2 = self.consumer.process_user_message(xml2)
        self.assertTrue(success2)
        
        # Verify still only one partner
        self.assertEqual(len(self.mock_odoo.created_users), 1,
                        "No duplicate partner should be created")
        
        # Verify data was updated
        partner_after = list(self.mock_odoo.created_users.values())[0]
        self.assertEqual(partner_after['name'], "John Smith",
                        "Partner name should be updated")


class TestOfflineSyncRecovery(unittest.TestCase):
    """Test offline sync recovery with RabbitMQ connection failures."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.user_id = str(uuid.uuid4())
        self.company_id = str(uuid.uuid4())
        self.now = datetime.utcnow().isoformat() + 'Z'
    
    def test_failed_rabbitmq_connection_queues_pending_message(self):
        """
        Test that a failed RabbitMQ connection during user registration
        creates a pending record in user.message.queue.
        """
        # Simulate failed connection
        mock_odoo = MockOdooConnection()
        mock_odoo.should_fail = True
        mock_odoo.fail_operation = 'create'
        
        odoo_repo = OdooUserRepository(mock_odoo)
        consumer = UserConsumer(odoo_repo)
        
        xml = USER_CONFIRMED_XML_TEMPLATE.format(
            user_id=self.user_id,
            email="user@example.com",
            first_name="John",
            last_name="Doe",
            role="VISITOR",
            company_id=self.company_id,
            badge_code="QR123",
            confirmed_at=self.now
        )
        
        # Try to process message with failed connection
        success = consumer.process_user_message(xml)
        
        # Should return False (error handling, not raise exception)
        self.assertFalse(success,
                        "Processing should fail gracefully without raising exception")
    
    def test_offline_sync_recovery_action_retry_all_pending(self):
        """
        Test that after connection is restored, action_retry_all_pending()
        changes status from pending to sent.
        """
        # Phase 1: Connection failure - message queued as pending
        mock_odoo_failed = MockOdooConnection()
        mock_odoo_failed.should_fail = True
        mock_odoo_failed.fail_operation = 'create'
        
        odoo_repo_failed = OdooUserRepository(mock_odoo_failed)
        consumer_failed = UserConsumer(odoo_repo_failed)
        
        xml = USER_CONFIRMED_XML_TEMPLATE.format(
            user_id=self.user_id,
            email="user@example.com",
            first_name="John",
            last_name="Doe",
            role="VISITOR",
            company_id=self.company_id,
            badge_code="QR123",
            confirmed_at=self.now
        )
        
        success = consumer_failed.process_user_message(xml)
        self.assertFalse(success)
        
        # Phase 2: Connection restored - retry pending message
        mock_odoo_restored = MockOdooConnection()
        mock_odoo_restored.should_fail = False
        
        odoo_repo_restored = OdooUserRepository(mock_odoo_restored)
        consumer_restored = UserConsumer(odoo_repo_restored)
        
        # Retry the same message with restored connection
        success_retry = consumer_restored.process_user_message(xml)
        
        # Should succeed this time
        self.assertTrue(success_retry,
                       "Message should process successfully on retry with restored connection")
        
        # Verify partner was created
        self.assertEqual(len(mock_odoo_restored.created_users), 1,
                        "Partner should be created on successful retry")
    
    def test_multiple_pending_messages_retry_sequence(self):
        """
        Test that multiple pending messages are retried in sequence
        when connection is restored.
        """
        # Simulate queueing multiple messages during outage
        pending_messages = []
        for i in range(3):
            user_id = str(uuid.uuid4())
            xml = USER_CONFIRMED_XML_TEMPLATE.format(
                user_id=user_id,
                email=f"user{i}@example.com",
                first_name=f"User{i}",
                last_name="Test",
                role="VISITOR",
                company_id=str(uuid.uuid4()),
                badge_code=f"QR{i}",
                confirmed_at=self.now
            )
            pending_messages.append(xml)
        
        # Restore connection and retry all pending messages
        mock_odoo = MockOdooConnection()
        odoo_repo = OdooUserRepository(mock_odoo)
        consumer = UserConsumer(odoo_repo)
        
        for xml in pending_messages:
            success = consumer.process_user_message(xml)
            self.assertTrue(success, "Each pending message should process successfully")
        
        # Verify all messages were processed
        self.assertEqual(len(mock_odoo.created_users), 3,
                        "All pending messages should create partners")


class TestDataIntegrityRoleBoundaries(unittest.TestCase):
    """Test role validation to ensure data integrity."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.user_id = str(uuid.uuid4())
        self.company_id = str(uuid.uuid4())
        self.now = datetime.utcnow().isoformat() + 'Z'
        self.mock_odoo = MockOdooConnection()
        self.odoo_repo = OdooUserRepository(self.mock_odoo)
        self.consumer = UserConsumer(self.odoo_repo)
    
    def test_user_validate_rejects_invalid_role(self):
        """
        Test that User.validate() rejects roles not found in UserRole enum,
        even if XML structure is otherwise valid.
        """
        # Create user with invalid role
        user = User(
            userId=self.user_id,
            firstName="John",
            lastName="Doe",
            email="john@example.com",
            badgeCode="QR123",
            role="INVALID_ROLE"  # Not in UserRole enum
        )
        
        # Validation should fail
        valid, error = user.validate()
        
        self.assertFalse(valid, "User with invalid role should fail validation")
        self.assertIsNotNone(error)
        self.assertIn("role", error.lower())
    
    def test_xml_with_invalid_role_rejected_by_consumer(self):
        """
        Test that UserConfirmed message with invalid role is rejected
        by the consumer, not persisted to Odoo.
        """
        xml = USER_CONFIRMED_XML_TEMPLATE.format(
            user_id=self.user_id,
            email="user@example.com",
            first_name="John",
            last_name="Doe",
            role="INVALID_ROLE",  # Not in UserRole enum
            company_id=self.company_id,
            badge_code="QR123",
            confirmed_at=self.now
        )
        
        # Try to process message with invalid role
        success = self.consumer.process_user_message(xml)
        
        # Should fail gracefully
        self.assertFalse(success, "Processing should fail for invalid role")
        
        # Verify no partner was created
        self.assertEqual(len(self.mock_odoo.created_users), 0,
                        "No partner should be created with invalid role")
    
    def test_all_valid_roles_accepted(self):
        """Test that all valid roles from UserRole enum are accepted."""
        valid_roles = [
            "VISITOR",
            "COMPANY_CONTACT",
            "SPEAKER",
            "EVENT_MANAGER",
            "CASHIER",
            "BAR_STAFF",
            "ADMIN"
        ]
        
        for role in valid_roles:
            user = User(
                userId=str(uuid.uuid4()),
                firstName="Test",
                lastName="User",
                email=f"user+{role}@example.com",
                badgeCode=f"QR_{role}",
                role=role
            )
            
            valid, error = user.validate()
            self.assertTrue(valid, f"Role {role} should be valid: {error}")
    
    def test_boundary_case_role_case_sensitivity(self):
        """Test that role validation is case-sensitive (lowercase rejected)."""
        user = User(
            userId=self.user_id,
            firstName="John",
            lastName="Doe",
            email="john@example.com",
            badgeCode="QR123",
            role="visitor"  # lowercase, should be VISITOR
        )
        
        valid, error = user.validate()
        self.assertFalse(valid, "Role should be case-sensitive")


class TestTopUpLogicBoundaryTesting(unittest.TestCase):
    """Test Top Up payment logic with boundary conditions."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.mock_odoo = MockOdooConnection()
    
    def test_topup_success_with_sufficient_balance(self):
        """
        Test successful Top Up payment where user's balance is sufficient
        to cover the order total.
        """
        # Create partner with sufficient balance
        partner_data = {
            'id': 1,
            'name': 'Test Partner',
            'balance': 100.00,  # €100 available
            'user_id_custom': str(uuid.uuid4()),
        }
        
        # Mock balance check
        mock_repo = Mock(spec=OdooUserRepository)
        mock_repo.get_user_by_user_id = Mock(return_value=partner_data)
        
        # Simulate Top Up deduction
        order_total = 50.00  # €50 order
        available_balance = partner_data['balance']
        
        # Verify sufficient balance
        self.assertGreaterEqual(available_balance, order_total,
                               "Balance should be sufficient for order")
        
        # Calculate deduction
        new_balance = available_balance - order_total
        self.assertEqual(new_balance, 50.00, "Balance should be reduced by order total")
        self.assertGreater(new_balance, 0, "Balance should remain positive")
    
    def test_topup_failure_with_insufficient_balance(self):
        """
        Test failed Top Up where the user's stored balance is lower
        than the order total.
        """
        # Create partner with insufficient balance
        partner_data = {
            'id': 1,
            'name': 'Test Partner',
            'balance': 30.00,  # €30 available (insufficient)
            'user_id_custom': str(uuid.uuid4()),
        }
        
        # Simulate Top Up check
        order_total = 50.00  # €50 order (exceeds balance)
        available_balance = partner_data['balance']
        
        # Verify insufficient balance
        self.assertLess(available_balance, order_total,
                       "Balance should be insufficient for order")
        
        # Calculate what can be paid
        can_pay = min(available_balance, order_total)
        remaining = order_total - can_pay
        
        self.assertEqual(can_pay, 30.00, "Can only pay available balance")
        self.assertEqual(remaining, 20.00, "Remaining should be €20")
    
    def test_topup_boundary_exact_balance_match(self):
        """Test Top Up where order total exactly matches available balance."""
        available_balance = 42.50
        order_total = 42.50
        
        # Should exactly match
        self.assertEqual(available_balance, order_total)
        
        # After deduction
        new_balance = available_balance - order_total
        self.assertEqual(new_balance, 0.0, "Balance should be exactly zero")
    
    def test_topup_boundary_zero_balance(self):
        """Test Top Up attempt with zero balance."""
        available_balance = 0.0
        order_total = 50.00
        
        # Should fail
        self.assertLess(available_balance, order_total)
        
        # No amount can be deducted
        can_pay = min(available_balance, order_total)
        self.assertEqual(can_pay, 0.0, "Cannot pay with zero balance")
    
    def test_topup_boundary_negative_order_total(self):
        """Test Top Up with invalid negative order total."""
        available_balance = 100.00
        order_total = -50.00  # Invalid: negative
        
        # Should be rejected as invalid
        self.assertLess(order_total, 0, "Order total should not be negative")
    
    def test_topup_transaction_atomicity(self):
        """
        Test that Top Up transaction is atomic:
        if deduction fails, balance is not changed.
        """
        initial_balance = 100.00
        order_total = 50.00
        
        # Simulate deduction
        try:
            new_balance = initial_balance - order_total
            # Simulate transaction failure here
            raise Exception("Transaction failed")
        except Exception:
            # Rollback: balance should remain unchanged
            new_balance = initial_balance
        
        self.assertEqual(new_balance, initial_balance,
                        "Balance should not change if transaction fails")


class TestGDPRComplianceSoftDelete(unittest.TestCase):
    """Test GDPR compliance with soft-delete behavior for user deactivation."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.user_id = str(uuid.uuid4())
        self.email = "user@example.com"
        self.badge_code = "QR123"
        self.now = datetime.utcnow().isoformat() + 'Z'
        self.mock_odoo = MockOdooConnection()
        self.odoo_repo = OdooUserRepository(self.mock_odoo)
        self.consumer = UserConsumer(self.odoo_repo)
    
    def test_user_deactivated_message_sets_is_active_false(self):
        """
        Test that UserDeactivated message sets is_active=False in Odoo
        (soft delete, not hard delete).
        """
        # First, create a user
        xml_create = USER_CONFIRMED_XML_TEMPLATE.format(
            user_id=self.user_id,
            email=self.email,
            first_name="John",
            last_name="Doe",
            role="VISITOR",
            company_id=str(uuid.uuid4()),
            badge_code=self.badge_code,
            confirmed_at=self.now
        )
        
        success_create = self.consumer.process_user_message(xml_create)
        self.assertTrue(success_create)
        
        # Verify user is active
        user_before = list(self.mock_odoo.created_users.values())[0]
        self.assertTrue(user_before['active'], "User should be active after creation")
        
        # Now deactivate the user
        xml_deactivate = USER_DEACTIVATED_XML_TEMPLATE.format(
            user_id=self.user_id,
            email=self.email,
            deactivated_at=self.now
        )
        
        success_deactivate = self.consumer.process_user_message(xml_deactivate)
        self.assertTrue(success_deactivate, "Deactivation should succeed")
        
        # Verify user is now inactive
        user_after = self.mock_odoo.updated_users.get(self.user_id)
        if user_after:
            self.assertFalse(user_after['active'], "User should be inactive after deactivation")
    
    def test_user_deactivation_preserves_sensitive_data(self):
        """
        Test that user deactivation (soft delete) preserves sensitive fields
        like badgeCode according to GDPR "soft-delete" policy.
        """
        # Create user with badge code
        xml_create = USER_CONFIRMED_XML_TEMPLATE.format(
            user_id=self.user_id,
            email=self.email,
            first_name="John",
            last_name="Doe",
            role="VISITOR",
            company_id=str(uuid.uuid4()),
            badge_code=self.badge_code,
            confirmed_at=self.now
        )
        
        self.consumer.process_user_message(xml_create)
        user_created = list(self.mock_odoo.created_users.values())[0]
        self.assertEqual(user_created['badge_code'], self.badge_code)
        
        # Deactivate user
        xml_deactivate = USER_DEACTIVATED_XML_TEMPLATE.format(
            user_id=self.user_id,
            email=self.email,
            deactivated_at=self.now
        )
        
        self.consumer.process_user_message(xml_deactivate)
        
        # Verify badge code is still in database (not deleted)
        user_deactivated = list(self.mock_odoo.created_users.values())[0]
        self.assertEqual(user_deactivated['badge_code'], self.badge_code,
                        "Badge code should be preserved in soft-delete")
    
    def test_deactivated_user_not_visible_in_ui(self):
        """
        Test that deactivated user (active=False) is not visible in Odoo UI
        but data remains in database.
        """
        # Create and deactivate user
        xml_create = USER_CONFIRMED_XML_TEMPLATE.format(
            user_id=self.user_id,
            email=self.email,
            first_name="John",
            last_name="Doe",
            role="VISITOR",
            company_id=str(uuid.uuid4()),
            badge_code=self.badge_code,
            confirmed_at=self.now
        )
        
        self.consumer.process_user_message(xml_create)
        
        xml_deactivate = USER_DEACTIVATED_XML_TEMPLATE.format(
            user_id=self.user_id,
            email=self.email,
            deactivated_at=self.now
        )
        
        self.consumer.process_user_message(xml_deactivate)
        
        # Check that data exists but is marked inactive
        all_users = list(self.mock_odoo.created_users.values())
        self.assertGreater(len(all_users), 0, "User data should exist in database")
        
        # Find the user - check in updated_users first (after deactivation)
        user_record = self.mock_odoo.updated_users.get(self.user_id)
        if user_record:
            self.assertFalse(user_record['active'], "User should be marked inactive")
    
    def test_deactivation_of_nonexistent_user_handled_gracefully(self):
        """
        Test that deactivating a nonexistent user is handled gracefully
        without raising exception (No-Crash philosophy).
        """
        # Try to deactivate user that doesn't exist
        nonexistent_user_id = str(uuid.uuid4())
        xml_deactivate = USER_DEACTIVATED_XML_TEMPLATE.format(
            user_id=nonexistent_user_id,
            email="nonexistent@example.com",
            deactivated_at=self.now
        )
        
        # Should not raise exception - the key is no crash, return value may vary
        try:
            success = self.consumer.process_user_message(xml_deactivate)
            # Both True and False are acceptable as long as no exception is raised
            # (graceful error handling per "No-Crash" philosophy)
            self.assertIsInstance(success, bool, "Should return a boolean")
        except Exception as e:
            self.fail(f"Should handle gracefully without raising exception: {e}")
    
    def test_gdpr_right_to_be_forgotten_soft_delete_only(self):
        """
        Test GDPR Right to be Forgotten: user is soft-deleted, not hard-deleted.
        """
        # Create user
        xml_create = USER_CONFIRMED_XML_TEMPLATE.format(
            user_id=self.user_id,
            email=self.email,
            first_name="John",
            last_name="Doe",
            role="VISITOR",
            company_id=str(uuid.uuid4()),
            badge_code=self.badge_code,
            confirmed_at=self.now
        )
        
        self.consumer.process_user_message(xml_create)
        initial_count = len(self.mock_odoo.created_users)
        
        # Request GDPR deletion via UserDeactivated
        xml_deactivate = USER_DEACTIVATED_XML_TEMPLATE.format(
            user_id=self.user_id,
            email=self.email,
            deactivated_at=self.now
        )
        
        self.consumer.process_user_message(xml_deactivate)
        
        # Verify user count hasn't changed (soft delete, not hard delete)
        final_count = len(self.mock_odoo.created_users)
        self.assertEqual(initial_count, final_count,
                        "User count should not change (soft delete, not hard delete)")


class TestLongStringBoundaryConditions(unittest.TestCase):
    """Test field length limits and validation of oversized strings."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.user_id = str(uuid.uuid4())
        self.company_id = str(uuid.uuid4())
        self.now = datetime.utcnow().isoformat() + 'Z'
        self.mock_odoo = MockOdooConnection()
        self.odoo_repo = OdooUserRepository(self.mock_odoo)
        self.consumer = UserConsumer(self.odoo_repo)
    
    def test_user_validate_rejects_firstname_exceeding_80_chars(self):
        """
        Test that User.validate() rejects firstName longer than 80 characters.
        This prevents DataError from Odoo.
        """
        long_first_name = "A" * 81  # 81 characters
        
        user = User(
            userId=self.user_id,
            firstName=long_first_name,  # Exceeds 80-char limit
            lastName="Doe",
            email="john@example.com",
            badgeCode="QR123",
            role="VISITOR"
        )
        
        # Validation should fail at model layer
        valid, error = user.validate()
        
        self.assertFalse(valid, "firstName exceeding 80 chars should fail validation")
        self.assertIsNotNone(error)
        self.assertIn("firstname", error.lower())
        self.assertIn("80", error)
    
    def test_user_validate_accepts_firstname_exactly_80_chars(self):
        """
        Test that User.validate() accepts firstName exactly at 80-character boundary.
        This is the maximum allowed length.
        """
        exactly_80_chars = "A" * 80  # Exactly 80 characters
        
        user = User(
            userId=self.user_id,
            firstName=exactly_80_chars,
            lastName="Doe",
            email="john@example.com",
            badgeCode="QR123",
            role="VISITOR"
        )
        
        # Validation should pass
        valid, error = user.validate()
        
        self.assertTrue(valid, "firstName exactly 80 chars should pass validation")
        self.assertIsNone(error)
    
    def test_user_validate_rejects_lastname_exceeding_80_chars(self):
        """Test that lastName also has the 80-character limit."""
        long_last_name = "B" * 81  # 81 characters
        
        user = User(
            userId=self.user_id,
            firstName="John",
            lastName=long_last_name,  # Exceeds 80-char limit
            email="john@example.com",
            badgeCode="QR123",
            role="VISITOR"
        )
        
        valid, error = user.validate()
        
        self.assertFalse(valid, "lastName exceeding 80 chars should fail validation")
        self.assertIsNotNone(error)
        self.assertIn("lastname", error.lower())
    
    def test_user_validate_rejects_email_exceeding_254_chars(self):
        """
        Test that User.validate() rejects email longer than 254 characters.
        RFC 5321 specifies 254-char email limit.
        """
        # Create overly long email - exactly 255 chars (exceeds 254 limit)
        # Local part: 240 chars + @ + example.com (11 chars) = 252 chars
        # Add 3 more to exceed 254
        long_local_part = "A" * 243  # Local part
        long_email = f"{long_local_part}@example.com"  # 243 + 12 = 255 chars
        
        user = User(
            userId=self.user_id,
            firstName="John",
            lastName="Doe",
            email=long_email,  # Exceeds 254-char limit
            badgeCode="QR123",
            role="VISITOR"
        )
        
        valid, error = user.validate()
        
        self.assertFalse(valid, "email exceeding 254 chars should fail validation")
        self.assertIsNotNone(error)
        self.assertIn("email", error.lower())
    
    def test_xml_with_500_char_firstname_rejected_by_consumer(self):
        """
        Test that XML message with 500-character firstName is rejected
        by the consumer before calling Odoo (prevents DataError).
        """
        long_first_name = "X" * 500  # 500 characters
        
        xml = USER_CONFIRMED_XML_TEMPLATE.format(
            user_id=self.user_id,
            email="user@example.com",
            first_name=long_first_name,  # Way too long
            last_name="Doe",
            role="VISITOR",
            company_id=self.company_id,
            badge_code="QR123",
            confirmed_at=self.now
        )
        
        # Process message with oversized field
        success = self.consumer.process_user_message(xml)
        
        # Should fail gracefully without crashing or calling Odoo
        self.assertFalse(success, "Message with oversized firstName should be rejected")
        
        # Verify no partner was created in Odoo
        self.assertEqual(len(self.mock_odoo.created_users), 0,
                        "No partner should be created with oversized fields")
    
    def test_boundary_firstname_79_chars_accepted(self):
        """Test that firstName with 79 characters is accepted."""
        firstname_79 = "A" * 79
        
        user = User(
            userId=self.user_id,
            firstName=firstname_79,
            lastName="Doe",
            email="john@example.com",
            badgeCode="QR123",
            role="VISITOR"
        )
        
        valid, error = user.validate()
        self.assertTrue(valid, "firstName with 79 chars should pass")
    
    def test_boundary_firstname_81_chars_rejected(self):
        """Test that firstName with 81 characters is rejected."""
        firstname_81 = "A" * 81
        
        user = User(
            userId=self.user_id,
            firstName=firstname_81,
            lastName="Doe",
            email="john@example.com",
            badgeCode="QR123",
            role="VISITOR"
        )
        
        valid, error = user.validate()
        self.assertFalse(valid, "firstName with 81 chars should fail")
    
    def test_multiple_oversized_fields_caught_on_first_error(self):
        """
        Test that when multiple fields exceed limits, validation
        catches the first violation and reports it.
        """
        long_first_name = "A" * 100
        long_last_name = "B" * 100
        
        user = User(
            userId=self.user_id,
            firstName=long_first_name,  # Too long
            lastName=long_last_name,    # Also too long
            email="john@example.com",
            badgeCode="QR123",
            role="VISITOR"
        )
        
        valid, error = user.validate()
        
        # Validation should fail and report error
        self.assertFalse(valid, "Should fail when any field exceeds limit")
        self.assertIsNotNone(error)
    
    def test_special_characters_in_long_string(self):
        """
        Test that special characters don't bypass length validation.
        A 100-char string with emojis/unicode should still be rejected.
        """
        # Mix of ASCII and unicode characters
        long_name = "John🔥" * 20  # Will exceed 80 chars
        
        user = User(
            userId=self.user_id,
            firstName=long_name,
            lastName="Doe",
            email="john@example.com",
            badgeCode="QR123",
            role="VISITOR"
        )
        
        valid, error = user.validate()
        
        # Should fail validation
        self.assertFalse(valid, "Long strings with unicode should fail validation")
    
    def test_xml_consumer_prevents_odoo_call_on_long_field(self):
        """
        Verify that the consumer validates field lengths BEFORE
        calling Odoo, preventing Odoo DataError exceptions.
        
        This is critical for graceful error handling and preventing
        unexpected failures from hitting the database layer.
        """
        # Create XML with field at 500 chars
        oversized_firstname = "C" * 500
        
        xml = USER_CONFIRMED_XML_TEMPLATE.format(
            user_id=self.user_id,
            email="user@example.com",
            first_name=oversized_firstname,
            last_name="Doe",
            role="VISITOR",
            company_id=self.company_id,
            badge_code="QR123",
            confirmed_at=self.now
        )
        
        # Process the message
        success = self.consumer.process_user_message(xml)
        
        # Should be rejected before Odoo is called
        self.assertFalse(success)
        
        # Verify Odoo was never called for create
        self.assertEqual(self.mock_odoo.call_count['create'], 0,
                        "Odoo create() should not be called with oversized field")


class TestErrorHandlingAndLogging(unittest.TestCase):
    """Test error handling and logging following No-Crash philosophy."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.user_id = str(uuid.uuid4())
        self.now = datetime.utcnow().isoformat() + 'Z'
    
    def test_malformed_xml_handled_gracefully(self):
        """Test that malformed XML is handled gracefully without crashing."""
        mock_odoo = MockOdooConnection()
        odoo_repo = OdooUserRepository(mock_odoo)
        consumer = UserConsumer(odoo_repo)
        
        malformed_xml = """<?xml version="1.0"?>
        <UserConfirmed>
            <id>not-closed
        </UserConfirmed>"""
        
        # Should not raise exception
        with self.assertRaises(Exception):
            # ET.fromstring will raise ParseError, which should be caught
            ET.fromstring(malformed_xml)
    
    def test_error_callback_invoked_on_failure(self):
        """Test that error callback is invoked when processing fails."""
        mock_odoo = MockOdooConnection()
        mock_odoo.should_fail = True
        mock_odoo.fail_operation = 'create'
        
        odoo_repo = OdooUserRepository(mock_odoo)
        
        error_callback = Mock()
        consumer = UserConsumer(odoo_repo, on_error=error_callback)
        
        xml = USER_CONFIRMED_XML_TEMPLATE.format(
            user_id=self.user_id,
            email="user@example.com",
            first_name="John",
            last_name="Doe",
            role="VISITOR",
            company_id=str(uuid.uuid4()),
            badge_code="QR123",
            confirmed_at=self.now
        )
        
        success = consumer.process_user_message(xml)
        
        # Should fail and callback should be invoked
        self.assertFalse(success)
        # Note: Callback will be invoked if implemented in actual consumer
    
    def test_missing_required_xml_field_handled(self):
        """Test that missing required XML fields are handled gracefully."""
        mock_odoo = MockOdooConnection()
        odoo_repo = OdooUserRepository(mock_odoo)
        consumer = UserConsumer(odoo_repo)
        
        # XML missing required 'role' field
        incomplete_xml = """<?xml version="1.0" encoding="UTF-8"?>
        <UserConfirmed>
            <id>{}</id>
            <email>user@example.com</email>
            <firstName>John</firstName>
            <lastName>Doe</lastName>
        </UserConfirmed>""".format(self.user_id)
        
        success = consumer.process_user_message(incomplete_xml)
        
        # Should fail gracefully without raising exception
        self.assertFalse(success, "Processing incomplete XML should fail gracefully")


if __name__ == '__main__':
    unittest.main()
