import importlib
from lxml import etree
import pytest

import src.xml_validator as xml_validator


def test_validate_xml_returns_true_when_schema_none():
    orig = xml_validator._schema
    try:
        xml_validator._schema = None
        ok, err = xml_validator.validate_xml("<dummy/>")
        assert ok is True and err is None
    finally:
        xml_validator._schema = orig


def test_validate_xml_reports_schema_validation_errors():
    class FakeSchema:
        def assertValid(self, doc):
            raise etree.DocumentInvalid("schema failed")

    orig = xml_validator._schema
    try:
        xml_validator._schema = FakeSchema()
        ok, err = xml_validator.validate_xml("<Root></Root>")
        assert ok is False
        assert "schema failed" in err
    finally:
        xml_validator._schema = orig


def test_validate_raises_value_error_for_invalid_bytes():
    class FakeSchema:
        def assertValid(self, doc):
            raise etree.DocumentInvalid("invalid bytes")

    orig = xml_validator._schema
    try:
        xml_validator._schema = FakeSchema()
        with pytest.raises(ValueError):
            xml_validator.validate(b"<Bad></Bad>")
    finally:
        xml_validator._schema = orig
