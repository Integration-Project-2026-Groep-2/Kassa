import logging
import time

from messaging.producer import KassaProducer
from messaging.message_builders import build_heartbeat_xml
from config import RABBIT_HOST, HEARTBEAT_QUEUE


"""
Kleine runner die periodiek een Heartbeat-XML opbouwt en naar RabbitMQ publiceert.

Wij gebruiken `KassaProducer` om de verbinding en publicatie te doen;
`build_heartbeat_xml` leest het XML-template en vult de actuele timestamp.

Start dit bestand direct om een eenvoudige heartbeat-publisher te draaien.
"""


logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)


def run_heartbeat(interval_seconds: int = 10):
    """Start de producer en verstuur elke `interval_seconds` een heartbeat.

    - Maakt verbinding via `KassaProducer`.
    - Gebruikt het XML-template uit `templates/Heartbeat.xml`.
    - Logt succes en fouten.
    """

    producer = KassaProducer(host=RABBIT_HOST)
    producer.connect()

    try:
        while True:
            # Bouw het XML-bericht (vult timestamp en andere velden)
            xml = build_heartbeat_xml()

            # Publiceer naar de queue/exchange die in config is ingesteld
            producer.publish(xml, routing_key=HEARTBEAT_QUEUE)
            logger.info("Heartbeat verzonden")

            time.sleep(interval_seconds)
    except KeyboardInterrupt:
        logger.info("Heartbeat publisher gestopt (KeyboardInterrupt)")
    finally:
        producer.close()


if __name__ == "__main__":
    run_heartbeat()
    