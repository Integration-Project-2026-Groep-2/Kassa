# Een centraal bestand voor instellingen zoals het IP-adres van de RabbitMQ server, gebruikersnamen en wachtwoorden.
"""Centrale configuratie-instellingen.

Plaats hier eenvoudige constants zoals hostnamen en queue-namen.
"""

# RabbitMQ host (pas aan naar uw omgeving)
RABBIT_HOST = 'localhost'

# Queue names
HEARTBEAT_QUEUE = 'heartbeat_queue'
USER_UPDATES_QUEUE = 'user_updates'
#Een centraal bestand voor instellingen zoals het IP-adres van de RabbitMQ server, gebruikersnamen en wachtwoorden.