"""Unit tests for RabbitMQLogHandler — verifies logs.direct routing and failure isolation.

Run from the Kassa repo root:
    python -m unittest tests.test_logging_config -v
"""
import io
import logging
import sys
import types
import unittest
from unittest.mock import AsyncMock, patch

# src/config.py uses sibling-imports that only resolve when /app/src is on sys.path.
# Stub it before importing logging_config so the lazy import inside _ensure_connected
# succeeds during tests without dragging in the rest of the project.
_fake_config = types.ModuleType("src.config")
_fake_config.RABBIT_HOST = "localhost"
_fake_config.RABBIT_PORT = 5672
_fake_config.RABBIT_USER = "guest"
_fake_config.RABBIT_PASSWORD = "guest"
_fake_config.RABBIT_VHOST = "/"
sys.modules.setdefault("src.config", _fake_config)

# Also stub the top-level `settings` module that `src.logging_config` imports.
_fake_settings = types.ModuleType("settings")
_fake_settings.RABBIT_HOST = "localhost"
_fake_settings.RABBIT_PORT = 5672
_fake_settings.RABBIT_USER = "guest"
_fake_settings.RABBIT_PASSWORD = "guest"
_fake_settings.RABBIT_VHOST = "/"
sys.modules.setdefault("settings", _fake_settings)

import os
os.environ['ENABLE_RABBITMQ_LOGS'] = 'false'

from src.logging_config import RabbitMQLogHandler


def _record(level: int = logging.INFO, msg: str = "hello") -> logging.LogRecord:
    return logging.LogRecord(
        name="test",
        level=level,
        pathname=__file__,
        lineno=1,
        msg=msg,
        args=None,
        exc_info=None,
    )


class RabbitMQLogHandlerTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        # Stub _worker_thread so __init__ doesn't spawn a real daemon that
        # would race against the test's mocked aio_pika.
        with patch.object(RabbitMQLogHandler, "_worker_thread", lambda self: None):
            self.handler = RabbitMQLogHandler(service_name="KASSA")
        self.handler.stop_event.set()

    @patch("src.logging_config.aio_pika.connect_robust", new_callable=AsyncMock)
    async def test_publish_uses_logs_direct_exchange(self, mock_connect: AsyncMock) -> None:
        connection = AsyncMock()
        channel = AsyncMock()
        channel.is_closed = False
        exchange = AsyncMock()
        connection.channel.return_value = channel
        channel.declare_exchange.return_value = exchange
        mock_connect.return_value = connection

        await self.handler._publish_to_rabbitmq(_record(logging.INFO, "hello kibana"))

        channel.declare_exchange.assert_awaited_once_with(
            "logs.direct", "direct", durable=True
        )
        exchange.publish.assert_awaited_once()

        message = exchange.publish.await_args.args[0]
        routing_key = exchange.publish.await_args.kwargs["routing_key"]
        self.assertEqual(routing_key, "routing.log")
        self.assertIn(b"<service>KASSA</service>", message.body)
        self.assertIn(b"<level>INFO</level>", message.body)
        self.assertIn(b"<data>hello kibana</data>", message.body)
        self.assertTrue(message.body.startswith(b"<?xml"))

    @patch("src.logging_config.aio_pika.connect_robust", new_callable=AsyncMock)
    async def test_publish_failure_does_not_crash(self, mock_connect: AsyncMock) -> None:
        mock_connect.side_effect = RuntimeError("broker is down")
        captured = io.StringIO()

        with patch.object(sys, "stderr", captured):
            await self.handler._publish_to_rabbitmq(_record(logging.ERROR, "boom"))

        self.assertIn("broker is down", captured.getvalue())
        self.assertIsNone(self.handler._connection)
        self.assertIsNone(self.handler._channel)
        self.assertIsNone(self.handler._exchange)


if __name__ == "__main__":
    unittest.main()
