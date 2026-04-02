# Een centraal bestand voor instellingen zoals het IP-adres van de RabbitMQ server, gebruikersnamen en wachtwoorden.
"""Centrale configuratie-instellingen.

Plaats hier eenvoudige constants zoals hostnamen en queue-namen.
"""

import os


def _get_int_env(name: str, default: int) -> int:
	value = os.getenv(name)
	if value is None:
		return default
	try:
		return int(value)
	except ValueError:
		return default


# RabbitMQ connectie-instellingen
RABBIT_HOST = os.getenv('RABBIT_HOST', 'localhost')
RABBIT_PORT = _get_int_env('RABBIT_PORT', 5672)
RABBIT_USER = os.getenv('RABBIT_USER', 'guest')
RABBIT_PASSWORD = os.getenv('RABBIT_PASSWORD', 'guest')
RABBIT_VHOST = os.getenv('RABBIT_VHOST', '/')

# Heartbeat instellingen
HEARTBEAT_INTERVAL_SECONDS = _get_int_env('HEARTBEAT_INTERVAL_SECONDS', 1)
HEARTBEAT_EXCHANGE = os.getenv('HEARTBEAT_EXCHANGE', 'heartbeat.direct')
HEARTBEAT_ROUTING_KEY = os.getenv('HEARTBEAT_ROUTING_KEY', 'routing.heartbeat')

# Queue names / Routing keys
HEARTBEAT_QUEUE = os.getenv('HEARTBEAT_QUEUE', 'heartbeat_queue')
USER_UPDATES_QUEUE = 'user_updates'
CONSUMPTION_ORDER_QUEUE = 'ConsumptionOrder'
PAYMENT_COMPLETED_QUEUE = 'PaymentCompleted'
