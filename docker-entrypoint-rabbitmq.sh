#!/bin/bash
# RabbitMQ initialization script
# Creates required exchanges for Kassa system

set -e

echo "Waiting for RabbitMQ to be ready..."
for i in {1..30}; do
  if rabbitmq-diagnostics -q ping 2>/dev/null; then
    echo "RabbitMQ is ready!"
    break
  fi
  echo "Attempt $i/30 - Waiting for RabbitMQ..."
  sleep 2
done

echo "Creating Kassa exchanges..."

RABBITMQADMIN=(rabbitmqadmin -V "${RABBITMQ_DEFAULT_VHOST:-/}" -u "${RABBITMQ_DEFAULT_USER:-guest}" -p "${RABBITMQ_DEFAULT_PASS:-guest}")

# Create kassa.topic exchange (for batch closing messages)
"${RABBITMQADMIN[@]}" declare exchange name=kassa.topic type=topic durable=true auto_delete=false || echo "Exchange kassa.topic already exists"

# Create kassa.direct exchange (for other Kassa messages)
"${RABBITMQADMIN[@]}" declare exchange name=kassa.direct type=direct durable=true auto_delete=false || echo "Exchange kassa.direct already exists"

# Create user events exchange (Salesforce CRM integration - topic-based routing)
"${RABBITMQADMIN[@]}" declare exchange name=user.topic type=topic durable=true auto_delete=false || echo "Exchange user.topic already exists"

# Create user.topic exchange (shared with CRM/Facturatie/Mailing/Planning — C36/C37/C38)
rabbitmqctl declare_exchange user.topic topic durable=true auto_delete=false || echo "Exchange user.topic already exists"

# Create heartbeat exchange
"${RABBITMQADMIN[@]}" declare exchange name=heartbeat.direct type=direct durable=true auto_delete=false || echo "Exchange heartbeat.direct already exists"

# Create CRM contact exchange (for receiving CRM → Kassa messages)
"${RABBITMQADMIN[@]}" declare exchange name=contact.topic type=topic durable=true auto_delete=false || echo "Exchange contact.topic already exists"

echo "Creating CRM consumer queues (Salesforce integration)..."

# Create queues for consuming from CRM (queue names kassa.user.*, bound to contact.topic with crm.user.* routing keys)
"${RABBITMQADMIN[@]}" declare queue name=kassa.user.confirmed durable=true auto_delete=false || echo "Queue kassa.user.confirmed already exists"
"${RABBITMQADMIN[@]}" declare binding source=contact.topic destination_type=queue destination=kassa.user.confirmed routing_key=crm.user.confirmed || echo "Binding kassa.user.confirmed → contact.topic with routing key crm.user.confirmed already exists"

"${RABBITMQADMIN[@]}" declare queue name=kassa.user.updated durable=true auto_delete=false || echo "Queue kassa.user.updated already exists"
"${RABBITMQADMIN[@]}" declare binding source=contact.topic destination_type=queue destination=kassa.user.updated routing_key=crm.user.updated || echo "Binding kassa.user.updated → contact.topic with routing key crm.user.updated already exists"

"${RABBITMQADMIN[@]}" declare queue name=kassa.user.deactivated durable=true auto_delete=false || echo "Queue kassa.user.deactivated already exists"
"${RABBITMQADMIN[@]}" declare binding source=contact.topic destination_type=queue destination=kassa.user.deactivated routing_key=crm.user.deactivated || echo "Binding kassa.user.deactivated → contact.topic with routing key crm.user.deactivated already exists"

echo "✓ All exchanges created successfully!"
echo "Kassa system is ready for message publishing."