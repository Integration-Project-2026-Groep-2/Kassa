import types
import sys
from unittest.mock import MagicMock

import pytest


# Stub User dataclass used in repository
models_mod = types.ModuleType("models")
user_mod = types.ModuleType("models.user")

class FakeUser:
    def __init__(self, **kwargs):
        # set known fields with defaults
        self.userId = kwargs.get('userId', '')
        self.firstName = kwargs.get('firstName', '')
        self.lastName = kwargs.get('lastName', '')
        self.email = kwargs.get('email', '')
        self.badgeCode = kwargs.get('badgeCode', '')
        self.role = kwargs.get('role', '')
        self.companyId = kwargs.get('companyId', None)
        self.createdAt = kwargs.get('createdAt', None)
        self.updatedAt = kwargs.get('updatedAt', None)

    def validate(self):
        return True, None

    @staticmethod
    def _is_valid_uuid(val):
        return True

user_mod.User = FakeUser
user_mod.UserRole = object
sys.modules.setdefault("models", models_mod)
sys.modules.setdefault("models.user", user_mod)

import importlib
sys.modules.setdefault("odoo_integration", importlib.import_module("src.odoo_integration"))


class FakeOdoo:
    def __init__(self):
        self.storage = {}
        self.next_id = 1

    def is_connected(self):
        return True

    def search(self, model, domain):
        # simple search by user_id_custom or badge_code or email
        if [['user_id_custom', '=', domain[0][2]] if isinstance(domain[0], list) else domain]:
            pass
        # naive: return empty -> simulate not found
        return []

    def create(self, model, values):
        pid = self.next_id
        self.next_id += 1
        self.storage[pid] = values.copy()
        self.storage[pid]['id'] = pid
        return pid

    def read(self, model, ids, fields):
        return [self.storage.get(ids[0], {})]

    def write(self, model, ids, values, context=None):
        pid = ids[0]
        if pid not in self.storage:
            raise Exception("not found")
        self.storage[pid].update(values)


def test_create_user_success():
    from odoo_integration.user_repository import OdooUserRepository

    fake_odoo = FakeOdoo()
    repo = OdooUserRepository(fake_odoo)

    user = FakeUser(userId='u1', firstName='A', lastName='B', email='x@y', badgeCode='BC', role='VISITOR')
    pid = repo.create_user(user)
    assert isinstance(pid, int)


def test_update_user_raises_when_not_found():
    from odoo_integration.user_repository import OdooUserRepository

    fake_odoo = FakeOdoo()
    repo = OdooUserRepository(fake_odoo)
    user = FakeUser(userId='u2', firstName='C', lastName='D', email='y@z', badgeCode='BC2', role='VISITOR')
    with pytest.raises(ValueError):
        repo.update_user(user)


def test_deactivate_user_returns_false_if_not_found():
    from odoo_integration.user_repository import OdooUserRepository

    fake_odoo = FakeOdoo()
    repo = OdooUserRepository(fake_odoo)
    assert repo.deactivate_user('nonexistent') is False
