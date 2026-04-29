# -*- coding: utf-8 -*-
"""
Unit tests for User CRUD operations.

Tests cover:
- User model validation
- CRUD operations (Create, Read, Update, Delete)
- Edge cases (user not found, invalid data, duplicate badge codes)
- XML parsing and serialization
"""

import unittest
import uuid
import xml.etree.ElementTree as ET
from src.models.user import User, UserStore, UserRole
from src.messaging.message_builders import build_user_xml, parse_user_xml


class TestUserModel(unittest.TestCase):
    """Tests for the User model class."""

    def test_user_creation_with_all_fields(self):
        """Test creating a user with all fields specified."""
        user_id = str(uuid.uuid4())
        user = User(
            userId=user_id,
            firstName="John",
            lastName="Doe",
            email="john@example.com",
            badgeCode="QR12345",
            role="CASHIER",
            companyId=str(uuid.uuid4())
        )
        
        self.assertEqual(user.userId, user_id)
        self.assertEqual(user.firstName, "John")
        self.assertEqual(user.email, "john@example.com")
        self.assertIsNotNone(user.createdAt)

    def test_user_auto_generates_uuid_if_missing(self):
        """Test that userId is auto-generated if not provided."""
        user = User(
            userId="",
            firstName="Jane",
            lastName="Smith",
            email="jane@example.com",
            badgeCode="QR67890",
            role="VISITOR"
        )
        
        self.assertIsNotNone(user.userId)
        # Verify it's a valid UUID
        self.assertEqual(len(user.userId), 36)  # UUID v4 length

    def test_user_validation_success(self):
        """Test successful user validation."""
        user = User(
            userId=str(uuid.uuid4()),
            firstName="Alice",
            lastName="Brown",
            email="alice@example.com",
            badgeCode="QR99999",
            role="ADMIN"
        )
        
        valid, error = user.validate()
        self.assertTrue(valid)
        self.assertIsNone(error)

    def test_user_validation_missing_required_fields(self):
        """Test validation failure with missing required fields."""
        user = User(
            userId="",
            firstName="",
            lastName="Test",
            email="test@example.com",
            badgeCode="QR111",
            role="VISITOR"
        )
        
        valid, error = user.validate()
        self.assertFalse(valid)
        self.assertIsNotNone(error)

    def test_user_validation_invalid_email(self):
        """Test validation failure with invalid email."""
        user = User(
            userId=str(uuid.uuid4()),
            firstName="Bob",
            lastName="Jones",
            email="invalid-email",  # Invalid
            badgeCode="QR222",
            role="VISITOR"
        )
        
        valid, error = user.validate()
        self.assertFalse(valid)
        self.assertIn("email", error.lower())

    def test_user_validation_invalid_role(self):
        """Test validation failure with invalid role."""
        user = User(
            userId=str(uuid.uuid4()),
            firstName="Charlie",
            lastName="Davis",
            email="charlie@example.com",
            badgeCode="QR333",
            role="INVALID_ROLE"
        )
        
        valid, error = user.validate()
        self.assertFalse(valid)
        self.assertIn("role", error.lower())

    def test_user_validation_invalid_uuid(self):
        """Test validation failure with invalid UUID format."""
        user = User(
            userId="not-a-uuid",
            firstName="Eve",
            lastName="Evans",
            email="eve@example.com",
            badgeCode="QR444",
            role="VISITOR"
        )
        
        valid, error = user.validate()
        self.assertFalse(valid)
        self.assertIn("userid", error.lower())

    def test_user_to_xml_dict(self):
        """Test converting user to XML dictionary."""
        user_id = str(uuid.uuid4())
        company_id = str(uuid.uuid4())
        user = User(
            userId=user_id,
            firstName="Frank",
            lastName="Ford",
            email="frank@example.com",
            badgeCode="QR555",
            role="SPEAKER",
            companyId=company_id
        )
        
        xml_dict = user.to_xml_dict()
        self.assertEqual(xml_dict['userId'], user_id)
        self.assertEqual(xml_dict['companyId'], company_id)
        self.assertEqual(xml_dict['firstName'], "Frank")


