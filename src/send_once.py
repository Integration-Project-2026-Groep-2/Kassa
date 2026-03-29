from messaging.producer import KassaProducer
from messaging.message_builders import build_heartbeat_xml
from config import RABBIT_HOST, HEARTBEAT_QUEUE

if __name__ == '__main__':
    p = KassaProducer(host=RABBIT_HOST)
    p.connect()
    p.publish(build_heartbeat_xml(), routing_key=HEARTBEAT_QUEUE)
    p.close()
    print('Sent one heartbeat')
