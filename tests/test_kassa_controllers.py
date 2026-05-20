import types


def _setup_request_env(monkeypatch, env_map):
    import types as _t
    req = _t.SimpleNamespace(env=env_map)
    monkeypatch.setattr('odoo.http.request', req)
    # controllers often import `request` at module import time; patch those references too
    monkeypatch.setattr('kassa_pos.controllers.pos_order_controller.request', req, raising=False)
    monkeypatch.setattr('kassa_pos.controllers.health_controller.http.request', req, raising=False)


def test_get_gks_vat_breakdown_missing_order(monkeypatch):
    from kassa_pos.controllers.pos_order_controller import KassaPosOrderController

    _setup_request_env(monkeypatch, {})
    ctrl = KassaPosOrderController()
    res = ctrl.get_gks_vat_breakdown(order_id=None)
    assert res['ok'] is False and res['error'] == 'missing_order_id'


def test_get_vsc_code_order_not_found(monkeypatch):
    from kassa_pos.controllers.pos_order_controller import KassaPosOrderController

    class FakeModel:
        def sudo(self):
            return self
        def browse(self, _id):
            return None

    _setup_request_env(monkeypatch, {'pos.order': FakeModel()})
    ctrl = KassaPosOrderController()
    res = ctrl.get_vsc_code(order_id=123)
    assert res['ok'] is False and res['error'] == 'order_not_found'


def test_health_endpoint():
    from kassa_pos.controllers.health_controller import HealthController
    ctrl = HealthController()
    resp = ctrl.health()
    assert hasattr(resp, 'body') and 'ok' in str(resp.body)
