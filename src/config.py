# Een centraal bestand voor instellingen zoals het IP-adres van de RabbitMQ server, gebruikersnamen en wachtwoorden.
"""Centrale configuratie-instellingen.

Plaats hier eenvoudige constants zoals hostnamen en queue-namen.
"""

import os
from pathlib import Path

def _load_local_env() -> None:
	root_env = Path(__file__).resolve().parents[1] / '.env'
	if not root_env.exists():
		return

	for raw_line in root_env.read_text(encoding='utf-8').splitlines():
		line = raw_line.strip()
		if not line or line.startswith('#') or '=' not in line:
			continue
		key, value = line.split('=', 1)
		key = key.strip()
		value = value.strip().strip('"').strip("'")
		os.environ.setdefault(key, value)


_load_local_env()


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

# Legacy/local heartbeat queue naming (env-overridable)
HEARTBEAT_QUEUE = os.getenv('HEARTBEAT_QUEUE', 'heartbeat_queue')
USER_UPDATES_QUEUE = 'user_updates'
CONSUMPTION_ORDER_QUEUE = 'ConsumptionOrder'
PAYMENT_COMPLETED_QUEUE = 'PaymentCompleted'

# Queue names — conform contracten (Kassa publiceert op)
CONTRACT_HEARTBEAT_QUEUE = os.getenv('CONTRACT_HEARTBEAT_QUEUE', 'kassa.heartbeat')
STATUS_QUEUE = os.getenv('STATUS_QUEUE', 'kassa.status.checked')
PERSON_LOOKUP_QUEUE = os.getenv('PERSON_LOOKUP_QUEUE', 'kassa.person.lookup.requested')
PAYMENT_CONFIRMED_QUEUE = os.getenv('PAYMENT_CONFIRMED_QUEUE', 'kassa.payment.confirmed')
UNPAID_REQUEST_QUEUE = os.getenv('UNPAID_REQUEST_QUEUE', 'kassa.unpaid.requested')
INVOICE_REQUESTED_QUEUE = os.getenv('INVOICE_REQUESTED_QUEUE', 'kassa.invoice.requested')

# Queue names — conform contracten (Kassa luistert op)
WARNING_QUEUE = os.getenv('WARNING_QUEUE', 'controlroom.warning.issued')
PERSON_LOOKUP_RESPONSE_QUEUE = os.getenv('PERSON_LOOKUP_RESPONSE_QUEUE', 'crm.person.lookup.responded')
USER_CONFIRMED_QUEUE = os.getenv('USER_CONFIRMED_QUEUE', 'crm.user.confirmed')
COMPANY_CONFIRMED_QUEUE = os.getenv('COMPANY_CONFIRMED_QUEUE', 'crm.company.confirmed')
UNPAID_RESPONSE_QUEUE = os.getenv('UNPAID_RESPONSE_QUEUE', 'crm.unpaid.responded')
USER_UPDATED_QUEUE = os.getenv('USER_UPDATED_QUEUE', 'crm.user.updated')
COMPANY_UPDATED_QUEUE = os.getenv('COMPANY_UPDATED_QUEUE', 'crm.company.updated')
USER_DEACTIVATED_QUEUE = os.getenv('USER_DEACTIVATED_QUEUE', 'crm.user.deactivated')
COMPANY_DEACTIVATED_QUEUE = os.getenv('COMPANY_DEACTIVATED_QUEUE', 'crm.company.deactivated')
