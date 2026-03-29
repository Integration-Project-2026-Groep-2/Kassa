import pika


class RabbitManager:
    """Helperklasse om een RabbitMQ-verbinding en kanaal te beheren.

    Gebruik deze klasse om één verbinding en kanaal te openen die
    gebruikt kan worden door producers en consumers. Dit is een
    minimale wrapper rond `pika.BlockingConnection`.
    """

    def __init__(self, host='localhost'):
        # Hostnaam of IP-adres van de RabbitMQ-server (standaard 'localhost')
        self.host = host
        # Placeholder voor de pika.BlockingConnection instantie
        self.connection = None
        # Placeholder voor het kanaal (channel) dat gebruikt wordt om berichten te publiceren/consumeren
        self.channel = None

    def connect(self):
        """Maak een blocking verbinding met RabbitMQ en open een kanaal."""
        self.connection = pika.BlockingConnection(pika.ConnectionParameters(host=self.host))
        self.channel = self.connection.channel()

    def close(self):
        """Sluit de verbinding als die bestaat."""
        if self.connection:
            self.connection.close()



