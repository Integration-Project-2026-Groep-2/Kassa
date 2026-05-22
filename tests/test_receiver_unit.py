from lxml import etree
import pytest

import src.receiver as receiver


def test_parse_and_validate_rejects_bad_utf8(monkeypatch):
    bad_bytes = b"\xff\xff\xff"
    res = receiver._parse_and_validate(bad_bytes, 'Test')
    assert res is None


def test_parse_and_validate_rejects_invalid_xml(monkeypatch):
    # make receiver's imported validate_xml return False
    monkeypatch.setattr(receiver, 'validate_xml', lambda s: (False, 'bad xml'))
    ok = receiver._parse_and_validate(b"<root></root>", 'Test')
    assert ok is None
