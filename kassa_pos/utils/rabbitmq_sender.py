# -*- coding: utf-8 -*-

import datetime
import logging
import os
import xml.etree.ElementTree as ET
from pathlib import Path

_logger = logging.getLogger(__name__)

# RabbitMQ connection settings — read lazily at connection time (not at import).
# Reading at module level would snapshot the environment before Odoo fully
# propagates container env-vars, causing the publisher to fall back to
# 'localhost'/'guest' defaults on the VM.
SCHEMA_PATH = Path(__file__).resolve().parents[2] / 'src' / 'schema' / 'kassa-schema-v1.xsd'
if not SCHEMA_PATH.exists():
    SCHEMA_PATH = Path('/app/src/schema/kassa-schema-v1.xsd')

# Authoritative schema for Contract K-02 (BatchClosed)
BATCH_SCHEMA_PATH = Path(__file__).resolve().parents[2] / 'src' / 'schema' / 'kassa_batch_contract.xsd'
if not BATCH_SCHEMA_PATH.exists():
    BATCH_SCHEMA_PATH = Path('/app/src/schema/kassa_batch_contract.xsd')

# user.topic exchange — gedeeld met CRM, Facturatie, Mailing, Planning
USER_TOPIC_EXCHANGE = os.environ.get('USER_EVENTS_EXCHANGE') or os.environ.get('USER_TOPIC_EXCHANGE', 'user.topic')

# kassa.topic exchange — specifiek voor Kassa/POS events
KASSA_TOPIC_EXCHANGE = 'kassa.topic'


def _rabbit_host():
    return os.environ.get('RABBIT_HOST') or os.environ.get('RABBITMQ_HOST', 'localhost')

def _rabbit_port():
    raw = os.environ.get('RABBIT_PORT') or os.environ.get('RABBITMQ_PORT', '5672')
    try:
        return int(raw)
    except (TypeError, ValueError):
        return 5672

def _rabbit_user():
    return os.environ.get('RABBIT_USER') or os.environ.get('RABBITMQ_USER', 'guest')

def _rabbit_pass():
    return os.environ.get('RABBIT_PASSWORD') or os.environ.get('RABBITMQ_PASS', 'guest')

def _rabbit_vhost():
    return os.environ.get('RABBIT_VHOST') or os.environ.get('RABBITMQ_VHOST', '/')

# Queue namen conform Team Kassa contractoverzicht
QUEUE_PAYMENT_CONFIRMED = 'kassa.payment.confirmed'   # Contract 16 → CRM
QUEUE_INVOICE_REQUESTED = 'kassa.invoice.requested'   # Contract K-01 → Facturatie
QUEUE_USER_CREATED = 'kassa.user.created'
QUEUE_USER_UPDATED = 'kassa.user.updated'
QUEUE_USER_DELETED = 'kassa.user.deleted'

# Routing keys voor Kassa → CRM user sync (C36/C37/C38)
# CRM declareert de consumer-queues zelf; Kassa publiceert via user.topic exchange.
ROUTING_KEY_KASSA_USER_CREATED    = 'kassa.user.created'     # C36
ROUTING_KEY_KASSA_USER_UPDATED    = 'kassa.user.updated'     # C37
ROUTING_KEY_KASSA_USER_DEACTIVATED = 'kassa.user.deactivated'  # C38


def _now_iso() -> str:
    return datetime.datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')


def _validate_xml_with_schema(xml_str: str, element_name: str) -> bool:
    """
    Validate XML against the kassa-schema-v1.xsd.
    Returns True if valid, False if validation fails.
    Logs errors appropriately.
    """
    try:
        from lxml import etree  # type: ignore[import-not-found]
    except ImportError:
        _logger.warning(
            "lxml not installed, skipping XSD validation for element=%s schema=%s. Install with: pip install lxml",
            element_name,
            SCHEMA_PATH,
        )
        return True

    try:
        # Find schema file
        schema_file = SCHEMA_PATH
        if not os.path.isabs(schema_file):
            # Try relative to module root
            module_dir = Path(__file__).parent.parent.parent
            schema_file = module_dir / SCHEMA_PATH
        
        if not os.path.exists(schema_file):
            _logger.warning(
                "Schema file not found at %s for element=%s, skipping validation",
                schema_file,
                element_name,
            )
            return True
        
        # Parse schema and XML
        schema_doc = etree.parse(str(schema_file))
        schema = etree.XMLSchema(schema_doc)
        
        xml_doc = etree.fromstring(xml_str.encode('utf-8'))
        
        # Validate
        if schema.validate(xml_doc):
            _logger.debug("XML valid for element %s", element_name)
            return True
        else:
            _logger.error(
                "XSD validation failed for %s [schema=%s]: %s",
                element_name,
                schema_file,
                schema.error_log,
            )
            return False
            
    except Exception as e:
        _logger.exception("XSD validation error for %s [schema=%s]", element_name, SCHEMA_PATH)
        return False


