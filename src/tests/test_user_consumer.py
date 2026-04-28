# -*- coding: utf-8 -*-
"""
Unit tests for CRM user message consumption.

These tests exercise the real XML-to-UserStore path used by the contact.topic
consumer so regressions in queue handling are easier to spot.
"""

import unittest

from messaging.user_consumer import UserConsumer
from models.user import UserStore


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


class TestUserConsumer(unittest.TestCase):
    def setUp(self):
        self.store = UserStore()
        self.consumer = UserConsumer(self.store)

    def tearDown(self):
        self.store.clear_all()

    def test_process_user_confirmed_message_creates_user(self):
        success = self.consumer.process_user_message(USER_CONFIRMED_XML)

        self.assertTrue(success)
        self.assertEqual(self.store.get_user_count(), 1)

        user = self.store.get_user_by_id("8a9b2a3e-6d1f-4b58-8c20-2f5f3f5c4d11")
        self.assertIsNotNone(user)
        self.assertEqual(user.firstName, "Emma")
        self.assertEqual(user.lastName, "Janssens")
        self.assertEqual(user.badgeCode, "BADGE-00123")
        self.assertEqual(user.role, "COMPANY_CONTACT")
        self.assertEqual(user.companyId, "9a33a76e-2c43-407b-8eee-48d141b2de80")

    def test_process_user_updated_message_replaces_snapshot(self):
        self.assertTrue(self.consumer.process_user_message(USER_CONFIRMED_XML))

        success = self.consumer.process_user_message(USER_UPDATED_XML)

        self.assertTrue(success)
        self.assertEqual(self.store.get_user_count(), 1)

        user = self.store.get_user_by_id("8a9b2a3e-6d1f-4b58-8c20-2f5f3f5c4d11")
        self.assertIsNotNone(user)
        self.assertEqual(user.firstName, "New")
        self.assertEqual(user.lastName, "Updated")
        self.assertEqual(user.badgeCode, "BADGE-00123")
        self.assertEqual(user.role, "COMPANY_CONTACT")


if __name__ == "__main__":
    unittest.main()