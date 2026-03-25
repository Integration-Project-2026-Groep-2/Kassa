from connection import RabbitManager
import datetime

def send_heartbeat():
    #deze methode maakt een XML-bericht op en stuurt die naar de queue


    #Start de manager en verbind met RabbitMQ
    rabbit = RabbitManager()
    rabbit.connect()
    
    #maak de XML payload aan met de huidige timestamp
    xml_payload = f"""<Heartbeat>
    <serviceName>TeamKassa</serviceName>
    <status>Alive</status>
    <timestamp>{datetime.datetime.now().isoformat()}Z</timestamp>
</Heartbeat>"""

    #declareer de queue (zorgt ervoor dat de queue bestaat voordat we er berichten naartoe sturen)
    rabbit.channel.queue_declare(queue='heartbeat_queue')
    #verstuur het XML-bericht naar de queue met de naam 'heartbeat_queue'
    rabbit.channel.basic.publish(exchange='',
                                 routing_key='heartbeat_queue',
                                 body=xml_payload
                                 )
    print(f" [LOG] Heartbeat verzonden naar RabbitMQ op {datetime.datetime.now().isoformat()}Z")
    # Sluit de verbinding netjes af
    rabbit.close()

if __name__ == "__main__":
    send_heartbeat()
    