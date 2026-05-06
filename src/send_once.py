from messaging.producer import KassaProducer
from messaging.message_builders import build_heartbeat_xml
from config import RABBIT_HOST, HEARTBEAT_EXCHANGE, HEARTBEAT_ROUTING_KEY

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
    print('Sent one heartbeat')
