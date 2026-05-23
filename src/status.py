"""Contract 8 — Kassa → Controlroom: statuscheck elke 2 minuten."""

import asyncio
import logging
import os
import time
from datetime import datetime, timezone

import aio_pika
from aio_pika.abc import AbstractRobustConnection
from lxml import etree

from xml_validator import validate

logger = logging.getLogger(__name__)

STATUS_INTERVAL_SECONDS = int(os.environ.get('STATUS_INTERVAL_SECONDS', 120))

_EXCHANGE_NAME  = "statuscheck.direct"
_ROUTING_KEY    = "routing.statuscheck"
_QUEUE_NAME     = "controlroom.statuscheck.queue"
_DLQ_NAME       = "controlroom.statuscheck.queue.dlq"

# Tijdstip waarop de service gestart is, voor uptime berekening
_START_TIME = time.monotonic()


def _get_system_load() -> tuple[float, float]:
    """Geeft memory en disk terug als float tussen 0.0 en 1.0."""
    try:
        import psutil
        memory = psutil.virtual_memory().percent / 100.0
        disk = psutil.disk_usage('/').percent / 100.0
        return memory, disk
    except ImportError:
        logger.warning("psutil niet beschikbaar — geheugen/schijf worden als 0.0 gerapporteerd")
        return 0.0, 0.0


def _build_status_xml() -> bytes:
    """Bouw een StatusCheck XML-bericht conform Contract 8."""
    memory, disk = _get_system_load()
    uptime = int(time.monotonic() - _START_TIME)

    root = etree.Element("StatusCheck")
    etree.SubElement(root, "serviceId").text = "KASSA"
    etree.SubElement(root, "timestamp").text = datetime.now(timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    etree.SubElement(root, "uptime").text = str(uptime)
    etree.SubElement(root, "memory").text = f"{memory:.2f}"
    etree.SubElement(root, "disk").text = f"{disk:.2f}"

    return etree.tostring(root, xml_declaration=True, encoding="UTF-8")


async def run_status(connection: AbstractRobustConnection) -> None:
    """
    Publiceer een StatusCheck XML-bericht elke 2 minuten.
    Exchange: statuscheck.direct | Queue: controlroom.statuscheck.queue | durable: true
    """
    logger.info("Status task gestart (interval=%ds)", STATUS_INTERVAL_SECONDS)

    channel = None

    while True:
        try:
            if channel is None or channel.is_closed:
                logger.info("Status kanaal openen...")
                channel = await connection.channel()

                dlq = await channel.declare_queue(_DLQ_NAME, durable=True)

                exchange = await channel.declare_exchange(
                    _EXCHANGE_NAME,
                    aio_pika.ExchangeType.DIRECT,
                    durable=True,
                )

                queue = await channel.declare_queue(_QUEUE_NAME, durable=True)
                await queue.bind(exchange, routing_key=_ROUTING_KEY)

            xml_bytes = _build_status_xml()
            validate(xml_bytes)

            await exchange.publish(
                aio_pika.Message(body=xml_bytes),
                routing_key=_ROUTING_KEY,
            )
            logger.debug("StatusCheck gepubliceerd")
        except (ValueError, etree.XMLSyntaxError):
            logger.exception("StatusCheck XML-validatie mislukt")
        except Exception:
            logger.exception("StatusCheck iteratie mislukt")
            channel = None

        await asyncio.sleep(STATUS_INTERVAL_SECONDS)