def _build_payment_confirmed_xml(payment_data: dict) -> str:
    """
    Bouw een PaymentConfirmed XML-bericht conform Contract 16.

    Verplichte velden: email, amount, currency, paidAt
    Optionele velden: userId, registrationId
    """
    root = ET.Element('PaymentConfirmed')

    if payment_data.get('userId'):
        ET.SubElement(root, 'userId').text = str(payment_data['userId'])

    ET.SubElement(root, 'email').text = str(payment_data.get('email', ''))

    if payment_data.get('registrationId'):
        ET.SubElement(root, 'registrationId').text = str(payment_data['registrationId'])

    ET.SubElement(root, 'amount').text = str(payment_data.get('amount', '0'))
    ET.SubElement(root, 'currency').text = 'EUR'
    ET.SubElement(root, 'paidAt').text = str(payment_data.get('paidAt') or _now_iso())

    return ET.tostring(root, encoding='unicode')


def _build_invoice_requested_xml(invoice_data: dict) -> str:
    """
    Bouw een InvoiceRequested XML-bericht conform Contract K-01.
    Bevat nu een volledige <User> entiteit voor on-demand provisioning (US-11).

    Verplichte velden: orderId, User (nested), amount, currency, orderedAt, items
    """
    root = ET.Element('InvoiceRequested')

    ET.SubElement(root, 'orderId').text = str(invoice_data.get('orderId', ''))
    
    # Voeg User toe via bestaande builder-logica
    user_data = invoice_data.get('user', {})
    user_el = ET.SubElement(root, 'User')
    ET.SubElement(user_el, 'userId').text = str(user_data.get('userId', ''))
    ET.SubElement(user_el, 'firstName').text = str(user_data.get('firstName', ''))
    ET.SubElement(user_el, 'lastName').text = str(user_data.get('lastName', ''))
    ET.SubElement(user_el, 'email').text = str(user_data.get('email', ''))
    
    # Optioneel: companyId (meestal afwezig voor K-01)
    if user_data.get('companyId'):
        ET.SubElement(user_el, 'companyId').text = str(user_data['companyId'])
        
    ET.SubElement(user_el, 'badgeCode').text = str(user_data.get('badgeCode', ''))
    ET.SubElement(user_el, 'role').text = str(user_data.get('role', ''))

    ET.SubElement(root, 'amount').text = str(invoice_data.get('amount', '0'))
    ET.SubElement(root, 'currency').text = 'EUR'
    ET.SubElement(root, 'orderedAt').text = str(invoice_data.get('orderedAt') or _now_iso())

    items_el = ET.SubElement(root, 'items')
    for item in invoice_data.get('items', []):
        item_el = ET.SubElement(items_el, 'item')
        ET.SubElement(item_el, 'productName').text = str(item.get('productName', ''))
        ET.SubElement(item_el, 'quantity').text = str(item.get('quantity', ''))
        ET.SubElement(item_el, 'unitPrice').text = str(item.get('unitPrice', ''))

    if invoice_data.get('paymentReference'):
        ET.SubElement(root, 'paymentReference').text = str(invoice_data['paymentReference'])

    return ET.tostring(root, encoding='unicode')


def _build_user_created_xml(user_data: dict) -> str:
    """Bouw een UserCreated XML conform kassa-schema-v1.xsd <UserCreated>."""
    root = ET.Element('UserCreated')

    ET.SubElement(root, 'userId').text = str(user_data.get('userId', ''))
    ET.SubElement(root, 'firstName').text = str(user_data.get('firstName', ''))
    ET.SubElement(root, 'lastName').text = str(user_data.get('lastName', ''))
    ET.SubElement(root, 'email').text = str(user_data.get('email', ''))

    company_id = user_data.get('companyId')
    if company_id:
        ET.SubElement(root, 'companyId').text = str(company_id)

    ET.SubElement(root, 'badgeCode').text = str(user_data.get('badgeCode', ''))
    ET.SubElement(root, 'role').text = str(user_data.get('role', ''))
    ET.SubElement(root, 'createdAt').text = str(user_data.get('createdAt') or _now_iso())

    return ET.tostring(root, encoding='unicode')


