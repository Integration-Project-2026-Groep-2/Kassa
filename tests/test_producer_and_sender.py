import types
import asyncio
import pytest


def test_kassa_producer_publish_and_declare(monkeypatch):
    from src.messaging import producer as prod

    # fake channel that records calls
    class FakeChannel:
        def __init__(self):
            self.calls = []

        def exchange_declare(self, **kwargs):
            self.calls.append(('exchange_declare', kwargs))

        def queue_declare(self, queue, durable=True):
            self.calls.append(('queue_declare', queue, durable))

        def queue_bind(self, queue, exchange, routing_key):
            self.calls.append(('queue_bind', queue, exchange, routing_key))

        def basic_publish(self, exchange, routing_key, body):
            self.calls.append(('basic_publish', exchange, routing_key, body))

    fake_chan = FakeChannel()

    class FakeMgr:
        def __init__(self):
            self.channel = fake_chan

        def connect(self, max_retries=None):
            return None

        def close(self):
            self.closed = True

    # patch RabbitManager used by KassaProducer
    monkeypatch.setattr(prod, 'RabbitManager', lambda **k: FakeMgr())

    p = prod.KassaProducer(host='x')
    p.connect(max_retries=1)
    # publish with exchange
    p.publish('PAYLOAD', routing_key='rk', exchange='ex1', queue_name='q1', durable=False)
    assert ('exchange_declare',) == tuple([fake_chan.calls[0][0]])
    assert ('queue_declare', 'q1', False) in fake_chan.calls
    p.close()


@pytest.mark.asyncio
async def test_publish_async_success_and_failure(monkeypatch):
    import src.sender as sender

    class FakeExchange:
        async def publish(self, msg, routing_key=None):
            return True

    class FakeChannel:
        def __init__(self):
            self.default_exchange = FakeExchange()

        async def declare_queue(self, name, durable=True):
            return True

    class FakeConn:
        def __init__(self):
            self.called = False

        async def channel(self):
            return FakeChannel()

    ok = await sender._publish(FakeConn(), 'queue.test', b'<x/>', durable=True)
    assert ok is True

    class BadConn:
        async def channel(self):
            raise RuntimeError('nope')

    ok2 = await sender._publish(BadConn(), 'q', b'<x/>', durable=True)
    assert ok2 is False
