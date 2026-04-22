# RabbitMQ Setup Guide

## Overview

The Kassa system uses RabbitMQ for message publishing and consuming between different components. The system requires several exchanges to be created before operation.

## Exchanges Required

| Exchange Name | Type | Purpose |
|---------------|------|---------|
| `kassa.topic` | topic | Batch closing messages from POS to Facturatie |
| `kassa.direct` | direct | Other Kassa system messages |
| `user.direct` | direct | User CRUD events |
| `user.dlx` | direct | User dead letter exchange (errors) |
| `user.retry` | direct | User message retry queue |
| `heartbeat.direct` | direct | System heartbeat messages |

## Setup Instructions

### Automatic Setup (Recommended)

After starting the Docker containers with `docker compose -f docker-compose.production.yml up -d --build`, run the setup script to create all exchanges:

```bash
python setup_rabbitmq.py
```

This script will:
1. Wait for RabbitMQ to be ready (with retries)
2. Create all required exchanges
3. Verify they exist and are durable

**Output:**
```
✓ Connected to RabbitMQ
✓ Exchange 'kassa.topic' (topic) created/verified
✓ Exchange 'kassa.direct' (direct) created/verified
✓ Exchange 'user.direct' (direct) created/verified
✓ Exchange 'user.dlx' (direct) created/verified
✓ Exchange 'user.retry' (direct) created/verified
✓ Exchange 'heartbeat.direct' (direct) created/verified

✓ All exchanges created successfully!
Kassa system is ready for message publishing.
```

### Manual Setup

If you need to verify or manually create exchanges, use the RabbitMQ Management UI:

1. Open RabbitMQ Management: http://localhost:15672
2. Log in with credentials from your `.env` file (default: guest/guest)
3. Navigate to "Exchanges" tab
4. Create each exchange with the following settings:
   - **Name:** (from table above)
   - **Type:** (from table above)
   - **Durable:** Yes
   - **Auto delete:** No

### Verify Exchanges

Check that all exchanges are created:

```bash
docker compose exec -T rabbitmq rabbitmqctl list_exchanges
```

You should see all exchanges listed with their types.

## RabbitMQ Management UI

- **URL:** http://localhost:15672
- **Default Username:** guest
- **Default Password:** guest
- **Vhost:** /

## Architecture

### Message Flow

1. **POS System** → publishes `BatchClosed` messages
2. **kassa.topic Exchange** → routes messages based on routing keys
3. **Facturatie System** → binds queue to exchange with routing key `kassa.closed`
4. **Facturatie Consumer** → processes batch and sends back confirmation

### Routing Keys

- `kassa.closed` - Batch closing events from POS (published to `kassa.topic`)
- `kassa.heartbeat` - System heartbeat messages (published from the Odoo image/container)
- `user.*` - User CRUD operations

## Troubleshooting

### Exchanges Don't Exist

If exchanges are missing after starting Docker:

```bash
# Verify RabbitMQ is running and healthy
docker compose ps rabbitmq

# Run the setup script
python setup_rabbitmq.py
```

### Connection Refused

If the setup script can't connect to RabbitMQ:

1. Verify RabbitMQ container is running: `docker compose ps`
2. Check RabbitMQ is healthy: `docker compose logs rabbitmq | tail -20`
3. Ensure port 5672 is exposed in docker-compose.yml
4. Check `.env` file has correct `RABBIT_HOST=rabbitmq`

### Messages Not Routing

If messages are published but not reaching consumers:

1. Verify exchange exists: `docker compose exec -T rabbitmq rabbitmqctl list_exchanges`
2. Verify queue bindings: `docker compose exec -T rabbitmq rabbitmqctl list_bindings`
3. Check routing key matches between publisher and consumer

## Docker Compose Integration

The `rabbitmq` service in docker-compose.yml is configured with:

- **Image:** rabbitmq:3-management (includes web UI)
- **Ports:** 5672 (AMQP), 15672 (Management UI)
- **Health Check:** `rabbitmq-diagnostics ping` every 10 seconds
- **Credentials:** From `.env` file environment variables

Dependent services (`pos_receiver`) wait for RabbitMQ to be healthy before starting:

```yaml
depends_on:
  rabbitmq:
    condition: service_healthy
```

## Scripts Reference

### setup_rabbitmq.py

Python script that creates all required RabbitMQ exchanges using pika AMQP library.

**Features:**
- Auto-retry connection logic (up to 30 attempts)
- Creates all exchanges atomically
- Handles already-existing exchanges gracefully
- Clear success/failure output

**Usage:**
```bash
python setup_rabbitmq.py
```

**Requirements:**
- pika 1.3.2+ (already in requirements.txt)
- RabbitMQ running and accessible on localhost:5672
