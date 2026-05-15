from messaging.producer import KassaProducer
from messaging.message_builders import build_heartbeat_xml
from src.settings import RABBIT_HOST, HEARTBEAT_EXCHANGE, HEARTBEAT_ROUTING_KEY
import logging


if __name__ == '__main__':
    p = KassaProducer(host=RABBIT_HOST)
    p.connect()
    p.publish(
        build_heartbeat_xml(),
        exchange=HEARTBEAT_EXCHANGE,
        routing_key=HEARTBEAT_ROUTING_KEY,
        declare_queue=False,
        durable=False,
    )
    p.close()
    logging.getLogger(__name__).info('Sent one heartbeat')
