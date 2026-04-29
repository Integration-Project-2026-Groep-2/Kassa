import logging
import threading

from messaging.consumer import KassaConsumer
from config import (
    RABBIT_HOST,
    WARNING_QUEUE,
    PERSON_LOOKUP_RESPONSE_QUEUE,
    USER_CONFIRMED_QUEUE,
    COMPANY_CONFIRMED_QUEUE,
    UNPAID_RESPONSE_QUEUE,
    USER_UPDATED_QUEUE,
    COMPANY_UPDATED_QUEUE,
    USER_DEACTIVATED_QUEUE,
    COMPANY_DEACTIVATED_QUEUE,
)

"""
Receiver voor alle inkomende queues van Team Kassa (R1–R3).
Elke queue krijgt een eigen thread. Berichten worden gevalideerd en gelogd.
Bij een foutief bericht: loggen als error, nooit crashen, POS-flow niet blokkeren.

Queues (conform Docker-docs):
  R1: controlroom.warning.issued, crm.person.lookup.responded,
      crm.user.confirmed, kassa.company.confirmed, crm.unpaid.responded
  R2: crm.user.updated, kassa.company.updated
  R3: crm.user.deactivated, kassa.company.deactivated
"""

logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)


# ── R1 handlers ────────────────────────────────────────────────────────────────

def on_warning(body: bytes):
    """Contract 9 — Controlroom → Kassa: systeemwaarschuwing."""
    try:
        logger.warning("=== Warning ontvangen (Contract 9) ===\n%s", body.decode('utf-8'))
    except Exception:
        logger.error("Warning: kon bericht niet decoderen")


def on_person_lookup_response(body: bytes):
    """Contract 10b — CRM → Kassa: persoonscheck response."""
    try:
        logger.info("=== PersonLookupResponse ontvangen (Contract 10b) ===\n%s", body.decode('utf-8'))
    except Exception:
        logger.error("PersonLookupResponse: kon bericht niet decoderen")


def on_user_confirmed(body: bytes):
    """Contract 13 — CRM → Kassa: user confirmed (master data)."""
    try:
        logger.info("=== UserConfirmed ontvangen (Contract 13) ===\n%s", body.decode('utf-8'))
    except Exception:
        logger.error("UserConfirmed: kon bericht niet decoderen")


def on_company_confirmed(body: bytes):
    """Contract 14 — CRM → Kassa: company confirmed."""
    try:
        logger.info("=== CompanyConfirmed ontvangen (Contract 14) ===\n%s", body.decode('utf-8'))
    except Exception:
        logger.error("CompanyConfirmed: kon bericht niet decoderen")


def on_unpaid_response(body: bytes):
    """Contract 17b — CRM → Kassa: lijst niet-betaalden response."""
    try:
        logger.info("=== UnpaidResponse ontvangen (Contract 17b) ===\n%s", body.decode('utf-8'))
    except Exception:
        logger.error("UnpaidResponse: kon bericht niet decoderen")


# ── R2 handlers ────────────────────────────────────────────────────────────────

def on_user_updated(body: bytes):
    """Contract 18 — CRM → Kassa: user updated (volledige replace)."""
    try:
        logger.info("=== UserUpdated ontvangen (Contract 18) ===\n%s", body.decode('utf-8'))
    except Exception:
        logger.error("UserUpdated: kon bericht niet decoderen")


def on_company_updated(body: bytes):
    """Contract 19 — CRM → Kassa: company updated (volledige replace)."""
    try:
        logger.info("=== CompanyUpdated ontvangen (Contract 19) ===\n%s", body.decode('utf-8'))
    except Exception:
        logger.error("CompanyUpdated: kon bericht niet decoderen")


# ── R3 handlers ────────────────────────────────────────────────────────────────

def on_user_deactivated(body: bytes):
    """Contract 22 — CRM → Kassa: user deactivated (GDPR, soft delete)."""
    try:
        logger.info("=== UserDeactivated ontvangen (Contract 22) ===\n%s", body.decode('utf-8'))
    except Exception:
        logger.error("UserDeactivated: kon bericht niet decoderen")


def on_company_deactivated(body: bytes):
    """Contract 23 — CRM → Kassa: company deactivated."""
    try:
        logger.info("=== CompanyDeactivated ontvangen (Contract 23) ===\n%s", body.decode('utf-8'))
    except Exception:
        logger.error("CompanyDeactivated: kon bericht niet decoderen")


# ── Thread helper ──────────────────────────────────────────────────────────────

CONTACT_TOPIC_EXCHANGE = "contact.topic"

def listen_queue(queue_name: str, callback, durable: bool = True, exchange: str | None = None, routing_key: str | None = None):
    """Start een consumer voor één queue in een aparte thread."""
    consumer = KassaConsumer(host=RABBIT_HOST)
    consumer.connect()
    try:
        consumer.start_listening(
            queue_name=queue_name,
            callback=callback,
            durable=durable,
            exchange=exchange,
            routing_key=routing_key,
        )
    except KeyboardInterrupt:
        pass
    finally:
        consumer.close()


# ── Entry point ────────────────────────────────────────────────────────────────

QUEUE_HANDLERS = [
    # (queue_name, callback, durable)
    (WARNING_QUEUE,                False, on_warning),
    (PERSON_LOOKUP_RESPONSE_QUEUE, False, on_person_lookup_response),
    (USER_CONFIRMED_QUEUE,         True,  on_user_confirmed),
    (COMPANY_CONFIRMED_QUEUE,      True,  on_company_confirmed),
    (UNPAID_RESPONSE_QUEUE,        False, on_unpaid_response),
    (USER_UPDATED_QUEUE,           True,  on_user_updated),
    (COMPANY_UPDATED_QUEUE,        True,  on_company_updated),
    (USER_DEACTIVATED_QUEUE,       True,  on_user_deactivated),
    (COMPANY_DEACTIVATED_QUEUE,    True,  on_company_deactivated),
]

if __name__ == "__main__":
    threads = []
    for queue_name, durable, callback in QUEUE_HANDLERS:
        exchange = None
        routing_key = None
        if queue_name == USER_CONFIRMED_QUEUE:
            exchange = CONTACT_TOPIC_EXCHANGE
            routing_key = "crm.user.confirmed"
        elif queue_name == USER_UPDATED_QUEUE:
            exchange = CONTACT_TOPIC_EXCHANGE
            routing_key = "crm.user.updated"
        elif queue_name == USER_DEACTIVATED_QUEUE:
            exchange = CONTACT_TOPIC_EXCHANGE
            routing_key = "crm.user.deactivated"
        logger.info("Start listener op queue '%s'", queue_name)
        t = threading.Thread(
            target=listen_queue,
            args=(queue_name, callback, durable, exchange, routing_key),
            daemon=True,
        )
        t.start()
        threads.append(t)

    try:
        for t in threads:
            t.join()
    except KeyboardInterrupt:
        logger.info("Receiver gestopt.")
