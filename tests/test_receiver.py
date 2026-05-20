import types
import sys
import asyncio
from contextlib import asynccontextmanager
from unittest.mock import patch, MagicMock

import pytest


# Ensure receiver can import validate_xml via the module-level name
_fake_settings = types.ModuleType("settings")
_fake_settings.RABBIT_HOST = "localhost"
_fake_settings.RABBIT_PORT = 5672
_fake_settings.RABBIT_USER = "guest"
_fake_settings.RABBIT_PASSWORD = "guest"
_fake_settings.RABBIT_VHOST = "/"
sys.modules.setdefault("settings", _fake_settings)

# Ensure top-level import name `xml_validator` resolves to `src.xml_validator` used in the package
import importlib
sys.modules.setdefault("xml_validator", importlib.import_module("src.xml_validator"))

# Create lightweight stubs for top-level packages the receiver imports so we
# don't have to pull in the entire src.* dependency graph during tests.
messaging_mod = types.ModuleType("messaging")
user_consumer_mod = types.ModuleType("messaging.user_consumer")
check_in_mod = types.ModuleType("messaging.check_in_consumer")

class _FakeUserConsumer:
    def __init__(self, repo=None, on_error=None):
        pass

    def process_user_message(self, xml_string: str) -> bool:
        return True

class _FakeCheckInConsumer:
    def __init__(self, repo=None):
        pass

    def process(self, xml_string: str):
        return True

user_consumer_mod.UserConsumer = _FakeUserConsumer
check_in_mod.CheckInConsumer = _FakeCheckInConsumer
sys.modules.setdefault("messaging", messaging_mod)
sys.modules.setdefault("messaging.user_consumer", user_consumer_mod)
sys.modules.setdefault("messaging.check_in_consumer", check_in_mod)

odoo_mod = types.ModuleType("odoo_integration")
odoo_conn_mod = types.ModuleType("odoo_integration.odoo_connection")
odoo_repo_mod = types.ModuleType("odoo_integration.user_repository")

class _FakeOdooConnection:
    def __init__(self, url, db, user, password):
        pass

    def connect(self):
        return True

class _FakeOdooUserRepository:
    def __init__(self, conn):
        pass

odoo_conn_mod.OdooConnection = _FakeOdooConnection
odoo_repo_mod.OdooUserRepository = _FakeOdooUserRepository
sys.modules.setdefault("odoo_integration", odoo_mod)
sys.modules.setdefault("odoo_integration.odoo_connection", odoo_conn_mod)
sys.modules.setdefault("odoo_integration.user_repository", odoo_repo_mod)


class DummyMessage:
    def __init__(self, body: bytes):
        self.body = body

    @asynccontextmanager
    async def process(self):
        yield


def test_parse_and_validate_returns_element_on_valid():
    import src.receiver as receiver

    with patch.object(receiver, "validate_xml", return_value=(True, None)):
        elem = receiver._parse_and_validate(b"<Root><id>1</id></Root>", "contract")
        assert elem is not None
        assert elem.findtext("id") == "1"


def test_parse_and_validate_handles_invalid_xml_and_logs(caplog):
    import src.receiver as receiver

    caplog.set_level("ERROR")
    with patch.object(receiver, "validate_xml", return_value=(False, "error details")):
        elem = receiver._parse_and_validate(b"<Bad></Bad>", "contract")
        assert elem is None
        assert "ongeldig XML-bericht" in caplog.text


@pytest.mark.asyncio
async def test_on_user_confirmed_logs_when_no_consumer(caplog):
    import src.receiver as receiver

    caplog.set_level("ERROR")
    # ensure no consumer
    receiver._user_consumer = None

    with patch.object(receiver, "validate_xml", return_value=(True, None)):
        msg = DummyMessage(b"<User><id>u1</id><email>x@y</email><role>admin</role></User>")
        await receiver.on_user_confirmed(msg)
        assert "UserConsumer not initialized" in caplog.text


@pytest.mark.asyncio
async def test_on_user_confirmed_calls_consumer_and_logs_info(caplog):
    import src.receiver as receiver

    caplog.set_level("INFO")
    fake_consumer = MagicMock()
    fake_consumer.process_user_message.return_value = True
    receiver._user_consumer = fake_consumer

    with patch.object(receiver, "validate_xml", return_value=(True, None)):
        msg = DummyMessage(b"<User><id>u2</id><email>a@b</email><role>user</role></User>")
        await receiver.on_user_confirmed(msg)
        fake_consumer.process_user_message.assert_called()
        assert "UserConfirmed ontvangen" in caplog.text
