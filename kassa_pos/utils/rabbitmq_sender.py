# -*- coding: utf-8 -*-

import datetime
import logging
import os
import xml.etree.ElementTree as ET

_logger = logging.getLogger(__name__)

# RabbitMQ-verbindingsinstellingen komen uit omgevingsvariabelen (zie docker-compose.yml)
RABBITMQ_HOST = os.environ.get('RABBIT_HOST') or os.environ.get('RABBITMQ_HOST', 'localhost')
RABBITMQ_PORT = int(os.environ.get('RABBIT_PORT') or os.environ.get('RABBITMQ_PORT', 5672))
RABBITMQ_USER = os.environ.get('RABBIT_USER') or os.environ.get('RABBITMQ_USER', 'guest')
RABBITMQ_PASS = os.environ.get('RABBIT_PASSWORD') or os.environ.get('RABBITMQ_PASS', 'guest')
RABBITMQ_VHOST = os.environ.get('RABBIT_VHOST') or os.environ.get('RABBITMQ_VHOST', '/')
USER_EVENTS_EXCHANGE = os.environ.get('USER_EVENTS_EXCHANGE', 'user.direct')
USER_EVENTS_EXCHANGE_TYPE = os.environ.get('USER_EVENTS_EXCHANGE_TYPE', 'direct')
USER_EVENTS_DLX_EXCHANGE = os.environ.get('USER_EVENTS_DLX_EXCHANGE', 'user.dlx')
USER_EVENTS_RETRY_EXCHANGE = os.environ.get('USER_EVENTS_RETRY_EXCHANGE', 'user.retry')
USER_EVENTS_RETRY_TTL_MS = int(os.environ.get('USER_EVENTS_RETRY_TTL_MS', '15000'))

# Queue namen conform Team Kassa contractoverzicht
QUEUE_PAYMENT_CONFIRMED = 'kassa.payment.confirmed'   # Contract 16 → CRM
QUEUE_INVOICE_REQUESTED = 'kassa.invoice.requested'   # Contract K-01 → Facturatie
QUEUE_USER_CREATED = 'integration.user.created'
QUEUE_USER_UPDATED = 'integration.user.updated'
QUEUE_USER_DELETED = 'integration.user.deleted'


def _now_iso() -> str:
    return datetime.datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')


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


def _build_user_xml(user_data: dict) -> str:
    root = ET.Element('User')

    ET.SubElement(root, 'userId').text = str(user_data.get('userId', ''))
    ET.SubElement(root, 'firstName').text = str(user_data.get('firstName', ''))
    ET.SubElement(root, 'lastName').text = str(user_data.get('lastName', ''))
    ET.SubElement(root, 'email').text = str(user_data.get('email', ''))

    company_id = user_data.get('companyId')
    if company_id:
        ET.SubElement(root, 'companyId').text = str(company_id)

    ET.SubElement(root, 'badgeCode').text = str(user_data.get('badgeCode', ''))
    ET.SubElement(root, 'role').text = str(user_data.get('role', ''))

    created_at = user_data.get('createdAt')
    if created_at:
        ET.SubElement(root, 'createdAt').text = str(created_at)

    updated_at = user_data.get('updatedAt')
    if updated_at:
        ET.SubElement(root, 'updatedAt').text = str(updated_at)

    return ET.tostring(root, encoding='unicode')


def _build_user_deleted_xml(user_id: str) -> str:
    root = ET.Element('UserDeleted')
    ET.SubElement(root, 'userId').text = str(user_id)
    ET.SubElement(root, 'deletedAt').text = _now_iso()
    return ET.tostring(root, encoding='unicode')


