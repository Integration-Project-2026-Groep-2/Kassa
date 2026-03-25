import pika


class RabbitManager:
    """Kleine helperklasse om een RabbitMQ-verbinding en kanaal te beheren.

    De klasse houdt de host, de open `connection` en het `channel` bij.
    """

    def __init__(self, host='localhost'):
        # Hostnaam of IP-adres van de RabbitMQ-server (standaard 'localhost')
        self.host = host
        # Placeholder voor de pika.BlockingConnection instantie
        self.connection = None
        # Placeholder voor het kanaal (channel) dat gebruikt wordt om berichten te publiceren/consumeren
        self.channel = None

    def connect(self):
        # Maakt een blocking verbinding met RabbitMQ aan op de opgegeven host
        # en opent daarna een kanaal dat gebruikt kan worden voor publish/consume acties.
        self.connection = pika.BlockingConnection(pika.ConnectionParameters(host=self.host))
        self.channel = self.connection.channel()

    def close(self):
        # Sluit de actieve verbinding veilig af als er een bestaat.
        # Controle is nodig omdat `close` anders op None zou proberen te worden aangeroepen.
        if self.connection:
            self.connection.close()


