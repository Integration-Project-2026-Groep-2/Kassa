from unittest.mock import MagicMock
import pytest

from messaging.producer import KassaProducer


def test_connect_calls_manager_connect():
    prod = KassaProducer(host="example")
    fake_mgr = MagicMock()
    prod._manager = fake_mgr

    prod.connect(max_retries=1)

    fake_mgr.connect.assert_called_once_with(max_retries=1)


def test_close_calls_manager_close():
    prod = KassaProducer(host="example")
    fake_mgr = MagicMock()
    prod._manager = fake_mgr

    prod.close()

    fake_mgr.close.assert_called_once()


def test_publish_raises_on_basic_publish_error():
    prod = KassaProducer(host="example")
    class F:
        def __init__(self):
            self.channel = MagicMock()
    fake_mgr = F()
    # make basic_publish raise
    fake_mgr.channel.basic_publish.side_effect = RuntimeError("publish failed")
    prod._manager = fake_mgr

    with pytest.raises(RuntimeError):
        prod.publish("payload", routing_key="r.k", queue_name="q", declare_queue=False)


def test_publish_declares_exchange_and_queue_when_exchange_set():
    prod = KassaProducer(host="example")
    class F:
        def __init__(self):
            self.channel = MagicMock()
    fake_mgr = F()
    prod._manager = fake_mgr

    prod.publish("p", routing_key="rk", exchange="ex", queue_name="q", declare_queue=True)

    fake_mgr.channel.exchange_declare.assert_called_once()
    fake_mgr.channel.queue_declare.assert_called_once()
    fake_mgr.channel.queue_bind.assert_called_once()
    fake_mgr.channel.basic_publish.assert_called_once()
