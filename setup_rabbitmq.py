#!/usr/bin/env python3
"""
Setup script — declareert alle RabbitMQ exchanges voor het Kassa-systeem.
Wordt automatisch uitgevoerd via de rabbitmq-setup service in docker-compose.yml.
Kan ook handmatig gedraaid worden: python setup_rabbitmq.py
"""

import os
import pika
import sys
import time
import logging

from src.logging_config import configure_logging

# Configure logging for this script
configure_logging()


USER_QUEUE_BINDINGS = [
    ("kassa.user.confirmed", "crm.user.confirmed"),
    ("kassa.user.updated", "crm.user.updated"),
    ("kassa.user.deactivated", "crm.user.deactivated"),
]


def create_exchanges():
    """Create all required exchanges for Kassa system."""

    host     = os.environ.get('RABBIT_HOST', 'localhost')
    port     = int(os.environ.get('RABBIT_PORT', 5672))
    user     = os.environ.get('RABBIT_USER', 'guest')
    password = os.environ.get('RABBIT_PASSWORD', 'guest')
    vhost    = os.environ.get('RABBIT_VHOST', '/')

    # Wacht tot RabbitMQ bereikbaar is
    for attempt in range(1, 31):
        try:
            credentials = pika.PlainCredentials(user, password)
            parameters  = pika.ConnectionParameters(
                host=host, port=port, virtual_host=vhost,
                credentials=credentials, connection_attempts=1,
            )
            connection = pika.BlockingConnection(parameters)
            channel    = connection.channel()
            logging.getLogger(__name__).info("✓ Verbonden met RabbitMQ op %s:%s", host, port)
            break
        except pika.exceptions.AMQPConnectionError:
            logging.getLogger(__name__).info("Wachten op RabbitMQ... (%d/30)", attempt)
            time.sleep(2)
    else:
        logging.getLogger(__name__).error("✗ RabbitMQ niet bereikbaar na 30 pogingen")
        sys.exit(1)

    exchanges = [
        # naam                 type      durable
        ("kassa.topic",        "topic",  True),   # batch closing (Afsluitknop)
        ("user.direct",        "direct", True),   # interne user CRUD (integration service)
        ("user.dlx",           "direct", True),   # dead letter exchange
        ("user.retry",         "direct", True),   # retry exchange
        ("user.topic",         "topic",  True),   # C36/C37/C38 Kassa → CRM user sync
        ("heartbeat.direct",   "direct", True),   # heartbeat (Contract 7)
        ("statuscheck.direct", "direct", True),   # statuscheck (Contract 8)
        ("logs.direct",        "direct", True),   # Controlroom centralized logs (ClickUp 2kyr1d3m-7235)
        ("user.checkin.topic", "topic",  True),   # IoT QR-scanner check-in berichten
    ]

    for name, kind, durable in exchanges:
        try:
            channel.exchange_declare(
                exchange=name,
                exchange_type=kind,
                durable=durable,
                auto_delete=False,
            )
            logging.getLogger(__name__).info("✓ Exchange '%s' (%s) aangemaakt/geverifieerd", name, kind)
        except Exception as exc:
            logging.getLogger(__name__).warning("⚠  Waarschuwing voor '%s': %s", name, exc)

    connection.close()
    logging.getLogger(__name__).info("\n✓ Alle exchanges zijn klaar.")
    return 0


if __name__ == "__main__":
    sys.exit(create_exchanges())
