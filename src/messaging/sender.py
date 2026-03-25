from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Optional

from .connection import RabbitMQClient
from .message_builders import (
    build_heartbeat_xml,
    build_invoice_requested_xml,
    build_payment_confirmed_xml,
    build_person_lookup_request_xml,
    build_status_check_xml,
    build_unpaid_request_xml,
)
from .xml_validator import XMLValidator


class KassaSender:
    def __init__(
        self,
        rabbitmq: RabbitMQClient,
        validator: XMLValidator,
        system_name: str,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        self.rabbitmq = rabbitmq
        self.validator = validator
        self.system_name = system_name
        self.logger = logger or logging.getLogger(__name__)

    async def _publish(self, queue_name: str, xml_bytes: bytes, durable: bool) -> None:
        self.validator.validate(xml_bytes)
        await self.rabbitmq.publish(queue_name, xml_bytes, durable=durable)

    async def publish_heartbeat(self, timestamp: datetime) -> None:
        xml_bytes = build_heartbeat_xml(self.system_name, timestamp)
        await self._publish("kassa.heartbeat", xml_bytes, durable=False)

    async def publish_status_check(
        self,
        timestamp: datetime,
        status: str,
        uptime: int,
        cpu: float,
        memory: float,
        disk: float,
    ) -> None:
        xml_bytes = build_status_check_xml(
            service_id=self.system_name,
            timestamp=timestamp,
            status=status,
            uptime=uptime,
            cpu=cpu,
            memory=memory,
            disk=disk,
        )
        await self._publish("kassa.status.checked", xml_bytes, durable=False)

    async def publish_person_lookup_requested(self, request_id: str, email: str) -> None:
        xml_bytes = build_person_lookup_request_xml(request_id, email)
        await self._publish("kassa.person.lookup.requested", xml_bytes, durable=True)

    async def publish_payment_confirmed(
        self,
        email: str,
        amount: float,
        paid_at: datetime,
        user_id: str | None = None,
        registration_id: str | None = None,
    ) -> None:
        xml_bytes = build_payment_confirmed_xml(
            email=email,
            amount=amount,
            paid_at=paid_at,
            user_id=user_id,
            registration_id=registration_id,
        )
        await self._publish("kassa.payment.confirmed", xml_bytes, durable=True)

    async def publish_unpaid_requested(self, request_id: str) -> None:
        xml_bytes = build_unpaid_request_xml(request_id)
        await self._publish("kassa.unpaid.requested", xml_bytes, durable=True)

    async def publish_invoice_requested(
        self,
        order_id: str,
        user_id: str,
        company_id: str,
        amount: float,
        ordered_at: datetime,
        items: list[dict[str, Any]],
        email: str | None = None,
        company_name: str | None = None,
        event_id: str | None = None,
        payment_reference: str | None = None,
    ) -> None:
        xml_bytes = build_invoice_requested_xml(
            order_id=order_id,
            user_id=user_id,
            company_id=company_id,
            amount=amount,
            ordered_at=ordered_at,
            items=items,
            email=email,
            company_name=company_name,
            event_id=event_id,
            payment_reference=payment_reference,
        )
        await self._publish("kassa.invoice.requested", xml_bytes, durable=True)
