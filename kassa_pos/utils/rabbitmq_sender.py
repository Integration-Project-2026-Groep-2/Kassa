# -*- coding: utf-8 -*-

import datetime
import logging
import os
import xml.etree.ElementTree as ET

_logger = logging.getLogger(__name__)

# RabbitMQ-verbindingsinstellingen komen uit omgevingsvariabelen (zie docker-compose.yml)
RABBITMQ_HOST = os.environ.get('RABBITMQ_HOST', 'localhost')
RABBITMQ_PORT = int(os.environ.get('RABBITMQ_PORT', 5672))
RABBITMQ_USER = os.environ.get('RABBITMQ_USER', 'guest')
RABBITMQ_PASS = os.environ.get('RABBITMQ_PASS', 'guest')
RABBITMQ_VHOST = os.environ.get('RABBITMQ_VHOST', '/')

QUEUE_CONSUMPTION_ORDER = 'ConsumptionOrder'
QUEUE_PAYMENT_COMPLETED = 'PaymentCompleted'


def _now_iso() -> str:
    return datetime.datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')


def _build_consumption_order_xml(order_data: dict) -> str:
    """Zet een order_data dict om naar een ConsumptionOrder XML-string."""
    root = ET.Element('ConsumptionOrder')

    ET.SubElement(root, 'orderId').text = str(order_data.get('orderId', ''))
    ET.SubElement(root, 'userId').text = str(order_data.get('userId', ''))

    items_el = ET.SubElement(root, 'items')
    for item in order_data.get('items', []):
        item_el = ET.SubElement(items_el, 'item')
        ET.SubElement(item_el, 'productName').text = str(item.get('productName', ''))
        ET.SubElement(item_el, 'quantity').text = str(item.get('quantity', ''))
        ET.SubElement(item_el, 'price').text = str(item.get('price', ''))

    ET.SubElement(root, 'totalAmount').text = str(order_data.get('totalAmount', ''))
    ET.SubElement(root, 'paymentType').text = str(order_data.get('paymentType', ''))
    ET.SubElement(root, 'timestamp').text = str(order_data.get('timestamp') or _now_iso())

    return ET.tostring(root, encoding='unicode')


def _build_payment_completed_xml(payment_data: dict) -> str:
    """Zet een payment_data dict om naar een PaymentCompleted XML-string."""
    root = ET.Element('PaymentCompleted')

    ET.SubElement(root, 'paymentId').text = str(payment_data.get('paymentId', ''))
    ET.SubElement(root, 'orderId').text = str(payment_data.get('orderId', ''))
    ET.SubElement(root, 'userId').text = str(payment_data.get('userId', ''))
    ET.SubElement(root, 'paymentMethod').text = str(payment_data.get('paymentMethod', ''))
    ET.SubElement(root, 'amount').text = str(payment_data.get('amount', ''))
    ET.SubElement(root, 'timestamp').text = str(payment_data.get('timestamp') or _now_iso())

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


def _send_xml(queue_name: str, xml_body: str) -> bool:
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

        channel.basic_publish(
            exchange='',
            routing_key=queue_name,
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


def send_consumption_order(order_data: dict) -> bool:
    """Bouw ConsumptionOrder XML en stuur naar RabbitMQ."""
    xml = _build_consumption_order_xml(order_data)
    return _send_xml(QUEUE_CONSUMPTION_ORDER, xml)


def send_payment_completed(payment_data: dict) -> bool:
    """Bouw PaymentCompleted XML en stuur naar RabbitMQ."""
    xml = _build_payment_completed_xml(payment_data)
    return _send_xml(QUEUE_PAYMENT_COMPLETED, xml)
