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
        credentials = pika.PlainCredentials(self.user, self.password)
        candidate_hosts = [self.host]
        if self.host in {'localhost', 'rabbitmq'}:
            candidate_hosts.append('127.0.0.1')

        # Retry loop: RabbitMQ container kan al "healthy" zijn terwijl AMQP nog opstart.
        while True:
            last_error = None
            for resolved_host in candidate_hosts:
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
                except Exception as exc:
                    last_error = exc

            logger.warning(
                "RabbitMQ connectie mislukt (hosts=%s, port=%s, user=%s, vhost=%s). Opnieuw proberen in 2s...",
                candidate_hosts,
                self.port,
                self.user,
                self.vhost,
            )
            if last_error is not None:
                logger.debug("Laatste RabbitMQ-fout: %s", last_error)
            time.sleep(2)

    def close(self):
        """Sluit de verbinding als die bestaat."""
        if self.connection:
            self.connection.close()



