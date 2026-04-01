import logging
from connection import RabbitManager

"""Consumer helper die berichten van een queue leest en een callback aanroept.

Callback signature: callback(body: bytes)
"""

logger = logging.getLogger(__name__)


class KassaConsumer:
    """Eenvoudige consumer die een callback aanroept voor elk bericht."""

    def __init__(self, host: str = 'localhost'):
        self.host = host
        self._manager = RabbitManager(host=self.host)

    def connect(self):
        """Open de verbinding en het kanaal."""
        self._manager.connect()

    def start_listening(self, queue_name: str, callback, durable: bool = True):
        """Bind aan `queue_name` en roep `callback(body)` aan voor elk bericht.

        durable=False voor tijdelijke queues (bv. kassa.heartbeat, controlroom.warning.issued).
        durable=True voor queues die berichten bewaren bij een RabbitMQ-herstart.
        """
        channel = self._manager.channel
        channel.queue_declare(queue=queue_name, durable=durable)

        def _on_message(ch, method, properties, body):
            try:
                callback(body)
            except Exception:
                logger.exception("Fout tijdens verwerking van bericht")

        logger.info("Start listening on queue '%s'", queue_name)
        channel.basic_consume(queue=queue_name, on_message_callback=_on_message, auto_ack=True)
        try:
            channel.start_consuming()
        except KeyboardInterrupt:
            logger.info("Consumer gestopt (KeyboardInterrupt)")

    def close(self):
        self._manager.close()