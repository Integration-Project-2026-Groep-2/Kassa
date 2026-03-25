from __future__ import annotations

import logging
from typing import Awaitable, Callable, Optional

import aio_pika
from aio_pika.abc import AbstractIncomingMessage


MessageCallback = Callable[[AbstractIncomingMessage], Awaitable[None]]


class RabbitMQClient:
    def __init__(self, url: str, logger: Optional[logging.Logger] = None) -> None:
        self.url = url
        self.logger = logger or logging.getLogger(__name__)
        self.connection: aio_pika.RobustConnection | None = None
        self.channel: aio_pika.RobustChannel | None = None

    async def connect(self) -> None:
        self.logger.info("Connecting to RabbitMQ...")
        self.connection = await aio_pika.connect_robust(self.url)
        self.channel = await self.connection.channel()
        await self.channel.set_qos(prefetch_count=20)
        self.logger.info("RabbitMQ connected.")

    async def close(self) -> None:
        if self.connection is not None:
            await self.connection.close()
            self.logger.info("RabbitMQ connection closed.")

    async def declare_queue(self, queue_name: str, durable: bool = True) -> aio_pika.RobustQueue:
        if self.channel is None:
            raise RuntimeError("RabbitMQ channel is not connected.")
        return await self.channel.declare_queue(queue_name, durable=durable)

    async def publish(self, routing_key: str, body: bytes, durable: bool = True) -> None:
        if self.channel is None:
            raise RuntimeError("RabbitMQ channel is not connected.")

        delivery_mode = (
            aio_pika.DeliveryMode.PERSISTENT
            if durable
            else aio_pika.DeliveryMode.NOT_PERSISTENT
        )

        message = aio_pika.Message(
            body=body,
            content_type="application/xml",
            delivery_mode=delivery_mode,
        )

        await self.channel.default_exchange.publish(message, routing_key=routing_key)
        self.logger.info("Published message to '%s'.", routing_key)

    async def consume(
        self,
        queue_name: str,
        callback: MessageCallback,
        durable: bool = True,
    ) -> None:
        queue = await self.declare_queue(queue_name, durable=durable)
        await queue.consume(callback)
        self.logger.info("Consuming queue '%s'.", queue_name)
