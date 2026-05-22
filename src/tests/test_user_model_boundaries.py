import unittest
from models.user import User


class TestUserModelBoundaries(unittest.TestCase):
    def setUp(self):
        self.valid_uuid = "550e8400-e29b-41d4-a716-446655440000"
        self.valid_email = "user@example.com"
        self.valid_role = "COMPANY_CONTACT"

    def _make_user(self, **overrides):
        data = {
            'userId': self.valid_uuid,
            'firstName': 'John',
            'lastName': 'Doe',
            'email': self.valid_email,
            'badgeCode': 'BADGE-123',
            'role': self.valid_role,
            'companyId': None,
        }
        data.update(overrides)
        return User(**data)

    def test_name_length_boundaries(self):
        # Exactly 80 characters should be valid
        name_80 = 'x' * 80
        user = self._make_user(firstName=name_80, lastName=name_80)
        ok, err = user.validate()
        self.assertTrue(ok, msg=err)

        # 81 characters should be invalid
        name_81 = 'x' * 81
        user2 = self._make_user(firstName=name_81)
        ok2, err2 = user2.validate()
        self.assertFalse(ok2)
        self.assertIn('firstName', err2)

    def test_unicode_names_allowed(self):
        unicode_name = 'Łukasz Żółć 漢字'
        user = self._make_user(firstName=unicode_name, lastName=unicode_name)
        ok, err = user.validate()
        self.assertTrue(ok, msg=err)

    def test_badgecode_whitespace_rejected(self):
        user = self._make_user(badgeCode='   ')
        ok, err = user.validate()
        self.assertFalse(ok)
        self.assertIn('badgeCode', err)


if __name__ == '__main__':
    unittest.main()