def _build_user_updated_integration_xml(user_data: dict) -> str:
    """Bouw een UserUpdatedIntegration XML conform kassa-schema-v1.xsd <UserUpdatedIntegration>."""
    root = ET.Element('UserUpdatedIntegration')

    ET.SubElement(root, 'userId').text = str(user_data.get('userId', ''))
    ET.SubElement(root, 'firstName').text = str(user_data.get('firstName', ''))
    ET.SubElement(root, 'lastName').text = str(user_data.get('lastName', ''))
    ET.SubElement(root, 'email').text = str(user_data.get('email', ''))

    company_id = user_data.get('companyId')
    if company_id:
        ET.SubElement(root, 'companyId').text = str(company_id)

    ET.SubElement(root, 'badgeCode').text = str(user_data.get('badgeCode', ''))
    ET.SubElement(root, 'role').text = str(user_data.get('role', ''))
    ET.SubElement(root, 'updatedAt').text = str(user_data.get('updatedAt') or _now_iso())

    return ET.tostring(root, encoding='unicode')


def _build_user_updated_xml(user_data: dict) -> str:
    """
    Build UserUpdated XML per Integration Service schema.
    Required: userId, firstName, lastName, email, badgeCode, role, updatedAt
    Optional: companyId
    """
    root = ET.Element('KassaUserUpdated')

    ET.SubElement(root, 'userId').text = str(user_data.get('userId', ''))
    ET.SubElement(root, 'firstName').text = str(user_data.get('firstName', ''))
    ET.SubElement(root, 'lastName').text = str(user_data.get('lastName', ''))
    ET.SubElement(root, 'email').text = str(user_data.get('email', ''))

    company_id = user_data.get('companyId')
    if company_id:
        ET.SubElement(root, 'companyId').text = str(company_id)

    ET.SubElement(root, 'badgeCode').text = str(user_data.get('badgeCode', ''))
    ET.SubElement(root, 'role').text = str(user_data.get('role', ''))
    ET.SubElement(root, 'updatedAt').text = str(user_data.get('updatedAt', _now_iso()))

    return ET.tostring(root, encoding='unicode')


def _build_user_deactivated_xml(user_email: str, user_id: str) -> str:
    """
    Build UserDeactivated XML per CRM Contract 22 schema.
    Required: id, email, deactivatedAt
    """
    root = ET.Element('UserDeactivated')

    ET.SubElement(root, 'id').text = str(user_id)
    ET.SubElement(root, 'email').text = str(user_email)
    ET.SubElement(root, 'deactivatedAt').text = _now_iso()

    return ET.tostring(root, encoding='unicode')


def _get_connection_params():
    try:
        import pika
        host = _rabbit_host()
        port = _rabbit_port()
        user = _rabbit_user()
        password = _rabbit_pass()
        vhost = _rabbit_vhost()
        _logger.debug(
            "RabbitMQ connection params [host=%s port=%s user=%s vhost=%s]",
            host, port, user, vhost,
        )
        credentials = pika.PlainCredentials(user, password)
        return pika.ConnectionParameters(
            host=host,
            port=port,
            virtual_host=vhost,
            credentials=credentials,
            connection_attempts=2,
            retry_delay=1,
            socket_timeout=3,
        )
    except ImportError:
        raise RuntimeError("pika library not installed. Run: pip install pika")


def _send_xml(
    xml_body: str,
    exchange: str,
    routing_key: str,
    exchange_type: str = 'topic',
    element_name: str = '',
) -> bool:
    """
    Send XML string to RabbitMQ with validation.
    Returns True on success, False on failure.
    """
    try:
        # Validate XML against schema
        if element_name:
            if not _validate_xml_with_schema(xml_body, element_name):
                _logger.error("XML validation failed for %s, message not sent", element_name)
                return False

        import pika
        params = _get_connection_params()
        connection = pika.BlockingConnection(params)
        channel = connection.channel()

        # Declare exchange (idempotent)
        channel.exchange_declare(
            exchange=exchange,
            exchange_type=exchange_type,
            durable=True,
        )

        # Publish message
        channel.basic_publish(
            exchange=exchange,
            routing_key=routing_key,
            body=xml_body.encode('utf-8'),
            properties=pika.BasicProperties(
                delivery_mode=2,  # persistent
                content_type='application/xml',
            ),
        )
        connection.close()

        _logger.info("RabbitMQ: XML published [exchange=%s routing_key=%s element=%s]",
                    exchange, routing_key, element_name)
        return True

    except Exception as e:
        _logger.error("RabbitMQ: publish failed [exchange=%s routing_key=%s error=%s]",
                     exchange, routing_key, e)
        return False


