import sys
import types
from datetime import datetime


def _install_odoo_stub():
    if 'odoo' in sys.modules:
        return
    odoo = types.ModuleType('odoo')

    class Model:
        def __init__(self, **kwargs):
            for k, v in kwargs.items():
                setattr(self, k, v)

        def ensure_one(self):
            return None

        def write(self, vals):
            for k, v in vals.items():
                setattr(self, k, v)
            return True

    odoo.models = types.SimpleNamespace(Model=Model)

    class Fields:
        @staticmethod
        def Char(**kwargs):
            return None

        @staticmethod
        def Selection(*args, **kwargs):
            return None

        @staticmethod
        def Float(**kwargs):
            return None

    odoo.fields = Fields()

    class api:
        @staticmethod
        def model_create_multi(func):
            return func
        @staticmethod
        def depends(*args, **kwargs):
            def _decor(fn):
                return fn
            return _decor

    odoo.api = api
    odoo.SUPERUSER_ID = 1
    # Provide common submodules used by kassa_pos
    exc_mod = types.ModuleType('odoo.exceptions')
    class UserError(Exception):
        pass
    exc_mod.UserError = UserError
    odoo.exceptions = exc_mod
    sys.modules['odoo.exceptions'] = exc_mod

    sys.modules['odoo'] = odoo


def test_split_name_and_mapping_and_iso():
    _install_odoo_stub()

    from kassa_pos.models.res_partner import ResPartner

    assert ResPartner._split_name('') == ('', '')
    assert ResPartner._split_name('Alice') == ('Alice', '')
    assert ResPartner._split_name('Bob Smith') == ('Bob', 'Smith')

    assert ResPartner._map_odoo_role_to_contract('Customer') == 'VISITOR'
    assert ResPartner._map_odoo_role_to_contract('Cashier') == 'CASHIER'
    assert ResPartner._map_odoo_role_to_contract('Admin') == 'ADMIN'
    assert ResPartner._map_odoo_role_to_contract('Unknown') == 'VISITOR'

    assert ResPartner._to_iso(None) is None
    now = datetime.utcnow()
    iso = ResPartner._to_iso(now)
    assert isinstance(iso, str) and iso.endswith('Z')


def test_payload_builders_and_data_dict():
    _install_odoo_stub()
    from kassa_pos.models.res_partner import ResPartner

    # create a minimal partner instance
    p = ResPartner()
    p.id = 23
    p.name = 'Jane Doe'
    p.user_id_custom = 'uuid-1234'
    p.email = 'jane@example.com'
    p.badge_code = 'BADGE1'
    p.role = 'Customer'
    p.company_id_custom = 'comp-1'
    p.create_date = datetime.utcnow()
    p.write_date = datetime.utcnow()

    user_data = p._build_user_data_dict()
    assert user_data['firstName'] == 'Jane'
    assert user_data['lastName'] == 'Doe'
    assert 'createdAt' in user_data

    created_xml = ResPartner._build_user_created_payload_xml(user_data)
    assert '<UserCreated>' in created_xml

    updated_xml = ResPartner._build_user_updated_payload_xml(user_data)
    assert '<UserUpdatedIntegration>' in updated_xml

    deactivated = ResPartner._build_user_deactivated_payload('uuid-1234', 'a@b')
    assert '<UserDeactivated>' in deactivated
