# -*- coding: utf-8 -*-

import json
import logging
import os

_logger = logging.getLogger(__name__)

RABBITMQ_HOST = os.environ.get('RABBITMQ_HOST', 'localhost')
RABBITMQ_PORT = int(os.environ.get('RABBITMQ_PORT', 5672))
RABBITMQ_USER = os.environ.get('RABBITMQ_USER', 'guest')
RABBITMQ_PASS = os.environ.get('RABBITMQ_PASS', 'guest')
RABBITMQ_VHOST = os.environ.get('RABBITMQ_VHOST', '/')

QUEUE_CONSUMPTION_ORDER = 'ConsumptionOrder'
QUEUE_PAYMENT_COMPLETED = 'PaymentCompleted'


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


def send_message(queue_name, payload: dict):
    """
    Stuur een bericht naar een RabbitMQ queue.
    payload: dict die automatisch naar JSON wordt omgezet.
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
            body=json.dumps(payload, default=str),
            properties=pika.BasicProperties(
                delivery_mode=2,  # persistent message
                content_type='application/json',
            ),
        )
        connection.close()
        _logger.info("RabbitMQ: bericht verstuurd naar queue '%s'", queue_name)
        return True

    except Exception as e:
        _logger.error("RabbitMQ: verzenden mislukt naar queue '%s': %s", queue_name, e)
        return False


def send_consumption_order(order_data: dict):
    return send_message(QUEUE_CONSUMPTION_ORDER, order_data)


def send_payment_completed(payment_data: dict):
    return send_message(QUEUE_PAYMENT_COMPLETED, payment_data)
