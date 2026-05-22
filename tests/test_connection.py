import sys
import types
from unittest.mock import patch, MagicMock

import pytest


# Ensure a minimal `settings` module for imports
_fake_settings = types.ModuleType("settings")
_fake_settings.RABBIT_HOST = "localhost"
_fake_settings.RABBIT_PORT = 5672
_fake_settings.RABBIT_USER = "guest"
_fake_settings.RABBIT_PASSWORD = "guest"
_fake_settings.RABBIT_VHOST = "/"
sys.modules.setdefault("settings", _fake_settings)


def test_connect_success_sets_connection_and_channel():
    import src.connection as connection

    fake_conn = MagicMock()
    fake_chan = MagicMock()
    fake_conn.channel.return_value = fake_chan

    with patch("pika.BlockingConnection", return_value=fake_conn) as mock_conn:
        mgr = connection.RabbitManager(host="example")
        mgr.connect(max_retries=1)

        assert mgr.connection is fake_conn
        assert mgr.channel is fake_chan
        mock_conn.assert_called()


def test_connect_retries_on_failure_then_succeeds():
    import src.connection as connection

    fake_conn = MagicMock()
    fake_chan = MagicMock()
    fake_conn.channel.return_value = fake_chan

    # First call raises, second call returns connection
    side_effects = [Exception("boom"), fake_conn]

    with patch("pika.BlockingConnection", side_effect=side_effects) as mock_conn:
        mgr = connection.RabbitManager(host="localhost")
        # max_retries None means loop; we set max_retries=2 to allow retry then success
        mgr.connect(max_retries=2)

        assert mgr.connection is fake_conn
        assert mgr.channel is fake_chan
        assert mock_conn.call_count >= 1


def test_connect_raises_after_max_retries():
    import src.connection as connection

    with patch("pika.BlockingConnection", side_effect=Exception("down")):
        mgr = connection.RabbitManager(host="example")
        with pytest.raises(Exception) as exc:
            mgr.connect(max_retries=1)
        assert "down" in str(exc.value)


def test_close_closes_connection():
    import src.connection as connection

    fake_conn = MagicMock()
    mgr = connection.RabbitManager(host="example")
    mgr.connection = fake_conn
    mgr.close()
    fake_conn.close.assert_called_once()
