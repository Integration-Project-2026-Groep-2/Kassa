import types
from datetime import datetime


def test_pos_session_triggers_close_daily_batch(monkeypatch):
    from kassa_pos.models.pos_session import PosSession

    called = {}

    class FakePosOrderModel:
        def close_daily_batch(self, session=None):
            called['closed'] = True
            return {'success': True, 'batch_id': 'B1', 'orders_count': 2, 'total_amount': 50.0}

        def search(self, domain):
            return [1]

    s = PosSession()
    s.name = 'S1'
    # inject fake env
    s.env = {'pos.order': FakePosOrderModel()}

    # method calls super() which our stub does not implement; assert that close_daily_batch was invoked
    try:
        s.action_pos_session_closing_control()
    except AttributeError:
        pass

    assert called.get('closed') is True


def test_pos_session_close_triggers_preclose(monkeypatch):
    from kassa_pos.models.pos_session import PosSession

    class FakePosOrderModel:
        def __init__(self):
            self.closed = False
            self.searched = False

        def close_daily_batch(self, session=None):
            self.closed = True
            return {'success': True}

        def search(self, domain):
            self.searched = True
            return [1]

    model = FakePosOrderModel()
    s = PosSession()
    s.id = 7
    s.name = 'S1'
    s.env = {'pos.order': model}

    try:
        s.action_pos_session_close()
    except AttributeError:
        pass

    assert model.searched is True


def test_pos_order_batch_create_and_state_transitions(monkeypatch):
    from kassa_pos.models.pos_order_batch import PosOrderBatch
    import odoo

    # ensure parent create uses a fake implementation so super().create works
    def fake_parent_create(self, vals):
        # emulate an Odoo record object
        return types.SimpleNamespace(**vals)

    monkeypatch.setattr(odoo.models.Model, 'create', fake_parent_create, raising=False)

    batch = PosOrderBatch().create({'total_orders': 3})
    assert hasattr(batch, 'batch_uuid')
    assert hasattr(batch, 'name')

    # now test action_mark_* on an instance of the real model class
    b = PosOrderBatch()
    b.name = 'BATCH-1'
    b.status = 'draft'
    b.retry_count = 0

    b.action_mark_sent()
    assert b.status == 'sent'

    b.action_mark_failed('boom')
    assert b.status == 'failed' and b.error_message == 'boom'

    b.retry_count = 0
    b.action_mark_retry('2026-05-20')
    assert b.status == 'retry' and b.retry_count == 1

    b.action_mark_confirmed()
    assert b.status == 'confirmed'


def test_balance_transaction_basic_fields():
    from kassa_pos.models.balance_transaction import BalanceTransaction

    t = BalanceTransaction()
    t.partner_id = 12
    t.amount = 15.5
    t.transaction_type = 'payment'
    t.payment_method = 'card'

    assert t.partner_id == 12
    assert t.amount == 15.5
    assert t.transaction_type == 'payment'
