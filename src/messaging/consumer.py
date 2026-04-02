import logging
from connection import RabbitManager
from config import RABBIT_HOST, RABBIT_PORT, RABBIT_USER, RABBIT_PASSWORD, RABBIT_VHOST

"""Consumer helper die berichten van een queue leest en een callback aanroept.

Callback signature: callback(body: bytes)
"""

logger = logging.getLogger(__name__)


class KassaConsumer:
    """Eenvoudige consumer die een callback aanroept voor elk bericht."""

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

    def start_listening(self, queue_name: str, callback):
        """Bind aan `queue_name` en roep `callback(body)` aan voor elk bericht.

        De callback krijgt de ruwe body (bytes). We gebruiken `auto_ack=True`
        voor eenvoud; in real-world code wil je mogelijk manuele acknowledgements.
        """
        channel = self._manager.channel
        # durable=True zodat de queue een RabbitMQ-herstart overleeft
        # én overeenkomt met hoe Odoo de queue declareert (anders: PRECONDITION_FAILED)
        channel.queue_declare(queue=queue_name, durable=True)

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