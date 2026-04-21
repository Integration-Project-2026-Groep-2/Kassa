#!/usr/bin/env python3
"""
Setup script to create required RabbitMQ exchanges for Kassa system.
Run this after docker-compose up to ensure exchanges exist.
"""

import pika
import sys
import time

def create_exchanges():
    """Create all required exchanges for Kassa system."""
    
    # Connection parameters
    rabbitmq_host = "localhost"
    rabbitmq_port = 5672
    rabbitmq_user = "guest"
    rabbitmq_password = "guest"
    rabbitmq_vhost = "/"
    
    # Retry logic for container startup
    max_retries = 30
    retry_count = 0
    
    while retry_count < max_retries:
        try:
            credentials = pika.PlainCredentials(rabbitmq_user, rabbitmq_password)
            parameters = pika.ConnectionParameters(
                host=rabbitmq_host,
                port=rabbitmq_port,
                virtual_host=rabbitmq_vhost,
                credentials=credentials,
                connection_attempts=1
            )
            connection = pika.BlockingConnection(parameters)
            channel = connection.channel()
            print("✓ Connected to RabbitMQ")
            break
        except pika.exceptions.AMQPConnectionError:
            retry_count += 1
            if retry_count < max_retries:
                print(f"Waiting for RabbitMQ... (attempt {retry_count}/{max_retries})")
                time.sleep(2)
            else:
                print("✗ Failed to connect to RabbitMQ after retries")
                sys.exit(1)
    
    # Define exchanges to create
    exchanges = [
        ("kassa.topic", "topic", True),      # Batch closing messages
        ("kassa.direct", "direct", True),    # Other Kassa messages
        ("user.direct", "direct", True),     # User CRUD events
        ("user.dlx", "direct", True),        # User dead letter exchange
        ("user.retry", "direct", True),      # User retry exchange
        ("heartbeat.direct", "direct", True), # Heartbeat messages
    ]
    
    try:
        for exchange_name, exchange_type, durable in exchanges:
            try:
                channel.exchange_declare(
                    exchange=exchange_name,
                    exchange_type=exchange_type,
                    durable=durable,
                    auto_delete=False
                )
                print(f"✓ Exchange '{exchange_name}' ({exchange_type}) created/verified")
            except pika.exceptions.ChannelClosedByBroker as e:
                # Exchange already exists - this is fine
                if "NOT_FOUND" not in str(e) and "PRECONDITION_FAILED" not in str(e):
                    print(f"⚠ Warning creating '{exchange_name}': {e}")
                else:
                    print(f"✓ Exchange '{exchange_name}' already exists")
        
        connection.close()
        print("\n✓ All exchanges created successfully!")
        print("Kassa system is ready for message publishing.")
        return 0
    
    except Exception as e:
        print(f"✗ Error creating exchanges: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(create_exchanges())
