import sys
import types
from xml.etree import ElementTree as ET

import pytest


# Ensure xml_validator is importable as top-level for build_user_xml checks
xml_mod = types.ModuleType("xml_validator")
def _valid(xml):
    return True, None
xml_mod.validate_xml = _valid
sys.modules.setdefault("xml_validator", xml_mod)

import importlib
# Make top-level `messaging` package available during tests
sys.modules.setdefault("messaging", importlib.import_module("src.messaging"))
from messaging.message_builders import (
    build_heartbeat_xml,
    build_payment_confirmed_xml,
    build_user_xml,
    parse_user_xml,
)


def test_build_heartbeat_xml_contains_service_and_timestamp():
    xml = build_heartbeat_xml()
    root = ET.fromstring(xml)
    assert root.findtext('serviceId') == 'KASSA'
    assert root.find('timestamp') is not None


def test_build_payment_confirmed_xml_fields():
    data = {'email': 'a@b', 'amount': '12.34', 'paidAt': '2026-05-20T12:00:00Z'}
    xml = build_payment_confirmed_xml(data)
    root = ET.fromstring(xml)
    assert root.findtext('email') == 'a@b'
    assert root.findtext('amount') == '12.34'
    assert root.findtext('currency') == 'EUR'


def test_parse_user_xml_success_and_failure():
    good = '<User><userId>u1</userId><firstName>A</firstName><lastName>B</lastName><email>x@y</email><badgeCode>BC</badgeCode><role>VISITOR</role></User>'
    ok, err, data = parse_user_xml(good)
    assert ok is True and data['userId'] == 'u1'

    bad = '<User><firstName></User>'
    ok, err, data = parse_user_xml(bad)
    assert ok is False and data is None


def test_build_user_xml_raises_when_validation_fails(monkeypatch):
    # make validate_xml return invalid
    xml_mod.validate_xml = lambda s: (False, 'schemerror')
    with pytest.raises(ValueError):
        build_user_xml({'userId':'u1','firstName':'A','lastName':'B','email':'x@y','badgeCode':'BC','role':'VISITOR'})