def _declare_user_topology(channel, queue_name: str, routing_key: str):
    """Declare user CRUD exchange, retry and DLQ topology idempotently.

    Primary queue declaration is kept argument-free for compatibility with
    legacy queues. Dead-letter behavior is provided via broker policy.
    """
    retry_queue = f"{queue_name}.retry"
    dlq_queue = f"{queue_name}.dlq"
    retry_routing_key = f"{routing_key}.retry"
    dlq_routing_key = f"{routing_key}.dlq"

    channel.exchange_declare(
        exchange=USER_EVENTS_EXCHANGE,
        exchange_type=USER_EVENTS_EXCHANGE_TYPE,
        durable=True,
    )
    channel.exchange_declare(exchange=USER_EVENTS_DLX_EXCHANGE, exchange_type='direct', durable=True)
    channel.exchange_declare(exchange=USER_EVENTS_RETRY_EXCHANGE, exchange_type='direct', durable=True)

    channel.queue_declare(queue=queue_name, durable=True)

    channel.queue_bind(queue=queue_name, exchange=USER_EVENTS_EXCHANGE, routing_key=routing_key)

    channel.queue_declare(
        queue=retry_queue,
        durable=True,
        arguments={
            'x-message-ttl': USER_EVENTS_RETRY_TTL_MS,
            'x-dead-letter-exchange': USER_EVENTS_EXCHANGE,
            'x-dead-letter-routing-key': routing_key,
        },
    )
    channel.queue_bind(queue=retry_queue, exchange=USER_EVENTS_RETRY_EXCHANGE, routing_key=retry_routing_key)

    channel.queue_declare(queue=dlq_queue, durable=True)
    channel.queue_bind(queue=dlq_queue, exchange=USER_EVENTS_DLX_EXCHANGE, routing_key=dlq_routing_key)
    # Also bind on original routing key so policy-based DLX on existing queues
    # can route messages without requiring queue recreation.
    channel.queue_bind(queue=dlq_queue, exchange=USER_EVENTS_DLX_EXCHANGE, routing_key=routing_key)

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
    queue_name: str,
    xml_body: str,
    exchange: str = '',
    routing_key: str | None = None,
    exchange_type: str = 'direct',
) -> bool:
    """
    Stuur een XML-string naar een RabbitMQ queue.
    Geeft True terug bij succes, False bij fout.
    """
    try:
        import pika
        params = _get_connection_params()
        connection = pika.BlockingConnection(params)
        channel = connection.channel()

        channel.queue_declare(queue=queue_name, durable=True)

        publish_routing_key = routing_key or queue_name
        if exchange:
            channel.exchange_declare(exchange=exchange, exchange_type=exchange_type, durable=True)
            channel.queue_bind(queue=queue_name, exchange=exchange, routing_key=publish_routing_key)

            if exchange == USER_EVENTS_EXCHANGE:
                _declare_user_topology(channel, queue_name, publish_routing_key)

        channel.basic_publish(
            exchange=exchange,
            routing_key=publish_routing_key,
            body=xml_body.encode('utf-8'),
            properties=pika.BasicProperties(
                delivery_mode=2,        # persistent: bericht overleeft RabbitMQ herstart
                content_type='application/xml',
            ),
        )
        connection.close()
        _logger.info("RabbitMQ: XML-bericht verstuurd naar queue '%s'", queue_name)
        return True

    except Exception as e:
        _logger.error("RabbitMQ: verzenden mislukt naar queue '%s': %s", queue_name, e)
        return False


def send_payment_confirmed(payment_data: dict) -> bool:
    """
    Contract 16 — Kassa → CRM: betaling bevestigd.
    Stuur PaymentConfirmed XML naar kassa.payment.confirmed.
    """
    xml = _build_payment_confirmed_xml(payment_data)
    return _send_xml(QUEUE_PAYMENT_CONFIRMED, xml)


def send_invoice_requested(invoice_data: dict) -> bool:
    """
    Contract K-01 — Kassa → Facturatie: factuurverzoek bedrijfstransactie.
    Stuur InvoiceRequested XML naar kassa.invoice.requested.
    Alleen gebruiken als paymentType=Invoice en de klant gelinkt is aan een bedrijf.
    """
    xml = _build_invoice_requested_xml(invoice_data)
    return _send_xml(QUEUE_INVOICE_REQUESTED, xml)


def send_user_created(user_data: dict) -> bool:
    xml = _build_user_xml(user_data)
    return _send_xml(
        QUEUE_USER_CREATED,
        xml,
        exchange=USER_EVENTS_EXCHANGE,
        routing_key='integration.user.created',
        exchange_type=USER_EVENTS_EXCHANGE_TYPE,
    )


def send_user_updated(user_data: dict) -> bool:
    xml = _build_user_xml(user_data)
    return _send_xml(
        QUEUE_USER_UPDATED,
        xml,
        exchange=USER_EVENTS_EXCHANGE,
        routing_key='integration.user.updated',
        exchange_type=USER_EVENTS_EXCHANGE_TYPE,
    )


def send_user_deleted(user_id: str) -> bool:
    xml = _build_user_deleted_xml(user_id)
    return _send_xml(
        QUEUE_USER_DELETED,
        xml,
        exchange=USER_EVENTS_EXCHANGE,
        routing_key='integration.user.deleted',
        exchange_type=USER_EVENTS_EXCHANGE_TYPE,
    )
