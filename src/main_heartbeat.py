import logging
import time

from messaging.producer import KassaProducer
from messaging.message_builders import build_heartbeat_xml
from config import (
    RABBIT_HOST,
    HEARTBEAT_INTERVAL_SECONDS,
    HEARTBEAT_EXCHANGE,
    HEARTBEAT_ROUTING_KEY,
)


"""
Kleine runner die periodiek een Heartbeat-XML opbouwt en naar RabbitMQ publiceert.

Wij gebruiken `KassaProducer` om de verbinding en publicatie te doen;
`build_heartbeat_xml` leest het XML-template en vult de actuele timestamp.

Start dit bestand direct om een eenvoudige heartbeat-publisher te draaien.
"""


logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

RECONNECT_DELAY_SECONDS = 2


def run_heartbeat(interval_seconds: int = 1):
    """Start de producer en verstuur elke `interval_seconds` een heartbeat.

    - Maakt verbinding via `KassaProducer`.
    - Gebruikt het XML-template uit `templates/Heartbeat.xml`.
    - Logt succes en fouten.
    """
    producer = KassaProducer(host=RABBIT_HOST)
    logger.debug(
        "Heartbeat route: exchange='%s', routing_key='%s'",
        HEARTBEAT_EXCHANGE,
        HEARTBEAT_ROUTING_KEY,
    )

    connected = False
    try:
        while True:
            if not connected:
                try:
                    producer.connect()
                    connected = True
                    logger.debug("Heartbeat producer verbonden met RabbitMQ")
                except Exception as exc:
                    logger.warning("Heartbeat connectie mislukt: %s", exc)
                    time.sleep(RECONNECT_DELAY_SECONDS)
                    continue

            try:
                xml = build_heartbeat_xml()

                # Publiceer expliciet naar de heartbeat exchange.
                producer.publish(
                    xml,
                    routing_key=HEARTBEAT_ROUTING_KEY,
                    exchange=HEARTBEAT_EXCHANGE,
                    declare_queue=False,
                )
                time.sleep(interval_seconds)
            except Exception as exc:
                logger.warning("Heartbeat publish mislukt: %s", exc)
                try:
                    producer.close()
                except Exception:
                    pass
                connected = False
                time.sleep(RECONNECT_DELAY_SECONDS)
    except KeyboardInterrupt:
        logger.info("Heartbeat publisher gestopt (KeyboardInterrupt)")
    finally:
        try:
            producer.close()
        except Exception:
            pass


if __name__ == "__main__":
    run_heartbeat(interval_seconds=HEARTBEAT_INTERVAL_SECONDS)
    