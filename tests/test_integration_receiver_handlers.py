import types
import sys
from unittest.mock import MagicMock

import importlib
import pytest

# Prepare stubs and aliases so src.receiver imports cleanly
sys.modules.setdefault("settings", types.ModuleType("settings"))
sys.modules.setdefault("xml_validator", importlib.import_module("src.xml_validator"))

# Import receiver with minimal stubs
messaging_mod = types.ModuleType("messaging")
uc_mod = types.ModuleType("messaging.user_consumer")
ci_mod = types.ModuleType("messaging.check_in_consumer")
uc_mod.UserConsumer = type("_StubUserConsumer", (), {"process_user_message": lambda self, xml: True})
ci_mod.CheckInConsumer = type("_StubCheckInConsumer", (), {"process": lambda self, xml: True})
sys.modules.setdefault("messaging", messaging_mod)
sys.modules.setdefault("messaging.user_consumer", uc_mod)
sys.modules.setdefault("messaging.check_in_consumer", ci_mod)

# stub odoo_integration modules referenced by receiver
odoo_mod = types.ModuleType("odoo_integration")
odoo_conn_mod = types.ModuleType("odoo_integration.odoo_connection")
odoo_repo_mod = types.ModuleType("odoo_integration.user_repository")
odoo_conn_mod.OdooConnection = type("_StubOdooConn", (), {"is_connected": lambda self: True, "connect": lambda self: True})
odoo_repo_mod.OdooUserRepository = type("_StubRepo", (), {})
sys.modules.setdefault("odoo_integration", odoo_mod)
sys.modules.setdefault("odoo_integration.odoo_connection", odoo_conn_mod)
sys.modules.setdefault("odoo_integration.user_repository", odoo_repo_mod)

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


def test_on_person_lookup_response_logs_info(caplog):
    caplog.set_level('INFO')
    receiver.validate_xml = lambda s: (True, None)
    body = b"<PersonLookupResponse><requestId>r1</requestId><found>true</found><linkedToCompany>false</linkedToCompany></PersonLookupResponse>"
    msg = DummyMessage(body)
    import asyncio
    asyncio.get_event_loop().run_until_complete(receiver.on_person_lookup_response(msg))
    assert 'PersonLookupResponse' in caplog.text


def test_on_check_in_handles_missing_consumer(caplog):
    caplog.set_level('ERROR')
    receiver._check_in_consumer = None
    body = b"<CheckIn><userId>u1</userId></CheckIn>"
    msg = DummyMessage(body)
    import asyncio
    asyncio.get_event_loop().run_until_complete(receiver.on_check_in(msg))
    assert 'CheckInConsumer not initialized' in caplog.text


def test_on_check_in_calls_consumer(caplog):
    caplog.set_level('INFO')
    fake = MagicMock()
    fake.process = MagicMock()
    receiver._check_in_consumer = fake
    body = b"<CheckIn><userId>u2</userId></CheckIn>"
    msg = DummyMessage(body)
    import asyncio
    asyncio.get_event_loop().run_until_complete(receiver.on_check_in(msg))
    fake.process.assert_called()


def test_on_unpaid_response_counts_persons(caplog):
    caplog.set_level('INFO')
    receiver.validate_xml = lambda s: (True, None)
    body = b"<UnpaidResponse><requestId>r2</requestId><persons><person/><person/></persons></UnpaidResponse>"
    msg = DummyMessage(body)
    import asyncio
    asyncio.get_event_loop().run_until_complete(receiver.on_unpaid_response(msg))
    assert '2 personen' in caplog.text
