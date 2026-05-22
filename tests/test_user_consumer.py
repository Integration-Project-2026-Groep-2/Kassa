import sys
import types
from unittest.mock import MagicMock

import pytest


# Stub models.user.User and xml_validator for tests
models_mod = types.ModuleType("models")
user_mod = types.ModuleType("models.user")

class FakeUser:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)

    @staticmethod
    def _is_valid_uuid(val):
        return True

user_mod.User = FakeUser
sys.modules.setdefault("models", models_mod)
sys.modules.setdefault("models.user", user_mod)

xml_mod = types.ModuleType("xml_validator")
xml_mod.validate_xml = lambda s: (True, None)
sys.modules.setdefault("xml_validator", xml_mod)

# Stub odoo_integration.user_repository so importing messaging.user_consumer works
odoo_mod = types.ModuleType("odoo_integration")
odoo_repo_mod = types.ModuleType("odoo_integration.user_repository")
class FakeOdooRepo:
    def create_user(self, user):
        return True
    def deactivate_user(self, user_id):
        return True
odoo_repo_mod.OdooUserRepository = FakeOdooRepo
sys.modules.setdefault("odoo_integration", odoo_mod)
sys.modules.setdefault("odoo_integration.user_repository", odoo_repo_mod)


def test_process_user_message_valid_calls_odoo_and_returns_true():
    from messaging.user_consumer import UserConsumer

    fake_repo = MagicMock()
    # ensure validator returns valid for this test
    import messaging.user_consumer as uc_mod
    uc_mod.validate_xml = lambda s: (True, None)
    uc = uc_mod.UserConsumer(fake_repo)
    xml = '<User><userId>u1</userId><firstName>A</firstName><lastName>B</lastName><email>x@y</email><badgeCode>BC</badgeCode><role>VISITOR</role></User>'
    result = uc.process_user_message(xml)
    assert result is True


def test_process_user_message_invalid_triggers_on_error(monkeypatch):
    from messaging.user_consumer import UserConsumer

    fake_repo = MagicMock()
    errors = []

    def on_err(t, e):
        errors.append((t, e))

    # make validate_xml return False
    import xml_validator
    xml_validator.validate_xml = lambda s: (False, 'bad xml')

    import messaging.user_consumer as uc_mod2
    uc_mod2.validate_xml = lambda s: (False, 'bad xml')
    uc = uc_mod2.UserConsumer(fake_repo, on_error=on_err)
    xml = '<User></User>'
    result = uc.process_user_message(xml)
    assert result is False
    assert errors and errors[0][0] == 'User'
