"""
Entry point voor de Kassa integratiservice.
Start de heartbeat taak die elke seconde een bericht stuurt naar Control Room.

Opstarten:
    python src/main.py

Vereisten:
    - RabbitMQ draait (lokaal via docker compose up rabbitmq, of op de VM)
    - .env correct ingevuld met RABBITMQ_URL
"""

import asyncio
import logging
import os

import aio_pika

from heartbeat import run_heartbeat

logging.basicConfig(
    level=logging.INFO,
    format='[%(levelname)s] %(asctime)s %(name)s: %(message)s',
)
logger = logging.getLogger(__name__)

# RabbitMQ verbindings-URL uit omgevingsvariabele
# Formaat: amqp://gebruiker:wachtwoord@host/vhost
# Voorbeeld lokaal:  amqp://guest:guest@localhost/
# Voorbeeld VM:      amqp://team_kassa:wachtwoord@<vm-host>/
RABBITMQ_URL = os.environ.get('RABBITMQ_URL', 'amqp://guest:guest@localhost/')


async def main() -> None:
    logger.info("Kassa integratieservice opgestart")
    logger.info("Verbinding maken met RabbitMQ op %s ...", RABBITMQ_URL)

    # connect_robust herverbindt automatisch bij een RabbitMQ-herstart
    connection = await aio_pika.connect_robust(RABBITMQ_URL)

    logger.info("Verbinding geslaagd — heartbeat starten")

    # run_heartbeat loopt voor altijd (while True) — hij stopt alleen bij Ctrl+C
    await run_heartbeat(connection)


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Gestopt door gebruiker (Ctrl+C)")
