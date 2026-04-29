"""
Async receiver voor alle inkomende queues van Team Kassa (R1–R3).
Vervangt de threading-gebaseerde main_receiver.py.

Regels (conform documentatie):
- Foutieve berichten worden gelogd als error, veroorzaken nooit een crash
- Ontvangst blokkeert de POS-flow nooit
- Volledige replace bij user/company updates (geen partial merge)

Integreert ook:
- User CRUD operations (Integration Service)
- Ontvangst van user creates/updates vanaf CRM
"""

import asyncio
import logging
import os

import aio_pika
from aio_pika.abc import AbstractRobustConnection
from lxml import etree

from xml_validator import validate_xml
from messaging.user_consumer import UserConsumer
from odoo.odoo_connection import OdooConnection
from odoo.user_repository import OdooUserRepository

logger = logging.getLogger(__name__)

# Global user consumer and odoo connection (initialized in run_receiver)
_odoo_connection: OdooConnection | None = None
_user_consumer: UserConsumer | None = None


# ── Helpers ────────────────────────────────────────────────────────────────────

def _parse_and_validate(body: bytes, contract: str) -> etree._Element | None:
    """
    Parseer en valideer een inkomend XML-bericht.
    Geeft het root-element terug bij succes, None bij fout.
    Logt als error bij een ongeldig bericht — geen crash.
    """
    try:
        xml_string = body.decode('utf-8')
    except UnicodeDecodeError:
        logger.error("%s: kon bericht niet decoderen als UTF-8", contract)
        return None

    ok, error = validate_xml(xml_string)
    if not ok:
        logger.error("%s: ongeldig XML-bericht: %s", contract, error)
        return None

    return etree.fromstring(body)


# ── R1 handlers ────────────────────────────────────────────────────────────────

async def on_warning(message: aio_pika.IncomingMessage) -> None:
    """Contract 9 — Controlroom → Kassa: systeemwaarschuwing."""
    async with message.process():
        root = _parse_and_validate(message.body, "Contract 9 Warning")
        if root is None:
            return
        msg_type = root.findtext("type", "")
        msg_text = root.findtext("message", "")
        logger.warning("Systeemwaarschuwing ontvangen [type=%s]: %s", msg_type, msg_text)


async def on_person_lookup_response(message: aio_pika.IncomingMessage) -> None:
    """Contract 10b — CRM → Kassa: persoonscheck response."""
    async with message.process():
        root = _parse_and_validate(message.body, "Contract 10b PersonLookupResponse")
        if root is None:
            return
        request_id = root.findtext("requestId", "")
        found = root.findtext("found", "false").lower() == "true"
        linked = root.findtext("linkedToCompany", "false").lower() == "true"
        logger.info(
            "PersonLookupResponse [requestId=%s] found=%s linkedToCompany=%s",
            request_id, found, linked,
        )


async def on_user_confirmed(message: aio_pika.IncomingMessage) -> None:
    """Contract 13 — CRM → Kassa: user confirmed (master data voor personen)."""
    async with message.process():
        root = _parse_and_validate(message.body, "Contract 13 UserConfirmed")
        if root is None:
            return
        if _user_consumer is None:
            logger.error("UserConsumer not initialized")
            return

        try:
            xml_string = message.body.decode('utf-8')
        except UnicodeDecodeError:
            logger.error("Contract 13 UserConfirmed: kon bericht niet decoderen als UTF-8")
            return

        if not _user_consumer.process_user_message(xml_string):
            logger.error("Failed to process UserConfirmed message")
            return

        user_id = root.findtext("id", "")
        email = root.findtext("email", "")
        role = root.findtext("role", "")
        logger.info("UserConfirmed ontvangen [id=%s email=%s role=%s]", user_id, email, role)


async def on_company_confirmed(message: aio_pika.IncomingMessage) -> None:
    """Contract 14 — CRM → Kassa: company confirmed."""
    async with message.process():
        root = _parse_and_validate(message.body, "Contract 14 CompanyConfirmed")
        if root is None:
            return
        company_id = root.findtext("id", "")
        name = root.findtext("name", "")
        logger.info("CompanyConfirmed ontvangen [id=%s name=%s]", company_id, name)


async def on_unpaid_response(message: aio_pika.IncomingMessage) -> None:
    """Contract 17b — CRM → Kassa: lijst niet-betaalden response."""
    async with message.process():
        root = _parse_and_validate(message.body, "Contract 17b UnpaidResponse")
        if root is None:
            return
        request_id = root.findtext("requestId", "")
        persons = root.findall("persons/person")
        logger.info(
            "UnpaidResponse ontvangen [requestId=%s] %d personen",
            request_id, len(persons),
        )


# ── R2 handlers ────────────────────────────────────────────────────────────────

async def on_user_updated(message: aio_pika.IncomingMessage) -> None:
    """Contract 18 — CRM → Kassa: user updated (volledige replace, geen partial merge)."""
    async with message.process():
        root = _parse_and_validate(message.body, "Contract 18 UserUpdated")
        if root is None:
            return
        if _user_consumer is None:
            logger.error("UserConsumer not initialized")
            return

        try:
            xml_string = message.body.decode('utf-8')
        except UnicodeDecodeError:
            logger.error("Contract 18 UserUpdated: kon bericht niet decoderen als UTF-8")
            return

        if not _user_consumer.process_user_message(xml_string):
            logger.error("Failed to process UserUpdated message")
            return

        user_id = root.findtext("id", "")
        email = root.findtext("email", "")
        logger.info("UserUpdated ontvangen [id=%s email=%s] — lokale kopie vervangen", user_id, email)