def _build_batch_closed_xml(batch_data: dict) -> str:
    """
    Bouw een BatchClosed XML-bericht conform Contract K-02 (Kassa → Facturatie).
    Schema: kassa_batch_contract.xsd

    Structuur:
      <BatchClosed>
        <batchId>    — UUID v4 (idempotency key)
        <closedAt>   — ISO8601 UTC timestamp
        <currency>   — altijd EUR
        <users>      — optioneel: afwezig als er geen invoice-orders zijn
          <user>*
            <userId>     — CRM UUID van de klant (partner.user_id_custom)
            <items>      — verplicht; minstens 1 item
              <item>*
                <productName>, <quantity>, <unitPrice>, <totalPrice>
            <totalAmount>
        <summary>    — altijd aanwezig
          <totalOrders>, <totalAmount>
          <orderIds>   — optioneel
            <orderId>*
    """
    root = ET.Element('BatchClosed')

    ET.SubElement(root, 'batchId').text = str(batch_data.get('batchId', ''))

    closed_at = batch_data.get('closedAt') or _now_iso()
    ET.SubElement(root, 'closedAt').text = str(closed_at)

    ET.SubElement(root, 'currency').text = batch_data.get('currency', 'EUR')

    # <users> — optional wrapper; only emitted when there are qualifying users
    if batch_data.get('users'):
        users_el = ET.SubElement(root, 'users')
        for user in batch_data['users']:
            user_el = ET.SubElement(users_el, 'user')

            ET.SubElement(user_el, 'userId').text = str(user.get('userId', ''))

            # <items> is REQUIRED per contract (minOccurs defaults to 1)
            items_el = ET.SubElement(user_el, 'items')
            for item in user.get('items', []):
                item_el = ET.SubElement(items_el, 'item')
                ET.SubElement(item_el, 'productName').text = str(item.get('productName', ''))
                ET.SubElement(item_el, 'quantity').text = str(item.get('quantity', '1'))
                ET.SubElement(item_el, 'unitPrice').text = f"{float(item.get('unitPrice', 0)):.2f}"
                ET.SubElement(item_el, 'totalPrice').text = f"{float(item.get('totalPrice', 0)):.2f}"

            ET.SubElement(user_el, 'totalAmount').text = f"{float(user.get('totalAmount', 0)):.2f}"

    # <summary> is always present
    summary_el = ET.SubElement(root, 'summary')
    ET.SubElement(summary_el, 'totalOrders').text = str(batch_data.get('totalOrders', 0))
    ET.SubElement(summary_el, 'totalAmount').text = f"{float(batch_data.get('totalAmount', 0)):.2f}"
    if batch_data.get('orderIds'):
        order_ids_el = ET.SubElement(summary_el, 'orderIds')
        for order_id in batch_data['orderIds']:
            ET.SubElement(order_ids_el, 'orderId').text = str(order_id)

    return ET.tostring(root, encoding='unicode')


def _send_batch_to_exchange(xml_body: str) -> bool:
    """
    Publiceer BatchClosed naar exchange kassa.topic met routing key kassa.closed.
    Geen queue_declare — Facturatie is verantwoordelijk voor hun eigen queue binding.
    """
    try:
        import pika
        params = _get_connection_params()
        connection = pika.BlockingConnection(params)
        channel = connection.channel()

        channel.exchange_declare(exchange=KASSA_TOPIC_EXCHANGE, exchange_type='topic', durable=True)
        channel.basic_publish(
            exchange=KASSA_TOPIC_EXCHANGE,
            routing_key='kassa.closed',
            body=xml_body.encode('utf-8'),
            properties=pika.BasicProperties(
                delivery_mode=2,
                content_type='application/xml',
            ),
        )
        connection.close()
        _logger.info("RabbitMQ: BatchClosed verstuurd naar %s [routing_key=kassa.closed]", KASSA_TOPIC_EXCHANGE)
        return True

    except Exception as e:
        _logger.exception("RabbitMQ: verzenden BatchClosed mislukt")
        return False


