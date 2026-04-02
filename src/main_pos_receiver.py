import logging
import threading

from messaging.consumer import KassaConsumer
from config import RABBIT_HOST, CONSUMPTION_ORDER_QUEUE, PAYMENT_COMPLETED_QUEUE

"""
Receiver die berichten logt van de ConsumptionOrder- en PaymentCompleted-queues.
Deze queues worden gevuld door Odoo POS zodra een order afgerond is.

Start RabbitMQ via Docker, start daarna dit script.
Doe een verkoop in Odoo POS → je ziet de XML-berichten verschijnen.
"""

logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)


def on_consumption_order(body: bytes):
    logger.info("=== ConsumptionOrder ontvangen ===\n%s", body.decode('utf-8'))


def on_payment_completed(body: bytes):
    logger.info("=== PaymentCompleted ontvangen ===\n%s", body.decode('utf-8'))


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
                CONSUMPTION_ORDER_QUEUE, PAYMENT_COMPLETED_QUEUE)

    # Elke queue krijgt een eigen thread zodat beide tegelijk luisteren
    t1 = threading.Thread(
        target=listen_queue,
        args=(CONSUMPTION_ORDER_QUEUE, on_consumption_order),
        daemon=True,
    )
    t2 = threading.Thread(
        target=listen_queue,
        args=(PAYMENT_COMPLETED_QUEUE, on_payment_completed),
        daemon=True,
    )

    t1.start()
    t2.start()

    try:
        t1.join()
        t2.join()
    except KeyboardInterrupt:
        logger.info("POS receiver gestopt.")
