"""Contract 7 — Kassa → Controlroom: heartbeat elke 1 seconde."""

import asyncio
import logging
import os
from datetime import datetime, timezone

import aio_pika
from aio_pika import ExchangeType
from aio_pika.abc import AbstractChannel, AbstractExchange, AbstractRobustConnection
from lxml import etree

from xml_validator import validate

logger = logging.getLogger(__name__)

HEARTBEAT_INTERVAL_SECONDS = int(os.environ.get('HEARTBEAT_INTERVAL_SECONDS', 1))


def _build_heartbeat_xml() -> bytes:
    """
    Bouw een Heartbeat XML-bericht conform Contract 7.
    Verplichte velden: serviceId (KASSA), timestamp. Geen extra velden.
    """
    root = etree.Element("Heartbeat")
    etree.SubElement(root, "serviceId").text = "KASSA"
    etree.SubElement(root, "timestamp").text = datetime.now(timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    return etree.tostring(root, xml_declaration=True, encoding="UTF-8")


async def _get_channel(
    connection: AbstractRobustConnection,
) -> tuple[AbstractChannel, AbstractExchange]:
    """Open een nieuw kanaal en declareer de heartbeat exchange.
    Apart gezet zodat het opnieuw aangeroepen kan worden na een kanaalfout.
    """
    channel = await connection.channel()
    exchange = await channel.declare_exchange(
        "heartbeat.direct", type=ExchangeType.DIRECT, durable=True
    )
    return channel, exchange


async def run_heartbeat(connection: AbstractRobustConnection) -> None:
    """
    Publiceer een XML heartbeat via heartbeat.direct exchange elke seconde.

    - Declareert exchange heartbeat.direct (direct, durable=True)
    - Maakt automatisch een nieuw kanaal aan na een fout
    - Per iteratie try/except: logt fout, slaat iteratie over, loop gaat door
    - Heartbeat mag NOOIT stoppen
    """
    channel: AbstractChannel | None = None
    exchange: AbstractExchange | None = None

    logger.info("Heartbeat task gestart (interval=%ds)", HEARTBEAT_INTERVAL_SECONDS)

    while True:
        try:
            if channel is None or channel.is_closed:
                logger.info("Heartbeat kanaal openen...")
                channel, exchange = await _get_channel(connection)

            xml_bytes = _build_heartbeat_xml()
            validate(xml_bytes)

            await exchange.publish(
                aio_pika.Message(body=xml_bytes),
                routing_key="routing.heartbeat",
            )
            logger.debug("Heartbeat gepubliceerd")
        except (ValueError, etree.XMLSyntaxError):
            logger.exception("Heartbeat XML-validatie mislukt")
        except Exception:
            logger.exception("Heartbeat iteratie mislukt")
            channel = None
            exchange = None

        await asyncio.sleep(HEARTBEAT_INTERVAL_SECONDS)
