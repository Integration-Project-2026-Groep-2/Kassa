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

# User events: topic-based routing (Salesforce CRM integration)
USER_EVENTS_EXCHANGE = 'user.topic'
USER_EVENTS_EXCHANGE_TYPE = 'topic'

# Queue names for payment and invoice (non-user-event messages)
QUEUE_PAYMENT_CONFIRMED = 'kassa.payment.confirmed'   # Contract 16 → CRM
QUEUE_INVOICE_REQUESTED = 'kassa.invoice.requested'   # Contract K-01 → Facturatie

# XSD schema path for validation
SCHEMA_PATH = os.environ.get('SCHEMA_PATH', 'src/schema/kassa-schema-v1.xsd')


def _now_iso() -> str:
    return datetime.datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')


def _validate_xml_with_schema(xml_str: str, element_name: str) -> bool:
    """
    Validate XML against the kassa-schema-v1.xsd.
    Returns True if valid, False if validation fails.
    Logs errors appropriately.
    """
    try:
        from lxml import etree
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
    """
    Build UserCreated XML per Integration Service schema.
    Required: userId, firstName, lastName, email, badgeCode, role, createdAt
    Optional: companyId
    """
    root = ET.Element('KassaUserCreated')

    ET.SubElement(root, 'userId').text = str(user_data.get('userId', ''))
    ET.SubElement(root, 'firstName').text = str(user_data.get('firstName', ''))
    ET.SubElement(root, 'lastName').text = str(user_data.get('lastName', ''))
    ET.SubElement(root, 'email').text = str(user_data.get('email', ''))

    company_id = user_data.get('companyId')
    if company_id:
        ET.SubElement(root, 'companyId').text = str(company_id)

    ET.SubElement(root, 'badgeCode').text = str(user_data.get('badgeCode', ''))
    ET.SubElement(root, 'role').text = str(user_data.get('role', ''))
    ET.SubElement(root, 'createdAt').text = str(user_data.get('createdAt', _now_iso()))

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


def send_payment_confirmed(payment_data: dict) -> bool:
    """Contract 16 — Kassa → CRM: payment confirmed."""
    xml = _build_payment_confirmed_xml(payment_data)
    return _send_xml(xml, '', QUEUE_PAYMENT_CONFIRMED, exchange_type='direct', element_name='PaymentConfirmed')


def send_invoice_requested(invoice_data: dict) -> bool:
    """Contract K-01 — Kassa → Facturatie: invoice request."""
    xml = _build_invoice_requested_xml(invoice_data)
    return _send_xml(xml, '', QUEUE_INVOICE_REQUESTED, exchange_type='direct', element_name='InvoiceRequested')


def send_user_created(user_data: dict) -> bool:
    """
    Publish UserCreated to user.topic exchange with kassa.user.created routing key.
    user_data should contain: userId (Odoo id), firstName, lastName, email, badgeCode, role, companyId (opt), createdAt
    """
    xml = _build_user_created_xml(user_data)
    return _send_xml(
        xml,
        exchange=USER_EVENTS_EXCHANGE,
        routing_key='kassa.user.created',
        exchange_type=USER_EVENTS_EXCHANGE_TYPE,
        element_name='KassaUserCreated',
    )


def send_user_updated(user_data: dict) -> bool:
    """
    Publish UserUpdated to user.topic exchange with kassa.user.updated routing key.
    user_data should contain: userId (user_id_custom - CRM Master UUID), firstName, lastName, email, badgeCode, role, companyId (opt), updatedAt
    """
    xml = _build_user_updated_xml(user_data)
    return _send_xml(
        xml,
        exchange=USER_EVENTS_EXCHANGE,
        routing_key='kassa.user.updated',
        exchange_type=USER_EVENTS_EXCHANGE_TYPE,
        element_name='KassaUserUpdated',
    )


def send_user_deactivated(user_email: str, user_id_custom: str) -> bool:
    """
    Publish UserDeactivated to user.topic exchange with kassa.user.deactivated routing key.
    Uses user_id_custom (CRM Master UUID) as the id in the message.
    """
    xml = _build_user_deactivated_xml(user_email, user_id_custom)
    return _send_xml(
        xml,
        exchange=USER_EVENTS_EXCHANGE,
        routing_key='kassa.user.deactivated',
        exchange_type=USER_EVENTS_EXCHANGE_TYPE,
        element_name='UserDeactivated',
    )


