"""
Entry point voor de Kassa integratieservice.
Start de status- en receiver-taken in één Python-proces.

De heartbeat draait niet meer hier: die wordt in de custom Odoo image
gestart zodat hij automatisch stopt zodra Odoo stopt.

Opstarten:
    python src/main.py

Vereisten:
    - RabbitMQ draait (lokaal: docker compose up rabbitmq, of VM-adres in .env)
    - .env correct ingevuld (RABBIT_HOST, RABBIT_USER, RABBIT_PASSWORD, ...)
"""

import asyncio
import logging
import os

import aio_pika

from status import run_status
from receiver import run_receiver

logging.basicConfig(
    level=os.environ.get('LOG_LEVEL', 'INFO'),
    format='[%(levelname)s] %(asctime)s %(name)s: %(message)s',
)
logger = logging.getLogger(__name__)

_host     = os.environ.get('RABBIT_HOST', 'localhost')
_port     = os.environ.get('RABBIT_PORT', '5672')
_user     = os.environ.get('RABBIT_USER', 'guest')
_password = os.environ.get('RABBIT_PASSWORD', 'guest')
_vhost    = os.environ.get('RABBIT_VHOST', '/')

RABBITMQ_URL = f"amqp://{_user}:{_password}@{_host}:{_port}/{_vhost.lstrip('/')}"


async def main() -> None:
    logger.info("Kassa integratieservice opgestart")
    logger.info("Verbinding maken met RabbitMQ op %s:%s ...", _host, _port)

    # connect_robust herverbindt automatisch bij een RabbitMQ-herstart
    connection = await aio_pika.connect_robust(RABBITMQ_URL)
    logger.info("Verbinding geslaagd")

    # Status en receiver draaien samen in dit proces.
    await asyncio.gather(
        run_status(connection),
        run_receiver(connection),
    )


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Gestopt door gebruiker (Ctrl+C)")
