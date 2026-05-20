import sys
import types
from unittest.mock import MagicMock

import importlib


# Provide a stub 'connection' module with RabbitManager used by messaging.producer
conn_mod = types.ModuleType("connection")

class FakeManager:
    def __init__(self):
        self.channel = MagicMock()

    def connect(self, max_retries=None):
        return None

    def close(self):
        return None

conn_mod.RabbitManager = FakeManager
sys.modules.setdefault("connection", conn_mod)

# Ensure top-level messaging package maps to src.messaging
sys.modules.setdefault("messaging", importlib.import_module("src.messaging"))

from messaging.producer import KassaProducer


def test_publish_declares_queue_and_publishes():
    prod = KassaProducer(host="example")
    # set a fake manager with a fake channel
    fake_mgr = FakeManager()
    prod._manager = fake_mgr

    prod.publish("hello", routing_key="routing.test", queue_name="q.test", declare_queue=True, exchange="")

    fake_mgr.channel.queue_declare.assert_called_once()
    fake_mgr.channel.basic_publish.assert_called_once()


def test_publish_with_exchange_declares_exchange_and_binds():
    prod = KassaProducer(host="example")
    fake_mgr = FakeManager()
    prod._manager = fake_mgr

    prod.publish("hi", routing_key="r.k", exchange="ex.test", queue_name="q2", declare_queue=True)

    fake_mgr.channel.exchange_declare.assert_called_once()
    fake_mgr.channel.queue_bind.assert_called_once()
    fake_mgr.channel.basic_publish.assert_called_once()