def send_batch_closed(batch_data: dict) -> bool:
    """
    Contract K-02 — Kassa → Facturatie: dagafsluiting batch.
    Bouwt en valideert de BatchClosed XML tegen kassa_batch_contract.xsd,
    daarna publiceren naar kassa.topic exchange met routing key kassa.closed.
    """
    xml = _build_batch_closed_xml(batch_data)

    # Validate against the authoritative contract schema before publishing
    try:
        from lxml import etree  # type: ignore[import-not-found]
        if BATCH_SCHEMA_PATH.exists():
            schema_doc = etree.parse(str(BATCH_SCHEMA_PATH))
            schema = etree.XMLSchema(schema_doc)
            xml_doc = etree.fromstring(xml.encode('utf-8'))
            if not schema.validate(xml_doc):
                _logger.error(
                    "BatchClosed XML failed XSD validation [schema=%s]: %s",
                    BATCH_SCHEMA_PATH,
                    schema.error_log,
                )
                return False
            _logger.debug("BatchClosed XML passed XSD validation")
        else:
            _logger.warning("Batch schema not found at %s, skipping validation", BATCH_SCHEMA_PATH)
    except ImportError:
        _logger.warning("lxml not installed, skipping XSD validation for BatchClosed. Install with: pip install lxml")
    except Exception:
        _logger.exception("Unexpected error during BatchClosed XSD validation")
        return False

    return _send_batch_to_exchange(xml)


def send_payment_confirmed(payment_data: dict) -> bool:
    """Contract 16 — Kassa → CRM: payment confirmed."""
    xml = _build_payment_confirmed_xml(payment_data)
    return _send_xml(xml, KASSA_TOPIC_EXCHANGE, QUEUE_PAYMENT_CONFIRMED, exchange_type='topic', element_name='PaymentConfirmed')


def send_invoice_requested(invoice_data: dict) -> bool:
    """Contract K-01 — Kassa → Facturatie: invoice request."""
    xml = _build_invoice_requested_xml(invoice_data)
    return _send_xml(xml, KASSA_TOPIC_EXCHANGE, QUEUE_INVOICE_REQUESTED, exchange_type='topic', element_name='InvoiceRequested')


def send_user_created(user_data: dict) -> bool:
    # Compat wrapper: route to CRM topic exchange (same as send_kassa_user_created)
    return send_kassa_user_created(user_data)


def send_user_updated(user_data: dict) -> bool:
    # Compat wrapper: route to CRM topic exchange (same as send_kassa_user_updated)
    return send_kassa_user_updated(user_data)


def send_user_deactivated(user_email: str, user_id_custom: str) -> bool:
    """
    Publish UserDeactivated to user.topic exchange with kassa.user.deactivated routing key.
    Uses user_id_custom (CRM Master UUID) as the id in the message.
    """
    # Compat wrapper: route to CRM topic exchange (same as send_kassa_user_deactivated)
    return send_kassa_user_deactivated(user_id_custom, user_email)

# ─────────────────────────────────────────────────────────────────────────────
# Kassa → CRM User Sync  (Contracts C36 / C37 / C38)
# Exchange: user.topic (topic)
# Kassa publiceert alleen naar de exchange met routing key.
# CRM declareert zelf de consumer-queues (crm.kassa.user.*).
# ─────────────────────────────────────────────────────────────────────────────

def _build_kassa_user_created_xml(user_data: dict) -> str:
    """
    C36 — Bouw een KassaUserCreated XML conform kassa-user.xsd v1.10.1.

    Verplichte velden: userId (lokale res.partner.id), firstName, lastName,
    email, badgeCode, role, createdAt
    Optioneel: companyId
    """
    root = ET.Element('KassaUserCreated')

    ET.SubElement(root, 'userId').text    = str(user_data.get('userId', ''))
    ET.SubElement(root, 'firstName').text = str(user_data.get('firstName', ''))
    ET.SubElement(root, 'lastName').text  = str(user_data.get('lastName', ''))
    ET.SubElement(root, 'email').text     = str(user_data.get('email', ''))

    company_id = user_data.get('companyId')
    if company_id:
        ET.SubElement(root, 'companyId').text = str(company_id)

    ET.SubElement(root, 'badgeCode').text  = str(user_data.get('badgeCode', ''))
    ET.SubElement(root, 'role').text       = str(user_data.get('role', ''))
    ET.SubElement(root, 'createdAt').text  = str(user_data.get('createdAt') or _now_iso())

    return ET.tostring(root, encoding='unicode')