async def on_company_updated(message: aio_pika.IncomingMessage) -> None:
    """Contract 19 — CRM → Kassa: company updated (volledige replace, geen partial merge)."""
    async with message.process():
        root = _parse_and_validate(message.body, "Contract 19 CompanyUpdated")
        if root is None:
            return
        company_id = root.findtext("id", "")
        name = root.findtext("name", "")
        logger.info("CompanyUpdated ontvangen [id=%s name=%s] — lokale kopie vervangen", company_id, name)


# ── R3 handlers ────────────────────────────────────────────────────────────────

async def on_user_deactivated(message: aio_pika.IncomingMessage) -> None:
    """Contract 22 — CRM → Kassa: user deactivated (GDPR, soft delete — nooit hard deleten)."""
    async with message.process():
        root = _parse_and_validate(message.body, "Contract 22 UserDeactivated")
        if root is None:
            return
        if _user_consumer is None:
            logger.error("UserConsumer not initialized")
            return

        try:
            xml_string = message.body.decode('utf-8')
        except UnicodeDecodeError:
            logger.error("Contract 22 UserDeactivated: kon bericht niet decoderen als UTF-8")
            return

        if not _user_consumer.process_user_message(xml_string):
            logger.error("Failed to process UserDeactivated message")
            return

        user_id = root.findtext("id", "")
        email = root.findtext("email", "")
        logger.info(
            "UserDeactivated ontvangen [id=%s email=%s] — gebruiker gedeactiveerd, audit trail behouden",
            user_id, email,
        )


async def on_company_deactivated(message: aio_pika.IncomingMessage) -> None:
    """Contract 23 — CRM → Kassa: company deactivated."""
    async with message.process():
        root = _parse_and_validate(message.body, "Contract 23 CompanyDeactivated")
        if root is None:
            return
        company_id = root.findtext("id", "")
        vat = root.findtext("vatNumber", "")
        logger.info(
            "CompanyDeactivated ontvangen [id=%s vatNumber=%s] — geen nieuwe transacties meer koppelen",
            company_id, vat,
        )


# ── Queue configuratie ─────────────────────────────────────────────────────────

# (queue_name, durable, handler, routing_key)
CONTACT_TOPIC_EXCHANGE = "contact.topic"
QUEUE_HANDLERS = [
    ("kassa.person.lookup.responded",   False, on_person_lookup_response, "crm.person.lookup.responded"),
    ("kassa.user.confirmed",            True,  on_user_confirmed,         "crm.user.confirmed"),
    ("kassa.unpaid.responded",          False, on_unpaid_response,        "crm.unpaid.responded"),
    ("kassa.user.updated",              True,  on_user_updated,           "crm.user.updated"),
    ("kassa.user.deactivated",          True,  on_user_deactivated,       "crm.user.deactivated"),
]


# ── Entry point ────────────────────────────────────────────────────────────────

async def run_receiver(connection: AbstractRobustConnection) -> None:
    """
    Start de async receiver voor alle inkomende queues (R1–R3) en integratie service.
    Elke queue krijgt zijn eigen consumer. Draait voor altijd.
    
    Initialiseert ook de OdooConnection en UserConsumer voor CRUD operations.
    """
    global _odoo_connection, _user_consumer
    
    # Initialize Odoo connection
    odoo_url = os.getenv('ODOO_URL', 'http://odoo:8069')
    odoo_db = os.getenv('ODOO_DB', 'odoo')
    odoo_user = os.getenv('ODOO_USER')
    odoo_password = os.getenv('ODOO_PASSWORD')
    
    _odoo_connection = OdooConnection(odoo_url, odoo_db, odoo_user, odoo_password)
    
    retry_count = 0
    max_retries = 30
    while not _odoo_connection.connect():
        retry_count += 1
        if retry_count >= max_retries:
            logger.error("Failed to connect to Odoo after %d retries, receiver will not start", max_retries)
            raise RuntimeError("Cannot connect to Odoo instance")
        logger.warning("Odoo not ready yet, retrying in 5s... (%d/%d)", retry_count, max_retries)
        await asyncio.sleep(5)
    
    logger.info("Connected to Odoo [url=%s db=%s]", odoo_url, odoo_db)
    
    # Initialize user consumer with Odoo repository
    odoo_user_repo = OdooUserRepository(_odoo_connection)
    _user_consumer = UserConsumer(
        odoo_user_repo,
        on_error=lambda msg_type, error: logger.error(f"User {msg_type} error: {error}")
    )
    logger.info("OdooUserRepository and UserConsumer initialized")
    logger.info("Receiver task gestart — luistert op %d queues", len(QUEUE_HANDLERS))

    channel = await connection.channel()
    await channel.set_qos(prefetch_count=10)
    contact_exchange = await channel.declare_exchange(
        CONTACT_TOPIC_EXCHANGE,
        aio_pika.ExchangeType.TOPIC,
        durable=True,
    )

    for queue_name, durable, handler, routing_key in QUEUE_HANDLERS:
        queue = await channel.declare_queue(queue_name, durable=durable)
        if routing_key:
            await queue.bind(contact_exchange, routing_key=routing_key)
        else:
            await queue.bind(contact_exchange, routing_key=queue_name)
        await queue.consume(handler)
        logger.info("Luisteren op queue '%s'", queue_name)

    # Blijf draaien tot de verbinding wordt gesloten
    await asyncio.Future()
