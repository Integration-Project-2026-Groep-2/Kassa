import logging
from connection import RabbitManager

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
        self.host = host
        self._manager = RabbitManager(host=self.host)

    def connect(self):
        """Open de verbinding en het kanaal."""
        self._manager.connect()

    def publish(self, payload: str, routing_key: str = 'heartbeat_queue', exchange: str = ''):
        """Publiceer een string-payload naar de opgegeven `routing_key`.

        We declareren de queue eerst om er zeker van te zijn dat deze bestaat.
        De payload wordt als bytes naar RabbitMQ gestuurd.
        """
        channel = self._manager.channel
        # durable=True zodat de queue een RabbitMQ-herstart overleeft
        # én overeenkomt met hoe Odoo de queue declareert (anders: PRECONDITION_FAILED)
        channel.queue_declare(queue=routing_key, durable=True)
        channel.basic_publish(exchange=exchange, routing_key=routing_key, body=payload.encode('utf-8'))
        logger.debug("Bericht gepubliceerd naar %s", routing_key)

    def close(self):
        """Sluit de achterliggende verbinding."""
        self._manager.close()
#De "blauwdruk" voor het verzenden van elk type bericht (Order, Payment, Heartbeat).