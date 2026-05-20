import types

def _make_request_env(monkeypatch, partner):
    class ResPartnerModel:
        def __init__(self, partner):
            self._partner = partner

        def browse(self, pid):
            return self._partner if getattr(self._partner, 'id', None) == pid else types.SimpleNamespace(exists=lambda: False)

        def search(self, domain, limit=10):
            return []

    fake_env = {'res.partner': ResPartnerModel(partner), 'balance.transaction': types.SimpleNamespace(create=lambda v: None)}
    fake_request = types.SimpleNamespace(env=fake_env)
    monkeypatch.setattr('kassa_pos.controllers.balance_controller.request', fake_request)


def test_topup_deduct_get_balance(monkeypatch):
    from kassa_pos.controllers.balance_controller import BalanceController

    class Partner:
        def __init__(self):
            self.id = 3
            self.name = 'T'
            self.balance = 10.0
            self.email = 't@e'
            self.badge_code = 'B'

        def exists(self):
            return True

        def write(self, vals):
            for k, v in vals.items():
                setattr(self, k, v)

    p = Partner()
    _make_request_env(monkeypatch, p)

    bc = BalanceController()
    # topup too small
    res = bc.topup_balance(partner_id=3, amount=1.0, payment_method='cash')
    assert res['success'] is False

    # valid topup
    res = bc.topup_balance(partner_id=3, amount=5.0, payment_method='cash')
    assert res['success'] is True and p.balance >= 15.0

    # deduct more than balance
    res = bc.deduct_balance(partner_id=3, amount=100.0)
    assert res['success'] is False

    # deduct valid
    res = bc.deduct_balance(partner_id=3, amount=5.0)
    assert res['success'] is True and p.balance == round(p.balance,2)

    # get balance
    res = bc.get_balance(partner_id=3)
    assert res['success'] is True and 'balance' in res
