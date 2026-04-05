import logging
import threading

from messaging.consumer import KassaConsumer
from config import RABBIT_HOST, PAYMENT_CONFIRMED_QUEUE, INVOICE_REQUESTED_QUEUE

"""
Test-receiver die berichten logt van de queues die Kassa publiceert.
Start RabbitMQ via Docker, start daarna dit script.
Doe een verkoop in Odoo POS → je ziet de XML-berichten verschijnen.
"""

logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)


def on_payment_confirmed(body: bytes):
    logger.info("=== PaymentConfirmed ontvangen (Contract 16) ===\n%s", body.decode('utf-8'))


def on_invoice_requested(body: bytes):
    logger.info("=== InvoiceRequested ontvangen (Contract K-01) ===\n%s", body.decode('utf-8'))


def listen_queue(queue_name: str, callback):
    """Start een consumer voor één queue in een aparte thread."""
    consumer = KassaConsumer(host=RABBIT_HOST)
    consumer.connect()
    try:
        consumer.start_listening(queue_name=queue_name, callback=callback)
    except KeyboardInterrupt:
        pass
    finally:
        consumer.close()


if __name__ == "__main__":
    logger.info("POS receiver gestart. Luistert op '%s' en '%s'...",
                PAYMENT_CONFIRMED_QUEUE, INVOICE_REQUESTED_QUEUE)

    t1 = threading.Thread(
        target=listen_queue,
        args=(PAYMENT_CONFIRMED_QUEUE, on_payment_confirmed),
        daemon=True,
    )
    t2 = threading.Thread(
        target=listen_queue,
        args=(INVOICE_REQUESTED_QUEUE, on_invoice_requested),
        daemon=True,
    )

    t1.start()
    t2.start()

    try:
        t1.join()
        t2.join()
    except KeyboardInterrupt:
        logger.info("POS receiver gestopt.")