class TestUserStore(unittest.TestCase):
    """Tests for the UserStore CRUD operations."""

    def setUp(self):
        """Set up test fixtures."""
        self.store = UserStore()
        self.user_id = str(uuid.uuid4())
        self.company_id = str(uuid.uuid4())
        self.test_user = User(
            userId=self.user_id,
            firstName="Test",
            lastName="User",
            email="test@example.com",
            badgeCode="QR_TEST_001",
            role="VISITOR",
            companyId=self.company_id
        )

    def tearDown(self):
        """Clean up after tests."""
        self.store.clear_all()

    # ─────────────── CREATE TESTS ───────────────

    def test_create_user_success(self):
        """Test successful user creation."""
        success, error, user = self.store.create_user(self.test_user)
        
        self.assertTrue(success)
        self.assertIsNone(error)
        self.assertIsNotNone(user)
        self.assertEqual(user.userId, self.user_id)

    def test_create_user_duplicate_user_id(self):
        """Test creation fails with duplicate userId."""
        self.store.create_user(self.test_user)
        
        # Try to create another user with same ID
        duplicate = User(
            userId=self.user_id,
            firstName="Duplicate",
            lastName="User",
            email="duplicate@example.com",
            badgeCode="QR_DUP_001",
            role="VISITOR"
        )
        
        success, error, user = self.store.create_user(duplicate)
        self.assertFalse(success)
        self.assertIsNotNone(error)
        self.assertIn("already exists", error)

    def test_create_user_duplicate_badge_code(self):
        """Test creation fails with duplicate badgeCode."""
        self.store.create_user(self.test_user)
        
        # Try to create another user with same badge code
        duplicate_badge = User(
            userId=str(uuid.uuid4()),
            firstName="Another",
            lastName="User",
            email="another@example.com",
            badgeCode="QR_TEST_001",  # Same as test_user
            role="VISITOR"
        )
        
        success, error, user = self.store.create_user(duplicate_badge)
        self.assertFalse(success)
        self.assertIn("badgeCode", error)

    def test_create_user_invalid_data(self):
        """Test creation fails with invalid user data."""
        invalid_user = User(
            userId=str(uuid.uuid4()),
            firstName="",  # Empty
            lastName="User",
            email="invalid",  # Invalid email
            badgeCode="QR_INV",
            role="VISITOR"
        )
        
        success, error, user = self.store.create_user(invalid_user)
        self.assertFalse(success)
        self.assertIsNotNone(error)

    # ─────────────── READ TESTS ───────────────

    def test_get_user_by_id_success(self):
        """Test retrieving user by ID."""
        self.store.create_user(self.test_user)
        
        found_user = self.store.get_user_by_id(self.user_id)
        self.assertIsNotNone(found_user)
        self.assertEqual(found_user.email, "test@example.com")

    def test_get_user_by_id_not_found(self):
        """Test retrieving non-existent user by ID."""
        found_user = self.store.get_user_by_id(str(uuid.uuid4()))
        self.assertIsNone(found_user)

    def test_get_user_by_badge_success(self):
        """Test retrieving user by badge code."""
        self.store.create_user(self.test_user)
        
        found_user = self.store.get_user_by_badge("QR_TEST_001")
        self.assertIsNotNone(found_user)
        self.assertEqual(found_user.userId, self.user_id)

    def test_get_user_by_badge_not_found(self):
        """Test retrieving user with non-existent badge code."""
        found_user = self.store.get_user_by_badge("QR_NONEXISTENT")
        self.assertIsNone(found_user)

    def test_get_user_by_email_success(self):
        """Test retrieving user by email."""
        self.store.create_user(self.test_user)
        
        found_user = self.store.get_user_by_email("test@example.com")
        self.assertIsNotNone(found_user)
        self.assertEqual(found_user.userId, self.user_id)

    def test_get_all_users(self):
        """Test retrieving all users."""
        user1 = self.test_user
        user2 = User(
            userId=str(uuid.uuid4()),
            firstName="Second",
            lastName="User",
            email="second@example.com",
            badgeCode="QR_TEST_002",
            role="CASHIER"
        )
        
        self.store.create_user(user1)
        self.store.create_user(user2)
        
        all_users = self.store.get_all_users()
        self.assertEqual(len(all_users), 2)

    # ─────────────── UPDATE TESTS ───────────────

    def test_update_user_success(self):
        """Test successful user update."""
        self.store.create_user(self.test_user)
        
        updates = {
            'firstName': 'Updated',
            'email': 'updated@example.com'
        }
        
        success, error, user = self.store.update_user(self.user_id, updates)
        self.assertTrue(success)
        self.assertIsNone(error)
        self.assertEqual(user.firstName, 'Updated')
        self.assertEqual(user.email, 'updated@example.com')

    def test_update_user_not_found(self):
        """Test update fails for non-existent user."""
        nonexistent_id = str(uuid.uuid4())
        
        success, error, user = self.store.update_user(nonexistent_id, {'firstName': 'Test'})
        self.assertFalse(success)
        self.assertIn("not found", error)

    def test_update_user_badge_code(self):
        """Test updating badge code."""
        self.store.create_user(self.test_user)
        
        success, error, user = self.store.update_user(self.user_id, {'badgeCode': 'QR_NEW'})
        self.assertTrue(success)
        self.assertEqual(user.badgeCode, 'QR_NEW')
        
        # Old badge should not be found
        found = self.store.get_user_by_badge("QR_TEST_001")
        self.assertIsNone(found)
        
        # New badge should be found
        found = self.store.get_user_by_badge('QR_NEW')
        self.assertIsNotNone(found)

    def test_update_user_duplicate_badge_code(self):
        """Test update fails with duplicate badge code."""
        user1 = self.test_user
        user2 = User(
            userId=str(uuid.uuid4()),
            firstName="Second",
            lastName="User",
            email="second@example.com",
            badgeCode="QR_TEST_002",
            role="VISITOR"
        )
        
        self.store.create_user(user1)
        self.store.create_user(user2)
        
        # Try to change user2's badge to user1's
        success, error, user = self.store.update_user(user2.userId, {'badgeCode': "QR_TEST_001"})
        self.assertFalse(success)
        self.assertIn("already in use", error)

    # ─────────────── DELETE TESTS ───────────────

    def test_delete_user_success(self):
        """Test successful user deletion."""
        self.store.create_user(self.test_user)
        
        success, error = self.store.delete_user(self.user_id)
        self.assertTrue(success)
        self.assertIsNone(error)
        
        # Verify user is gone
        found = self.store.get_user_by_id(self.user_id)
        self.assertIsNone(found)

    def test_delete_user_not_found(self):
        """Test deletion fails for non-existent user."""
        nonexistent_id = str(uuid.uuid4())
        
        success, error = self.store.delete_user(nonexistent_id)
        self.assertFalse(success)
        self.assertIn("not found", error)

    def test_delete_user_removes_badge_index(self):
        """Test that deletion also removes badge code index."""
        self.store.create_user(self.test_user)
        
        # Verify badge can be found
        found = self.store.get_user_by_badge("QR_TEST_001")
        self.assertIsNotNone(found)
        
        # Delete user
        self.store.delete_user(self.user_id)
        
        # Verify badge is no longer found
        found = self.store.get_user_by_badge("QR_TEST_001")
        self.assertIsNone(found)

    # ─────────────── UTILITY TESTS ───────────────

    def test_user_count(self):
        """Test getting user count."""
        self.assertEqual(self.store.get_user_count(), 0)
        
        self.store.create_user(self.test_user)
        self.assertEqual(self.store.get_user_count(), 1)

    def test_clear_all(self):
        """Test clearing all users."""
        self.store.create_user(self.test_user)
        self.assertEqual(self.store.get_user_count(), 1)
        
        self.store.clear_all()
        self.assertEqual(self.store.get_user_count(), 0)


