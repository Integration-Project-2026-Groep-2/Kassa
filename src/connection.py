import pika
import time
import logging
from config import RABBIT_PORT, RABBIT_USER, RABBIT_PASSWORD, RABBIT_VHOST


logger = logging.getLogger(__name__)


class RabbitManager:
    """Helperklasse om een RabbitMQ-verbinding en kanaal te beheren.

    Gebruik deze klasse om één verbinding en kanaal te openen die
    gebruikt kan worden door producers en consumers. Dit is een
    minimale wrapper rond `pika.BlockingConnection`.
    """

    def __init__(self, host='localhost', port=RABBIT_PORT, user=RABBIT_USER, password=RABBIT_PASSWORD, vhost=RABBIT_VHOST):
        # Hostnaam of IP-adres van de RabbitMQ-server (standaard 'localhost')
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.vhost = vhost
        # Placeholder voor de pika.BlockingConnection instantie
        self.connection = None
        # Placeholder voor het kanaal (channel) dat gebruikt wordt om berichten te publiceren/consumeren
        self.channel = None

    def connect(self):
        """Maak een blocking verbinding met RabbitMQ en open een kanaal."""
        # Use 127.0.0.1 to explicitly bind to IPv4 local interface
        resolved_host = '127.0.0.1' if self.host == 'localhost' else self.host
        credentials = pika.PlainCredentials(self.user, self.password)

        # Retry loop: RabbitMQ container kan al "healthy" zijn terwijl AMQP nog opstart.
        while True:
            try:
                self.connection = pika.BlockingConnection(
                    pika.ConnectionParameters(
                        host=resolved_host,
                        port=self.port,
                        virtual_host=self.vhost,
                        credentials=credentials,
                    )
                )
                self.channel = self.connection.channel()
                return
            except pika.exceptions.AMQPConnectionError:
                logger.warning(
                    "RabbitMQ connectie mislukt (host=%s, port=%s, user=%s, vhost=%s). Opnieuw proberen in 2s...",
                    resolved_host,
                    self.port,
                    self.user,
                    self.vhost,
                )
                time.sleep(2)

    def close(self):
        """Sluit de verbinding als die bestaat."""
        if self.connection:
            self.connection.close()



