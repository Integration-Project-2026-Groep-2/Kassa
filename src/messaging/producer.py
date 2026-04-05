import logging
from connection import RabbitManager
from config import RABBIT_HOST, RABBIT_PORT, RABBIT_USER, RABBIT_PASSWORD, RABBIT_VHOST

"""Producer helper to publish XML messages to RabbitMQ.

This module wraps `RabbitManager` and exposes a simple `publish` method
which declares the queue (idempotent) and publishes the byte payload.
"""

logger = logging.getLogger(__name__)


class KassaProducer:
    """Eenvoudige producer voor het versturen van berichten.

    - `host` is de RabbitMQ hostnaam.
    - `connect()` opent de verbinding.
    - `publish(payload, routing_key=...)` stuurt een bericht.
    - `close()` sluit de verbinding.
    """

    def __init__(self, host: str = 'localhost'):
        self.host = host or RABBIT_HOST
        self._manager = RabbitManager(
            host=self.host,
            port=RABBIT_PORT,
            user=RABBIT_USER,
            password=RABBIT_PASSWORD,
            vhost=RABBIT_VHOST,
        )

    def connect(self):
        """Open de verbinding en het kanaal."""
        self._manager.connect()

    def publish(
        self,
        payload: str,
        routing_key: str = 'kassa.heartbeat',
        exchange: str = '',
        queue_name: str | None = None,
        durable: bool = True,
    ):
        """Publiceer een string-payload naar de opgegeven `routing_key`.

        durable=False voor queues zoals kassa.heartbeat en kassa.status.checked
        (conform de contracten). durable=True voor queues die berichten moeten
        bewaren bij een RabbitMQ-herstart.
        """
        channel = self._manager.channel

        # Als een exchange expliciet meegegeven is, declareer die ook expliciet
        # zodat hij zichtbaar is in RabbitMQ Management.
        if exchange:
            channel.exchange_declare(exchange=exchange, exchange_type='direct', durable=True)

        target_queue = queue_name or routing_key
        channel.queue_declare(queue=target_queue, durable=durable)

        if exchange:
            channel.queue_bind(queue=target_queue, exchange=exchange, routing_key=routing_key)
        channel.basic_publish(exchange=exchange, routing_key=routing_key, body=payload.encode('utf-8'))
        logger.debug("Bericht gepubliceerd naar %s", routing_key)

    def close(self):
        """Sluit de achterliggende verbinding."""
        self._manager.close()
#De "blauwdruk" voor het verzenden van elk type bericht (Order, Payment, Heartbeat).