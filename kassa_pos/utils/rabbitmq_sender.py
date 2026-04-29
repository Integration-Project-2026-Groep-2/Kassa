# -*- coding: utf-8 -*-

import datetime
import logging
import os
import xml.etree.ElementTree as ET
from pathlib import Path

_logger = logging.getLogger(__name__)

# RabbitMQ connection settings from environment variables
RABBITMQ_HOST = os.environ.get('RABBIT_HOST') or os.environ.get('RABBITMQ_HOST', 'localhost')
RABBITMQ_PORT = int(os.environ.get('RABBIT_PORT') or os.environ.get('RABBITMQ_PORT', 5672))
RABBITMQ_USER = os.environ.get('RABBIT_USER') or os.environ.get('RABBITMQ_USER', 'guest')
RABBITMQ_PASS = os.environ.get('RABBIT_PASSWORD') or os.environ.get('RABBITMQ_PASS', 'guest')
RABBITMQ_VHOST = os.environ.get('RABBIT_VHOST') or os.environ.get('RABBITMQ_VHOST', '/')
SCHEMA_PATH = Path(__file__).resolve().parents[2] / 'src' / 'schema' / 'kassa-schema-v1.xsd'

# user.topic exchange — gedeeld met CRM, Facturatie, Mailing, Planning
USER_TOPIC_EXCHANGE = os.environ.get('USER_TOPIC_EXCHANGE', 'user.topic')

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
        _logger.warning("lxml not installed, skipping XSD validation. Install with: pip install lxml")
        return True

    try:
        # Find schema file
        schema_file = SCHEMA_PATH
        if not os.path.isabs(schema_file):
            # Try relative to module root
            module_dir = Path(__file__).parent.parent.parent
            schema_file = module_dir / SCHEMA_PATH
        
        if not os.path.exists(schema_file):
            _logger.warning("Schema file not found at %s, skipping validation", schema_file)
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
            _logger.error("XSD validation failed for %s: %s", element_name, schema.error_log)
            return False
            
    except Exception as e:
        _logger.error("XSD validation error for %s: %s", element_name, e)
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

    Verplichte velden: orderId, userId, companyId, amount, currency, orderedAt, items
    Optionele velden: email, companyName, eventId, paymentReference
    Items: productName, quantity, unitPrice (per item)
    """
    root = ET.Element('InvoiceRequested')

    ET.SubElement(root, 'orderId').text = str(invoice_data.get('orderId', ''))
    ET.SubElement(root, 'userId').text = str(invoice_data.get('userId', ''))
    ET.SubElement(root, 'companyId').text = str(invoice_data.get('companyId', ''))
    ET.SubElement(root, 'amount').text = str(invoice_data.get('amount', '0'))
    ET.SubElement(root, 'currency').text = 'EUR'
    ET.SubElement(root, 'orderedAt').text = str(invoice_data.get('orderedAt') or _now_iso())

    items_el = ET.SubElement(root, 'items')
    for item in invoice_data.get('items', []):
        item_el = ET.SubElement(items_el, 'item')
        ET.SubElement(item_el, 'productName').text = str(item.get('productName', ''))
        ET.SubElement(item_el, 'quantity').text = str(item.get('quantity', ''))
        ET.SubElement(item_el, 'unitPrice').text = str(item.get('unitPrice', ''))

    if invoice_data.get('email'):
        ET.SubElement(root, 'email').text = str(invoice_data['email'])
    if invoice_data.get('companyName'):
        ET.SubElement(root, 'companyName').text = str(invoice_data['companyName'])
    if invoice_data.get('eventId'):
        ET.SubElement(root, 'eventId').text = str(invoice_data['eventId'])
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
        credentials = pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASS)
        return pika.ConnectionParameters(
            host=RABBITMQ_HOST,
            port=RABBITMQ_PORT,
            virtual_host=RABBITMQ_VHOST,
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
    Alleen Invoice-orders van geïdentificeerde klanten, gegroepeerd per userId.
    """
    root = ET.Element('BatchClosed')

    ET.SubElement(root, 'batchId').text = str(batch_data.get('batchId', ''))

    closed_at = batch_data.get('closedAt') or _now_iso()
    ET.SubElement(root, 'closedAt').text = str(closed_at)

    ET.SubElement(root, 'currency').text = batch_data.get('currency', 'EUR')

    if batch_data.get('users'):
        users_el = ET.SubElement(root, 'users')
        for user in batch_data['users']:
            user_el = ET.SubElement(users_el, 'user')
            ET.SubElement(user_el, 'userId').text = str(user.get('userId', ''))
            if user.get('items'):
                items_el = ET.SubElement(user_el, 'items')
                for item in user['items']:
                    item_el = ET.SubElement(items_el, 'item')
                    ET.SubElement(item_el, 'productName').text = str(item.get('productName', ''))
                    ET.SubElement(item_el, 'quantity').text = str(item.get('quantity', '0'))
                    ET.SubElement(item_el, 'unitPrice').text = f"{float(item.get('unitPrice', 0)):.2f}"
                    ET.SubElement(item_el, 'totalPrice').text = f"{float(item.get('totalPrice', 0)):.2f}"
            ET.SubElement(user_el, 'totalAmount').text = f"{float(user.get('totalAmount', 0)):.2f}"

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

        channel.exchange_declare(exchange='kassa.topic', exchange_type='topic', durable=True)
        channel.basic_publish(
            exchange='kassa.topic',
            routing_key='kassa.closed',
            body=xml_body.encode('utf-8'),
            properties=pika.BasicProperties(
                delivery_mode=2,
                content_type='application/xml',
            ),
        )
        connection.close()
        _logger.info("RabbitMQ: BatchClosed verstuurd naar kassa.topic [routing_key=kassa.closed]")
        return True

    except Exception as e:
        _logger.error("RabbitMQ: verzenden BatchClosed mislukt: %s", e)
        return False


def send_batch_closed(batch_data: dict) -> bool:
    """
    Contract K-02 — Kassa → Facturatie: dagafsluiting batch.
    Publiceert BatchClosed XML naar exchange kassa.topic, routing key kassa.closed.
    Alleen Invoice-orders van klanten met een CRM UUID.
    """
    xml = _build_batch_closed_xml(batch_data)
    return _send_batch_to_exchange(xml)


def send_payment_confirmed(payment_data: dict) -> bool:
    """Contract 16 — Kassa → CRM: payment confirmed."""
    xml = _build_payment_confirmed_xml(payment_data)
    return _send_xml(xml, '', QUEUE_PAYMENT_CONFIRMED, exchange_type='direct', element_name='PaymentConfirmed')


def send_invoice_requested(invoice_data: dict) -> bool:
    """Contract K-01 — Kassa → Facturatie: invoice request."""
    xml = _build_invoice_requested_xml(invoice_data)
    return _send_xml(xml, '', QUEUE_INVOICE_REQUESTED, exchange_type='direct', element_name='InvoiceRequested')


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

    Verplichte velden: userId, firstName, lastName, email, badgeCode, role, createdAt
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
        _logger.error(
            "RabbitMQ: publiceren mislukt [exchange=%s routing_key=%s]: %r",
            USER_TOPIC_EXCHANGE, routing_key, e,
        )
        raise e
        return False


def send_kassa_user_created(user_data: dict) -> bool:
    """
    Contract 36 — Kassa → CRM: user aanmaken.
    Publiceert <KassaUserCreated> naar user.topic met routing key kassa.user.created.
    CRM kent daarna een canonical CRM UUID toe en publiceert crm.user.confirmed.
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

