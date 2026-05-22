import types
import sys
from unittest.mock import MagicMock

import pytest


# Create minimal stubs so we can import src.receiver and its handlers
import importlib
sys.modules.setdefault("settings", types.ModuleType("settings"))
sys.modules.setdefault("xml_validator", importlib.import_module("src.xml_validator"))

# Use the real src.receiver but replace external dependencies with fakes
# Provide lightweight stubs for messaging and odoo_integration packages so
# importing `src.receiver` does not pull the whole dependency graph.
messaging_mod = types.ModuleType("messaging")
uc_mod = types.ModuleType("messaging.user_consumer")
ci_mod = types.ModuleType("messaging.check_in_consumer")

class _StubUserConsumer:
    def __init__(self, *args, **kwargs):
        pass

    def process_user_message(self, xml):
        return True

uc_mod.UserConsumer = _StubUserConsumer
ci_mod.CheckInConsumer = type("_StubCheckIn", (), {"process": lambda self, xml: True})
sys.modules.setdefault("messaging", messaging_mod)
sys.modules.setdefault("messaging.user_consumer", uc_mod)
sys.modules.setdefault("messaging.check_in_consumer", ci_mod)

# Also stub odoo_integration.user_repository used during import
odoo_mod = types.ModuleType("odoo_integration")
odoo_repo_mod = types.ModuleType("odoo_integration.user_repository")
odoo_repo_mod.OdooUserRepository = type("_StubRepo", (), {})
sys.modules.setdefault("odoo_integration", odoo_mod)
sys.modules.setdefault("odoo_integration.user_repository", odoo_repo_mod)
# Provide od o_connection stub
odoo_conn_mod = types.ModuleType("odoo_integration.odoo_connection")
class _StubOdooConn:
    def __init__(self, url, db, user, password):
        pass
    def is_connected(self):
        return True
    def connect(self):
        return True
odoo_conn_mod.OdooConnection = _StubOdooConn
sys.modules.setdefault("odoo_integration.odoo_connection", odoo_conn_mod)

import src.receiver as receiver


class DummyMessage:
    def __init__(self, body: bytes):
        self.body = body

    def process(self):
        class Ctx:
            async def __aenter__(self):
                return None

            async def __aexit__(self, exc_type, exc, tb):
                return False

        return Ctx()


@pytest.mark.asyncio
async def test_receiver_integration_user_flow(monkeypatch, caplog):
    caplog.set_level('INFO')

    # stub validate_xml to succeed
    monkeypatch.setattr(receiver, 'validate_xml', lambda s: (True, None))

    # create fake user consumer that records calls
    fake_consumer = MagicMock()
    fake_consumer.process_user_message.return_value = True
    receiver._user_consumer = fake_consumer

    msg = DummyMessage(b"<User><id>u1</id><email>a@b</email><role>VISITOR</role></User>")
    await receiver.on_user_confirmed(msg)

    fake_consumer.process_user_message.assert_called()
    assert 'UserConfirmed ontvangen' in caplog.text
