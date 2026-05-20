import types

def test_rabbit_manager_connect_failure(monkeypatch):
    import src.connection as conn

    class FakeBlocking:
        def __init__(self, *args, **kwargs):
            raise RuntimeError('no rabbit')

    monkeypatch.setattr('pika.BlockingConnection', FakeBlocking)
    mgr = conn.RabbitManager(host='doesnotexist')
    try:
        mgr.connect(max_retries=1)
        assert False, 'connect should have raised'
    except Exception as e:
        assert 'no rabbit' in str(e)


def test_rabbit_manager_connect_success(monkeypatch):
    import src.connection as conn

    class FakeConn:
        def __init__(self, *args, **kwargs):
            pass
        def channel(self):
            return 'chan'
        def close(self):
            pass

    monkeypatch.setattr('pika.BlockingConnection', lambda *a, **k: FakeConn())
    mgr = conn.RabbitManager(host='ok')
    mgr.connect(max_retries=1)
    assert mgr.channel == 'chan'
    mgr.close()
