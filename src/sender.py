"""
Async sender voor uitgaande berichten vanuit de integratieservice.

Behandelt:
- Contract 10a: PersonLookupRequest → kassa.person.lookup.requested
- Contract 17a: UnpaidRequest       → kassa.unpaid.requested

Betalingen (Contract 16) en factuurverzoeken (Contract K-01) worden
verstuurd door de Odoo module zelf (kassa_pos/utils/rabbitmq_sender.py).
"""

import logging
import uuid
from datetime import datetime, timezone

import aio_pika
from aio_pika.abc import AbstractRobustConnection
from lxml import etree

from xml_validator import validate

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


async def _publish(connection: AbstractRobustConnection, queue_name: str, xml_bytes: bytes, durable: bool = True) -> bool:
    """
    Publiceer een XML-bericht naar een queue.
    Geeft True terug bij succes, False bij fout.
    """
    try:
        channel = await connection.channel()
        await channel.declare_queue(queue_name, durable=durable)
        await channel.default_exchange.publish(
            aio_pika.Message(
                body=xml_bytes,
                content_type="application/xml",
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT if durable else aio_pika.DeliveryMode.NOT_PERSISTENT,
            ),
            routing_key=queue_name,
        )
        logger.info("Bericht verstuurd naar '%s'", queue_name)
        return True
    except Exception:
        logger.exception("Verzenden naar '%s' mislukt", queue_name)
        return False


async def send_person_lookup_request(connection: AbstractRobustConnection, email: str) -> str:
    """
    Contract 10a — Kassa → CRM: persoonscheck request.
    Geeft de requestId terug zodat de caller de response (Contract 10b) kan koppelen.

    Queue: kassa.person.lookup.requested | durable: true
    """
    request_id = str(uuid.uuid4())

    root = etree.Element("PersonLookupRequest")
    etree.SubElement(root, "requestId").text = request_id
    etree.SubElement(root, "email").text = email
    xml_bytes = etree.tostring(root, xml_declaration=True, encoding="UTF-8")

    validate(xml_bytes)
    await _publish(connection, "kassa.person.lookup.requested", xml_bytes, durable=True)

    logger.info("PersonLookupRequest verstuurd [requestId=%s email=%s]", request_id, email)
    return request_id


async def send_unpaid_request(connection: AbstractRobustConnection) -> str:
    """
    Contract 17a — Kassa → CRM: lijst niet-betaalden request.
    Geeft de requestId terug zodat de caller de response (Contract 17b) kan koppelen.

    Queue: kassa.unpaid.requested | durable: true
    """
    request_id = str(uuid.uuid4())

    root = etree.Element("UnpaidRequest")
    etree.SubElement(root, "requestId").text = request_id
    xml_bytes = etree.tostring(root, xml_declaration=True, encoding="UTF-8")

    validate(xml_bytes)
    await _publish(connection, "kassa.unpaid.requested", xml_bytes, durable=True)

    logger.info("UnpaidRequest verstuurd [requestId=%s]", request_id)
    return request_id
