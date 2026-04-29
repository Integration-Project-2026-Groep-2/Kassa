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

import aio_pika
from aio_pika.abc import AbstractRobustConnection
from lxml import etree

from xml_validator import validate_xml
from models.user import UserStore
from messaging.user_consumer import UserConsumer

logger = logging.getLogger(__name__)

# Global user store and consumer (initialized in run_receiver)
_user_store: UserStore | None = None
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
        user_id = root.findtext("id", "")
        email = root.findtext("email", "")
        role = root.findtext("role", "")
        logger.info("UserConfirmed ontvangen [id=%s email=%s role=%s]", user_id, email, role)

        if _user_consumer is not None:
            try:
                xml_string = message.body.decode('utf-8')
                _user_consumer.process_user_message(xml_string)
            except Exception as exc:
                logger.error("UserConfirmed: fout bij opslaan in store: %s", exc)


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
        user_id = root.findtext("id", "")
        email = root.findtext("email", "")
        logger.info("UserUpdated ontvangen [id=%s email=%s] — lokale kopie vervangen", user_id, email)

        if _user_consumer is not None:
            try:
                xml_string = message.body.decode('utf-8')
                _user_consumer.process_user_message(xml_string)
            except Exception as exc:
                logger.error("UserUpdated: fout bij opslaan in store: %s", exc)


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
        user_id = root.findtext("id", "")
        email = root.findtext("email", "")
        logger.info(
            "UserDeactivated ontvangen [id=%s email=%s] — gebruiker gedeactiveerd, audit trail behouden",
            user_id, email,
        )

        if _user_consumer is not None:
            try:
                xml_string = message.body.decode('utf-8')
                _user_consumer.process_user_message(xml_string)
            except Exception as exc:
                logger.error("UserDeactivated: fout bij verwijderen uit store: %s", exc)


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


# ── User CRUD handlers ──────────────────────────────────────────────────────

async def on_user_message(message: aio_pika.IncomingMessage) -> None:
    """
    Handle User, UserCreated, UserUpdated, or UserDeleted messages.
    Uses the global UserConsumer to process and store user data.
    """
    async with message.process():
        if _user_consumer is None:
            logger.error("UserConsumer not initialized")
            return
        
        try:
            xml_string = message.body.decode('utf-8')
        except UnicodeDecodeError:
            logger.error("Integration User: could not decode message as UTF-8")
            return
        
        success = _user_consumer.process_user_message(xml_string)
        if not success:
            logger.error("Failed to process user message")
            return
        
        logger.info("User message processed successfully")


# ── Queue configuratie ─────────────────────────────────────────────────────────

# (queue_name, durable, handler)
QUEUE_HANDLERS = [
    ("controlroom.warning.issued",      False, on_warning),
    ("crm.person.lookup.responded",     False, on_person_lookup_response),
    ("crm.user.confirmed",              True,  on_user_confirmed),
    ("crm.company.confirmed",           True,  on_company_confirmed),
    ("crm.unpaid.responded",            False, on_unpaid_response),
    ("crm.user.updated",                True,  on_user_updated),
    ("crm.company.updated",             True,  on_company_updated),
    ("crm.user.deactivated",            True,  on_user_deactivated),
    ("crm.company.deactivated",         True,  on_company_deactivated),
    # Kassa User CRUD queues
    ("kassa.user.created",              True,  on_user_message),
    ("kassa.user.updated",              True,  on_user_message),
    ("kassa.user.deleted",              True,  on_user_message),
]


# ── Entry point ────────────────────────────────────────────────────────────────

async def run_receiver(connection: AbstractRobustConnection) -> None:
    """
    Start de async receiver voor alle inkomende queues (R1–R3) en integratie service.
    Elke queue krijgt zijn eigen consumer. Draait voor altijd.
    
    Initialiseert ook het UserStore en UserConsumer voor CRUD operations.
    """
    global _user_store, _user_consumer
    
    # Initialize user store and consumer
    _user_store = UserStore()
    _user_consumer = UserConsumer(
        _user_store,
        on_error=lambda msg_type, error: logger.error(f"User {msg_type} error: {error}")
    )
    logger.info("UserStore and UserConsumer initialized")
    logger.info("Receiver task gestart — luistert op %d queues", len(QUEUE_HANDLERS))

    channel = await connection.channel()
    await channel.set_qos(prefetch_count=10)

    for queue_name, durable, handler in QUEUE_HANDLERS:
        queue = await channel.declare_queue(queue_name, durable=durable)
        await queue.consume(handler)
        logger.info("Luisteren op queue '%s'", queue_name)

    # Blijf draaien tot de verbinding wordt gesloten
    await asyncio.Future()
