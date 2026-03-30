# Een centraal bestand voor instellingen zoals het IP-adres van de RabbitMQ server, gebruikersnamen en wachtwoorden.
"""Centrale configuratie-instellingen.

Plaats hier eenvoudige constants zoals hostnamen en queue-namen.
"""

# RabbitMQ host (pas aan naar uw omgeving)
# Gebruik environment variable RABBIT_HOST of default naar 'localhost' voor lokaal
import os
RABBIT_HOST = os.getenv('RABBIT_HOST', 'localhost')  # 'localhost' voor lokaal, VM-IP voor remote

# Queue names / Routing keys
HEARTBEAT_QUEUE = 'heartbeat.direct'
USER_UPDATES_QUEUE = 'user_updates'
CONSUMPTION_ORDER_QUEUE = 'ConsumptionOrder'
PAYMENT_COMPLETED_QUEUE = 'PaymentCompleted'
#Een centraal bestand voor instellingen zoals het IP-adres van de RabbitMQ server, gebruikersnamen en wachtwoorden.