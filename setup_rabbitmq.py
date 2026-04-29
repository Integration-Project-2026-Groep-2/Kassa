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


def create_exchanges():
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
            print(f"✓ Verbonden met RabbitMQ op {host}:{port}")
            break
        except pika.exceptions.AMQPConnectionError:
            print(f"Wachten op RabbitMQ... ({attempt}/30)")
            time.sleep(2)
    else:
        print("✗ RabbitMQ niet bereikbaar na 30 pogingen")
        sys.exit(1)

    exchanges = [
        # naam                 type      durable
        ("kassa.topic",        "topic",  True),   # batch closing (Afsluitknop)
        ("kassa.direct",       "direct", True),   # overige Kassa-berichten
        ("user.direct",        "direct", True),   # interne user CRUD (integration service)
        ("user.dlx",           "direct", True),   # dead letter exchange
        ("user.retry",         "direct", True),   # retry exchange
        ("user.topic",         "topic",  True),   # C36/C37/C38 Kassa → CRM user sync
        ("heartbeat.direct",   "direct", True),   # heartbeat (Contract 7)
    ]

    for name, kind, durable in exchanges:
        try:
            channel.exchange_declare(
                exchange=name,
                exchange_type=kind,
                durable=durable,
                auto_delete=False,
            )
            print(f"✓ Exchange '{name}' ({kind}) aangemaakt/geverifieerd")
        except Exception as exc:
            print(f"⚠  Waarschuwing voor '{name}': {exc}")

    connection.close()
    print("\n✓ Alle exchanges zijn klaar.")
    return 0


if __name__ == "__main__":
    sys.exit(create_exchanges())
