from __future__ import annotations

import asyncio
import logging
from typing import Optional

from aio_pika.abc import AbstractIncomingMessage

from connection import RabbitMQClient
from message_handlers import dispatch_message
from odoo_client import OdooClient
from xml_validator import XMLValidator


INBOUND_QUEUES: dict[str, bool] = {
    "controlroom.warning.issued": False,
    "crm.person.lookup.responded": False,
    "crm.user.confirmed": True,
    "crm.company.confirmed": True,
    "crm.unpaid.responded": False,
    "crm.user.updated": True,
    "crm.company.updated": True,
    "crm.user.deactivated": True,
    "crm.company.deactivated": True,
}


class KassaReceiver:
    def __init__(
        self,
        rabbitmq: RabbitMQClient,
        validator: XMLValidator,
        odoo_client: OdooClient,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        self.rabbitmq = rabbitmq
        self.validator = validator
        self.odoo_client = odoo_client
        self.logger = logger or logging.getLogger(__name__)
        self._stop_event = asyncio.Event()

    async def _handle_message(self, queue_name: str, message: AbstractIncomingMessage) -> None:
        async with message.process(ignore_processed=True):
            try:
                self.validator.validate(message.body)
                await dispatch_message(message.body, self.odoo_client, self.logger)
                self.logger.info("Processed message from queue '%s'.", queue_name)
            except Exception as exc:
                self.logger.exception("Failed to process message from '%s': %s", queue_name, exc)

    def _callback_factory(self, queue_name: str):
        async def _callback(message: AbstractIncomingMessage) -> None:
            await self._handle_message(queue_name, message)

        return _callback

    async def run(self) -> None:
        self.logger.info("Receiver service starting...")

        for queue_name, durable in INBOUND_QUEUES.items():
            await self.rabbitmq.consume(
                queue_name=queue_name,
                callback=self._callback_factory(queue_name),
                durable=durable,
            )

        self.logger.info("Receiver service started.")
        try:
            await self._stop_event.wait()
        except asyncio.CancelledError:
            self.logger.info("Receiver service stopped.")
            raise

    def stop(self) -> None:
        self._stop_event.set()