def _build_kassa_user_updated_xml(user_data: dict) -> str:
    """
    C37 — Bouw een KassaUserUpdated XML conform kassa-user.xsd v1.10.1.

    Verplichte velden: userId, firstName, lastName, email, badgeCode, role, updatedAt
    Optioneel: companyId
    """
    root = ET.Element('KassaUserUpdated')

    ET.SubElement(root, 'userId').text    = str(user_data.get('userId', ''))
    ET.SubElement(root, 'firstName').text = str(user_data.get('firstName', ''))
    ET.SubElement(root, 'lastName').text  = str(user_data.get('lastName', ''))
    ET.SubElement(root, 'email').text     = str(user_data.get('email', ''))

    company_id = user_data.get('companyId')
    if company_id:
        ET.SubElement(root, 'companyId').text = str(company_id)

    ET.SubElement(root, 'badgeCode').text  = str(user_data.get('badgeCode', ''))
    ET.SubElement(root, 'role').text       = str(user_data.get('role', ''))
    ET.SubElement(root, 'updatedAt').text  = str(user_data.get('updatedAt') or _now_iso())

    return ET.tostring(root, encoding='unicode')


def _build_kassa_user_deactivated_xml(user_id: str, email: str) -> str:
    """
    C38 — Bouw een UserDeactivated XML conform kassa-user.xsd v1.10.1.

    Let op: root element is <UserDeactivated>, sleutelveld is <id> (niet <userId>).
    Verplichte velden: id, email, deactivatedAt
    """
    root = ET.Element('UserDeactivated')
    ET.SubElement(root, 'id').text            = str(user_id)
    ET.SubElement(root, 'email').text         = str(email)
    ET.SubElement(root, 'deactivatedAt').text = _now_iso()
    return ET.tostring(root, encoding='unicode')


def _publish_to_topic_exchange(routing_key: str, xml_body: str) -> bool:
    """
    Publiceer een XML-bericht naar user.topic exchange met de gegeven routing key.
    Declareert GEEN consumer-queues — dat is de verantwoordelijkheid van de receiver (CRM).
    Geeft True terug bij succes, False bij fout.
    """
    try:
        import pika
        params = _get_connection_params()
        connection = pika.BlockingConnection(params)
        channel = connection.channel()

        channel.exchange_declare(
            exchange=USER_TOPIC_EXCHANGE,
            exchange_type='topic',
            durable=True,
        )

        channel.basic_publish(
            exchange=USER_TOPIC_EXCHANGE,
            routing_key=routing_key,
            body=xml_body.encode('utf-8'),
            properties=pika.BasicProperties(
                delivery_mode=2,
                content_type='application/xml',
            ),
        )
        connection.close()
        _logger.info(
            "RabbitMQ: XML-bericht gepubliceerd [exchange=%s routing_key=%s]",
            USER_TOPIC_EXCHANGE, routing_key,
        )
        return True

    except Exception as e:
        _logger.exception(
            "RabbitMQ: publiceren mislukt [exchange=%s routing_key=%s element=%s]",
            USER_TOPIC_EXCHANGE,
            routing_key,
            '',
        )
        return False


def send_kassa_user_created(user_data: dict) -> bool:
    """
    Contract 36 — Kassa → CRM: user aanmaken.
    Publiceert <KassaUserCreated> naar user.topic met routing key kassa.user.created.
    userId is de lokale Odoo res.partner.id (niet de CRM UUID).
    """
    xml = _build_kassa_user_created_xml(user_data)
    return _publish_to_topic_exchange(ROUTING_KEY_KASSA_USER_CREATED, xml)


def send_kassa_user_updated(user_data: dict) -> bool:
    """
    Contract 37 — Kassa → CRM: user bijwerken.
    Publiceert <KassaUserUpdated> naar user.topic met routing key kassa.user.updated.
    CRM verwerkt de update en publiceert crm.user.updated (C18).
    """
    xml = _build_kassa_user_updated_xml(user_data)
    return _publish_to_topic_exchange(ROUTING_KEY_KASSA_USER_UPDATED, xml)


def send_kassa_user_deactivated(user_id: str, email: str) -> bool:
    """
    Contract 38 — Kassa → CRM: user deactiveren.
    Publiceert <UserDeactivated> naar user.topic met routing key kassa.user.deactivated.
    CRM voert soft delete uit in Salesforce en publiceert crm.user.deactivated (C22).

    Let op: veld is <id> (niet <userId>), conform kassa-user.xsd v1.10.1.
    """
    xml = _build_kassa_user_deactivated_xml(user_id, email)
    return _publish_to_topic_exchange(ROUTING_KEY_KASSA_USER_DEACTIVATED, xml)

