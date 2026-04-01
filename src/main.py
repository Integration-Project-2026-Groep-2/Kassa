"""
Entry point voor de Kassa integratieservice.
Start 4 asyncio-taken gelijktijdig in één Python-proces:

    heartbeat  — Contract 7:  XML heartbeat elke seconde naar Control Room
    status     — Contract 8:  StatusCheck elke 30s naar Control Room
    receiver   — R1–R3:       Luistert op alle inkomende CRM/Controlroom queues
    sender     — Contract 10a/17a: helper voor uitgaande requests (wordt on-demand gebruikt)

Opstarten:
    python src/main.py

Vereisten:
    - RabbitMQ draait (lokaal: docker compose up rabbitmq, of VM-adres in .env)
    - .env correct ingevuld met RABBITMQ_URL
"""

import asyncio
import logging
import os

import aio_pika

from heartbeat import run_heartbeat
from status import run_status
from receiver import run_receiver

logging.basicConfig(
    level=os.environ.get('LOG_LEVEL', 'INFO'),
    format='[%(levelname)s] %(asctime)s %(name)s: %(message)s',
)
logger = logging.getLogger(__name__)

RABBITMQ_URL = os.environ.get('RABBITMQ_URL', 'amqp://guest:guest@localhost/')


async def main() -> None:
    logger.info("Kassa integratieservice opgestart")
    logger.info("Verbinding maken met RabbitMQ op %s ...", RABBITMQ_URL)

    # connect_robust herverbindt automatisch bij een RabbitMQ-herstart
    connection = await aio_pika.connect_robust(RABBITMQ_URL)
    logger.info("Verbinding geslaagd")

    # Alle 4 taken starten en gelijktijdig laten draaien
    await asyncio.gather(
        run_heartbeat(connection),
        run_status(connection),
        run_receiver(connection),
    )


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Gestopt door gebruiker (Ctrl+C)")
