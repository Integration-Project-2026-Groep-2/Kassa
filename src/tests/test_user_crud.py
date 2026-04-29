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
from models.user import User, UserRole
from messaging.message_builders import build_user_xml, parse_user_xml
from odoo.user_repository import OdooUserRepository


class DummyOdooConnection:
    def __init__(self, existing_ids=None, read_response=None):
        self.existing_ids = existing_ids or []
        self.created_values = None
        self.written_values = None
        # Optional explicit read response to simulate Odoo read() results
        self.read_response = read_response

    def is_connected(self):
        return True

    def search(self, model, domain, **kwargs):
        return list(self.existing_ids)

    def create(self, model, values):
        self.created_values = values
        return 42

    def read(self, model, ids, fields=None):
        # If an explicit read_response is provided, return it (wrapped in a list)
        if self.read_response is not None:
            return [self.read_response]

        # Use written_values if available (from update), otherwise use created_values
        source_values = self.written_values or self.created_values
        if source_values is None:
            return []

        record = {
            'id': 42,
            'name': source_values.get('name'),
            'email': source_values.get('email'),
            'active': source_values.get('active', True),
            'customer_rank': source_values.get('customer_rank', 1),
            'is_company': source_values.get('is_company', False),
            'company_id': source_values.get('company_id', 1),
            'user_id_custom': source_values.get('user_id_custom'),
            'badge_code': source_values.get('badge_code'),
        }
        return [record]

    def get_default_company_id(self):
        return 1  # Simulate default company

    def write(self, model, ids, values):
        self.written_values = values
        return True


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


class TestOdooUserRepository(unittest.TestCase):
    def setUp(self):
        self.user = User(
            userId=str(uuid.uuid4()),
            firstName='Emma',
            lastName='Janssens',
            email='emma@example.com',
            badgeCode='BADGE-00123',
            role='COMPANY_CONTACT',
            companyId=str(uuid.uuid4()),
        )

    def test_create_user_sets_customer_visibility_flags(self):
        repo = OdooUserRepository(DummyOdooConnection())

        repo.create_user(self.user)

        self.assertIsNotNone(repo.odoo.created_values)
        self.assertEqual(repo.odoo.created_values['customer_rank'], 1)
        self.assertFalse(repo.odoo.created_values['is_company'])
        self.assertEqual(repo.odoo.created_values['company_type'], 'person')

    def test_update_user_also_sets_customer_visibility_flags(self):
        repo = OdooUserRepository(DummyOdooConnection(existing_ids=[99]))

        repo.create_user(self.user)

        self.assertIsNotNone(repo.odoo.written_values)
        self.assertEqual(repo.odoo.written_values['customer_rank'], 1)
        self.assertFalse(repo.odoo.written_values['is_company'])
        self.assertEqual(repo.odoo.written_values['company_type'], 'person')

    def test_create_user_sets_company_id(self):
        """Test that create_user sets the standard Odoo company_id field."""
        repo = OdooUserRepository(DummyOdooConnection())

        repo.create_user(self.user)

        self.assertIsNotNone(repo.odoo.created_values)
        # Verify company_id is set to the default (1)
        self.assertEqual(repo.odoo.created_values.get('company_id'), 1)
        self.assertEqual(repo.odoo.created_values['customer_rank'], 1)
        self.assertFalse(repo.odoo.created_values['is_company'])

    def test_create_user_readback_visibility_check_fails(self):
        # Simulate an Odoo read() returning a partner that is not visible
        bad_read = {
            'id': 99,
            'name': 'Hidden User',
            'email': 'hidden@example.com',
            'active': False,
            'customer_rank': 0,
            'is_company': True,
            'company_id': None,  # Missing company_id = not visible
            'user_id_custom': self.user.userId,
            'badge_code': self.user.badgeCode,
        }

        repo = OdooUserRepository(DummyOdooConnection(read_response=bad_read))

        with self.assertRaises(RuntimeError):
            repo.create_user(self.user)


if __name__ == '__main__':
    unittest.main()
