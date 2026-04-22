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

# Create kassa.topic exchange (for batch closing messages)
rabbitmqctl declare_exchange kassa.topic topic durable=true auto_delete=false || echo "Exchange kassa.topic already exists"

# Create kassa.direct exchange (for other Kassa messages)
rabbitmqctl declare_exchange kassa.direct direct durable=true auto_delete=false || echo "Exchange kassa.direct already exists"

# Create user events exchanges (for user CRUD)
rabbitmqctl declare_exchange user.direct direct durable=true auto_delete=false || echo "Exchange user.direct already exists"
rabbitmqctl declare_exchange user.dlx direct durable=true auto_delete=false || echo "Exchange user.dlx already exists"
rabbitmqctl declare_exchange user.retry direct durable=true auto_delete=false || echo "Exchange user.retry already exists"

# Create heartbeat exchange
rabbitmqctl declare_exchange heartbeat.direct direct durable=true auto_delete=false || echo "Exchange heartbeat.direct already exists"

echo "✓ All exchanges created successfully!"
echo "Kassa system is ready for message publishing."