class TestUserXMLBuilders(unittest.TestCase):
    """Tests for XML message builders."""

    def test_build_user_xml(self):
        """Test building User XML message."""
        user_id = str(uuid.uuid4())
        user_data = {
            'userId': user_id,
            'firstName': 'Alice',
            'lastName': 'Wonder',
            'email': 'alice@example.com',
            'badgeCode': 'QR_ALICE',
            'role': 'VISITOR'
        }
        
        xml = build_user_xml(user_data)
        root = ET.fromstring(xml)
        
        self.assertEqual(root.tag, 'User')
        self.assertEqual(root.findtext('userId'), user_id)
        self.assertEqual(root.findtext('firstName'), 'Alice')
        self.assertEqual(root.findtext('email'), 'alice@example.com')

    def test_parse_user_xml_success(self):
        """Test parsing valid User XML."""
        xml = """<User>
            <userId>550e8400-e29b-41d4-a716-446655440000</userId>
            <firstName>Shemsedine</firstName>
            <lastName>Boughaleb</lastName>
            <email>shems@example.com</email>
            <companyId>9c21f4e1-8b2e-4d71-a7a2-6f8cbbf81c10</companyId>
            <badgeCode>QR784512</badgeCode>
            <role>VISITOR</role>
        </User>"""
        
        success, error, user_data = parse_user_xml(xml)
        self.assertTrue(success)
        self.assertIsNone(error)
        self.assertIsNotNone(user_data)
        self.assertEqual(user_data['firstName'], 'Shemsedine')
        self.assertEqual(user_data['email'], 'shems@example.com')

    def test_parse_user_xml_invalid(self):
        """Test parsing invalid XML."""
        invalid_xml = "<User><userId>invalid xml</User>"
        
        success, error, user_data = parse_user_xml(invalid_xml)
        self.assertFalse(success)
        self.assertIsNotNone(error)
        self.assertIsNone(user_data)

    def test_build_and_parse_roundtrip(self):
        """Test building XML and parsing it back."""
        original_data = {
            'userId': str(uuid.uuid4()),
            'firstName': 'Bob',
            'lastName': 'Smith',
            'email': 'bob@example.com',
            'badgeCode': 'QR_BOB',
            'role': 'CASHIER',
            'companyId': str(uuid.uuid4())
        }
        
        xml = build_user_xml(original_data)
        success, error, parsed_data = parse_user_xml(xml)
        
        self.assertTrue(success)
        self.assertEqual(parsed_data['userId'], original_data['userId'])
        self.assertEqual(parsed_data['firstName'], original_data['firstName'])
        self.assertEqual(parsed_data['companyId'], original_data['companyId'])


if __name__ == '__main__':
    unittest.main()
