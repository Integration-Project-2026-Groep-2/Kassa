from __future__ import annotations

import asyncio
import logging
import signal
from typing import Any

from config import Settings
from heartbeat import HeartbeatService
from messaging.connection import RabbitMQClient
from messaging.receiver import KassaReceiver
from messaging.sender import KassaSender
from messaging.xml_validator import XMLValidator
from odoo.client import OdooClient
from status import StatusService


def setup_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )


async def run_app() -> None:
    settings = Settings.from_env()
    setup_logging(settings.log_level)
    logger = logging.getLogger("kassa")

    logger.info("Starting Team Kassa application...")

    rabbitmq = RabbitMQClient(settings.rabbitmq_url, logger=logger)
    await rabbitmq.connect()

    validator = XMLValidator(settings.schema_path)

    odoo_client = OdooClient(
        url=settings.odoo_url,
        database=settings.odoo_database,
        username=settings.odoo_username,
        password=settings.odoo_password,
        logger=logger,
    )
    await odoo_client.connect()

    sender = KassaSender(
        rabbitmq=rabbitmq,
        validator=validator,
        system_name=settings.system_name,
        logger=logger,
    )

    receiver = KassaReceiver(
        rabbitmq=rabbitmq,
        validator=validator,
        odoo_client=odoo_client,
        logger=logger,
    )

    heartbeat_service = HeartbeatService(
        sender=sender,
        interval_seconds=settings.heartbeat_interval_seconds,
        logger=logger,
    )

    status_service = StatusService(
        sender=sender,
        interval_seconds=settings.status_check_interval_seconds,
        logger=logger,
    )

    tasks = [
        asyncio.create_task(receiver.run(), name="receiver"),
        asyncio.create_task(heartbeat_service.run(), name="heartbeat"),
        asyncio.create_task(status_service.run(), name="status"),
    ]

    stop_event = asyncio.Event()

    def _stop() -> None:
        logger.info("Shutdown signal received.")
        stop_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _stop)
        except NotImplementedError:
            pass

    try:
        await stop_event.wait()
    finally:
        receiver.stop()

        for task in tasks:
            task.cancel()

        await asyncio.gather(*tasks, return_exceptions=True)
        await rabbitmq.close()
        logger.info("Team Kassa application stopped.")


if __name__ == "__main__":
    try:
        asyncio.run(run_app())
    except KeyboardInterrupt:
        pass
