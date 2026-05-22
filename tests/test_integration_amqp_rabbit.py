import os
import time
import threading
import pika
from testcontainers.rabbitmq import RabbitMqContainer


def test_rabbitmq_roundtrip():
    """Start a RabbitMQ container, publish a message with KassaProducer and
    consume it with a raw pika consumer to verify end-to-end wiring.
    This test requires Docker and is intended for manual/CI run via
    `RUN_INTEGRATION=1` or the `integration-tests` workflow.
    """
    # Start RabbitMQ container
    with RabbitMqContainer("rabbitmq:3.8-management") as c:
        host = c.get_container_host_ip()
        port = int(c.get_exposed_port(5672))

        # Provide environment variables before importing modules that read them
        os.environ["RABBIT_HOST"] = host
        os.environ["RABBIT_PORT"] = str(port)
        os.environ["RABBIT_USER"] = "guest"
        os.environ["RABBIT_PASSWORD"] = "guest"

        # Import here so settings picks up the env vars
        from src.connection import RabbitManager
        from messaging.producer import KassaProducer

        # Connect manager and declare a queue
        mgr = RabbitManager(host=host, port=port, user="guest", password="guest")
        mgr.connect(max_retries=10)

        # Consumer thread using pika direct connection
        received = []

        def consumer_thread():
            params = pika.ConnectionParameters(host=host, port=port, virtual_host='/', credentials=pika.PlainCredentials('guest', 'guest'))
            conn = pika.BlockingConnection(params)
            ch = conn.channel()
            ch.queue_declare(queue='int-test-queue', durable=True)

            for method_frame, properties, body in ch.consume('int-test-queue', inactivity_timeout=10):
                if body:
                    received.append(body.decode('utf-8'))
                    ch.basic_ack(method_frame.delivery_tag)
                    break
            try:
                ch.cancel()
            except Exception:
                pass
            conn.close()

        t = threading.Thread(target=consumer_thread, daemon=True)
        t.start()

        # Give consumer time to start
        time.sleep(1)

        prod = KassaProducer(host=host)
        prod._manager = mgr
        prod.publish('hello-integration', routing_key='int-test-queue', queue_name='int-test-queue', declare_queue=True)

        # Wait for consumer to receive
        t.join(timeout=15)
        assert 'hello-integration' in received
