import pytest

from src.odoo_integration.odoo_connection import OdooConnection


def test_connect_fails_with_missing_credentials():
    oc = OdooConnection(url='http://localhost:8069', db='', user='', password='')
    assert oc.connect() is False


def test_execute_raises_if_not_connected():
    oc = OdooConnection(url='http://localhost:8069', db='db', user='u', password='p')
    assert oc.is_connected() is False
    with pytest.raises(RuntimeError):
        oc.execute('res.partner', 'read', [1])
