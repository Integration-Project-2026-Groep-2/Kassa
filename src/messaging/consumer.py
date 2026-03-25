import xml.etree.ElementTree as ET
from src.connection import RabbitManager

def handle_user_crud(ch, method, properties, body):
    """
    Verwerkt inkomende User XML voor CRUD operaties.
    """
    # 1. XML Parsen
    root = ET.fromstring(body)
    
    # 2. Velden uitlezen volgens afgesproken naming convention [cite: 69]
    user_data = {
        "userId": root.find('userId').text, # [cite: 74]
        "firstName": root.find('firstName').text, # [cite: 75]
        "badgeCode": root.find('badgeCode').text, # 
        "role": root.find('role').text # [cite: 80]
    }

    # 3. Loggen (De 'Read' stap voor je demo)
    print(f"[CRUD] Ontvangen User: {user_data['firstName']} (ID: {user_data['userId']})")
    print(f"[ACTION] Update badgeCode naar: {user_data['badgeCode']}")
    
    # TODO: Hier voeg je later de API call naar Odoo toe (VM 1) [cite: 22]

def start_user_consumer():
    rabbit = RabbitManager()
    rabbit.connect()
    rabbit.channel.queue_declare(queue='user_queue')
    
    rabbit.channel.basic_consume(
        queue='user_queue', 
        on_message_callback=handle_user_crud, 
        auto_ack=True
    )
    print(" [*] User CRUD service gestart. Wachten op XML...")
    rabbit.channel.start_consuming()

if __name__ == "__main__":
    start_user_consumer()