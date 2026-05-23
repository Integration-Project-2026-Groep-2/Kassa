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

# Tijdstip waarop de service gestart is, voor uptime berekening
_START_TIME = time.monotonic()


def _get_system_load() -> tuple[float, float, float]:
    """Geeft cpu, memory en disk terug als float tussen 0.0 en 1.0."""
    try:
        import psutil
        cpu = psutil.cpu_percent(interval=None) / 100.0
        memory = psutil.virtual_memory().percent / 100.0
        disk = psutil.disk_usage('/').percent / 100.0
        return cpu, memory, disk
    except ImportError:
        logger.warning("psutil niet beschikbaar — geheugen/schijf worden als 0.0 gerapporteerd")
        return 0.0, 0.0, 0.0


def _build_status_xml() -> bytes:
    """Bouw een StatusCheck XML-bericht conform Contract 8."""
    _, memory, disk = _get_system_load()
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
    Publiceer een StatusCheck XML-bericht elke 2 minuten naar kassa.status.checked.
    Queue: kassa.status.checked | durable: false
    """
    logger.info("Status task gestart (interval=%ds)", STATUS_INTERVAL_SECONDS)

    channel = None

    while True:
        try:
            if channel is None or channel.is_closed:
                logger.info("Status kanaal openen...")
                channel = await connection.channel()

            queue = await channel.declare_queue("kassa.status.checked", durable=False, exclusive=False)

            xml_bytes = _build_status_xml()
            validate(xml_bytes)

            await channel.default_exchange.publish(
                aio_pika.Message(body=xml_bytes),
                routing_key="kassa.status.checked",
            )
            logger.debug("StatusCheck gepubliceerd")
        except (ValueError, etree.XMLSyntaxError):
            logger.exception("StatusCheck XML-validatie mislukt")
        except Exception:
            logger.exception("StatusCheck iteratie mislukt")
            channel = None

        await asyncio.sleep(STATUS_INTERVAL_SECONDS)
