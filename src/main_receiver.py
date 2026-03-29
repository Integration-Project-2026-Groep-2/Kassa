import logging

from messaging.consumer import KassaConsumer
from config import RABBIT_HOST, HEARTBEAT_QUEUE


"""
Receiver die berichten logt van de heartbeat-queue.

Start deze in een terminal; start daarna `main_heartbeat.py` in een andere
terminal om te zien binnenkomende heartbeats.
"""

logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)


def on_message(body: bytes):
    try:
        payload = body.decode('utf-8')
    except Exception:
        payload = str(body)
    logger.info("Nieuw bericht ontvangen:\n%s", payload)


def run_receiver():
    consumer = KassaConsumer(host=RABBIT_HOST)
    consumer.connect()
    try:
        consumer.start_listening(queue_name=HEARTBEAT_QUEUE, callback=on_message)
    except KeyboardInterrupt:
        logger.info("Receiver gestopt (KeyboardInterrupt)")
    finally:
        consumer.close()


if __name__ == "__main__":
    run_receiver()


