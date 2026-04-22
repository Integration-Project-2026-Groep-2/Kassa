# Kassa Environment Variables Configuration

## Overview
This document defines all environment variables required for the Kassa Odoo custom module deployment in a containerized environment with RabbitMQ messaging and PostgreSQL database.

---

## Environment Variables Table

| Variable | Service(s) | Type | Default | Example Value | Description |
|----------|-----------|------|---------|---|---|
| **DATABASE CONFIGURATION** |
| `DB_HOST` | odoo | string | `db` | `postgres.azure.internal` | PostgreSQL host address. Use internal DNS name for Azure VM networks. |
| `DB_PORT` | odoo | integer | `5432` | `5432` | PostgreSQL port. Standard PostgreSQL port. |
| `POSTGRES_DB` | db, odoo | string | `kassa_db` | `kassa_db` | PostgreSQL database name. Must match across all services. |
| `POSTGRES_USER` | db, odoo | string | `kassa` | `kassa_prod` | PostgreSQL user for database access. |
| `POSTGRES_PASSWORD` | db, odoo | string | `<PASSWORD_HERE>` | `<PASSWORD_HERE>` | PostgreSQL password. Use Azure Key Vault or secrets management. |
| **RABBITMQ CONFIGURATION** |
| `RABBIT_HOST` | odoo, pos_receiver, heartbeat | string | `rabbitmq` | `rabbitmq.integration-project-2026-groep-2.my.be` | RabbitMQ hostname/FQDN for AMQP connections. |
| `RABBIT_PORT` | odoo, pos_receiver, heartbeat | integer | `5672` | `5672` | RabbitMQ AMQP protocol port (non-encrypted). |
| `RABBIT_MANAGEMENT_PORT` | - | integer | `15671` | `15671` | RabbitMQ Management UI port (HTTPS). For reference/monitoring only. |
| `RABBIT_USER` | odoo, pos_receiver, heartbeat, rabbitmq | string | `guest` | `kassa_user` | RabbitMQ username for authentication. |
| `RABBIT_PASSWORD` | odoo, pos_receiver, heartbeat, rabbitmq | string | `<PASSWORD_HERE>` | `<PASSWORD_HERE>` | RabbitMQ password. Use Azure Key Vault or secrets management. |
| `RABBIT_VHOST` | odoo, pos_receiver, heartbeat, rabbitmq | string | `/` | `/kassa` | RabbitMQ virtual host. Isolates message queues. |
| **ODOO CONFIGURATION** |
| `ODOO_PORT` | odoo | integer | `8069` | `8069` | Internal port where Odoo listens (inside container). |
| `ODOO_DOMAIN` | odoo | string | `localhost` | `kassa.integration-project-2026-groep-2.my.be` | Public domain name via reverse proxy. Used for email notifications and external references. |
| **HEARTBEAT CONFIGURATION** |
| `HEARTBEAT_INTERVAL_SECONDS` | heartbeat | integer | `1` | `5` | Interval between heartbeat messages in seconds. |
| `HEARTBEAT_EXCHANGE` | heartbeat | string | `heartbeat.direct` | `heartbeat.direct` | RabbitMQ exchange name for heartbeat messages. |
| `HEARTBEAT_ROUTING_KEY` | heartbeat | string | `routing.heartbeat` | `routing.heartbeat` | RabbitMQ routing key for heartbeat queue binding. |
| `HEARTBEAT_QUEUE` | heartbeat | string | `heartbeat_queue` | `heartbeat_queue` | RabbitMQ queue name for heartbeat messages. |

---

## Service-Specific Environment Variables

### Odoo Service
```
DB_HOST, DB_PORT, POSTGRES_DB, POSTGRES_USER, POSTGRES_PASSWORD
RABBIT_HOST, RABBIT_PORT, RABBIT_USER, RABBIT_PASSWORD, RABBIT_VHOST
ODOO_PORT, ODOO_DOMAIN
```

### POS Receiver Service
```
RABBIT_HOST, RABBIT_PORT, RABBIT_USER, RABBIT_PASSWORD, RABBIT_VHOST
```

### Embedded Heartbeat in Odoo Image
```
RABBIT_HOST, RABBIT_PORT, RABBIT_USER, RABBIT_PASSWORD, RABBIT_VHOST
HEARTBEAT_INTERVAL_SECONDS, HEARTBEAT_EXCHANGE, HEARTBEAT_ROUTING_KEY, HEARTBEAT_QUEUE
```

### PostgreSQL Service
```
POSTGRES_DB, POSTGRES_USER, POSTGRES_PASSWORD
```

### RabbitMQ Service
```
RABBIT_USER, RABBIT_PASSWORD, RABBIT_VHOST
RABBIT_PORT (5672), RABBIT_MANAGEMENT_PORT (15671)
```

---

## Azure Infrastructure Context

### Network Configuration
- **Reverse Proxy**: Nginx (external-facing)
- **Internal Service Name**: `rabbitmq` (Docker Compose network)
- **FQDN**: `kassa.integration-project-2026-groep-2.my.be` (subdomain via Nginx proxy)
- **VM Location**: Azure Virtual Machine

### Port Mappings
| Service | Internal Port | External Port (via Nginx) | Protocol |
|---------|---|---|---|
| Odoo | `8069` | `443` (HTTPS) | HTTP/HTTPS |
| RabbitMQ AMQP | `5672` | `5672` (internal) | AMQP |
| RabbitMQ Management | `15671` | `15671` (HTTPS) | HTTPS |

---

## Production Deployment Guidelines

### Secrets Management
Never commit real passwords to version control. Use one of:
- **Azure Key Vault**: Retrieve secrets at container startup
- **Docker Secrets** (Swarm mode): Mount secrets as files
- **.env files** (LOCAL DEV ONLY): Create `.env` file in project root, add to `.gitignore`

### Example `.env` File (LOCAL DEVELOPMENT ONLY)
```bash
# Database
POSTGRES_USER=kassa_prod
POSTGRES_PASSWORD=<PASSWORD_HERE>
POSTGRES_DB=kassa_db
DB_HOST=postgres.azure.internal

# RabbitMQ
RABBIT_USER=kassa_user
RABBIT_PASSWORD=<PASSWORD_HERE>
RABBIT_HOST=rabbitmq.integration-project-2026-groep-2.my.be
RABBIT_VHOST=/kassa

# Odoo
ODOO_PORT=8069
ODOO_DOMAIN=kassa.integration-project-2026-groep-2.my.be

# Heartbeat
HEARTBEAT_INTERVAL_SECONDS=5
```

### Azure Key Vault Integration (Production)
```bash
# Retrieve secrets from Azure Key Vault at startup
az keyvault secret show --vault-name "kassa-vault" --name "POSTGRES_PASSWORD" --query value -o tsv

# Pass to container
docker run -e POSTGRES_PASSWORD=$(az keyvault secret show ...) ...
```

---

## How Custom Code Reads Environment Variables

### Python (Recommended for Kassa Services)

#### 1. Using `os.environ`
```python
import os

# Read with default fallback
db_host = os.environ.get('DB_HOST', 'db')
db_user = os.environ.get('POSTGRES_USER', 'kassa')
db_password = os.environ.get('POSTGRES_PASSWORD')

# Raise error if critical variable missing
rabbit_host = os.environ['RABBIT_HOST']  # KeyError if not set
```

#### 2. Creating a Configuration Module
Create [src/config.py](src/config.py):
```python
import os
from typing import Optional

class Config:
    """Centralized environment variable configuration"""
    
    # Database
    DB_HOST: str = os.environ.get('DB_HOST', 'db')
    DB_PORT: int = int(os.environ.get('DB_PORT', '5432'))
    DB_NAME: str = os.environ.get('POSTGRES_DB', 'kassa_db')
    DB_USER: str = os.environ.get('POSTGRES_USER', 'kassa')
    DB_PASSWORD: Optional[str] = os.environ.get('POSTGRES_PASSWORD')
    
    # RabbitMQ
    RABBIT_HOST: str = os.environ.get('RABBIT_HOST', 'rabbitmq')
    RABBIT_PORT: int = int(os.environ.get('RABBIT_PORT', '5672'))
    RABBIT_USER: str = os.environ.get('RABBIT_USER', 'guest')
    RABBIT_PASSWORD: Optional[str] = os.environ.get('RABBIT_PASSWORD')
    RABBIT_VHOST: str = os.environ.get('RABBIT_VHOST', '/')
    
    # Odoo
    ODOO_PORT: int = int(os.environ.get('ODOO_PORT', '8069'))
    ODOO_DOMAIN: str = os.environ.get('ODOO_DOMAIN', 'localhost')
    
    # Heartbeat
    HEARTBEAT_INTERVAL: int = int(os.environ.get('HEARTBEAT_INTERVAL_SECONDS', '1'))
    HEARTBEAT_EXCHANGE: str = os.environ.get('HEARTBEAT_EXCHANGE', 'heartbeat.direct')
    HEARTBEAT_ROUTING_KEY: str = os.environ.get('HEARTBEAT_ROUTING_KEY', 'routing.heartbeat')
    HEARTBEAT_QUEUE: str = os.environ.get('HEARTBEAT_QUEUE', 'heartbeat_queue')
    
    @classmethod
    def validate(cls) -> bool:
        """Validate critical environment variables are set"""
        critical = ['RABBIT_HOST', 'POSTGRES_PASSWORD', 'RABBIT_PASSWORD']
        missing = [var for var in critical if not os.environ.get(var)]
        
        if missing:
            raise EnvironmentError(f"Missing critical environment variables: {missing}")
        return True

# Usage in services
if __name__ == '__main__':
    Config.validate()
    print(f"Connecting to RabbitMQ at {Config.RABBIT_HOST}:{Config.RABBIT_PORT}")
```

#### 3. Using Python-Dotenv (Local Development)
```python
from dotenv import load_dotenv
import os

# Load .env file
load_dotenv()

# Access variables
db_host = os.environ.get('DB_HOST')
```

### Odoo Custom Module Integration

#### Reading Environment Variables in Python Files
[kassa_pos/models/user_registration.py](kassa_pos/models/user_registration.py):
```python
import os
from odoo import models, fields

class UserRegistration(models.Model):
    _name = 'kassa.user.registration'
    
    def _get_rabbitmq_config(self):
        """Get RabbitMQ configuration from environment"""
        return {
            'host': os.environ.get('RABBIT_HOST', 'rabbitmq'),
            'port': int(os.environ.get('RABBIT_PORT', '5672')),
            'user': os.environ.get('RABBIT_USER', 'guest'),
            'password': os.environ.get('RABBIT_PASSWORD'),
            'vhost': os.environ.get('RABBIT_VHOST', '/'),
        }
```

#### Using Environment Variables in RabbitMQ Sender
[kassa_pos/utils/rabbitmq_sender.py](kassa_pos/utils/rabbitmq_sender.py):
```python
import os
import pika

def get_rabbitmq_connection():
    """Establish RabbitMQ connection using environment variables"""
    credentials = pika.PlainCredentials(
        os.environ.get('RABBIT_USER', 'guest'),
        os.environ.get('RABBIT_PASSWORD', 'guest')
    )
    
    connection = pika.BlockingConnection(
        pika.ConnectionParameters(
            host=os.environ.get('RABBIT_HOST', 'rabbitmq'),
            port=int(os.environ.get('RABBIT_PORT', '5672')),
            virtual_host=os.environ.get('RABBIT_VHOST', '/'),
            credentials=credentials,
            connection_attempts=5,
            retry_delay=2,
        )
    )
    return connection
```

### Entrypoint Script Pattern

Create [entrypoint.sh](entrypoint.sh) in project root:
```bash
#!/bin/bash
set -e

# Validate critical environment variables
if [ -z "$RABBIT_HOST" ]; then
    echo "ERROR: RABBIT_HOST environment variable not set"
    exit 1
fi

if [ -z "$POSTGRES_PASSWORD" ]; then
    echo "ERROR: POSTGRES_PASSWORD environment variable not set"
    exit 1
fi

echo "✓ Validating environment variables..."
echo "  - RabbitMQ Host: $RABBIT_HOST:$RABBIT_PORT"
echo "  - Database: $POSTGRES_DB"
echo "  - Odoo Domain: $ODOO_DOMAIN"

# Execute main command
exec "$@"
```

Update [Dockerfile](Dockerfile):
```dockerfile
FROM odoo:latest
USER root
RUN pip3 install pika
COPY entrypoint.sh /
RUN chmod +x /entrypoint.sh
USER odoo
ENTRYPOINT ["/entrypoint.sh"]
CMD ["odoo"]
```

---

## Testing Environment Variables

### Docker Compose - Quick Test
```bash
# List all environment variables for odoo service
docker-compose config | grep -A 30 "odoo:"

# Connect to running odoo container and verify
docker-compose exec odoo bash -c 'echo RABBIT_HOST=$RABBIT_HOST'
docker-compose exec odoo bash -c 'echo DB_HOST=$DB_HOST'
```

### Python Script Test
```python
# test_config.py
from src.config import Config

try:
    Config.validate()
    print(f"✓ RabbitMQ: {Config.RABBIT_HOST}:{Config.RABBIT_PORT}")
    print(f"✓ Database: {Config.DB_HOST}:{Config.DB_PORT}/{Config.DB_NAME}")
    print(f"✓ Odoo Domain: {Config.ODOO_DOMAIN}")
except EnvironmentError as e:
    print(f"✗ Configuration Error: {e}")
```

---

## Industry Best Practices

### 1. Environment Variable Naming
- Use `UPPERCASE_WITH_UNDERSCORES` convention
- Group related variables (e.g., `RABBIT_*`, `DB_*`)
- Use descriptive names that indicate purpose

### 2. Default Values
- Provide sensible defaults for development
- Never default to production credentials
- Use `None` or empty string for secrets

### 3. Sensitive Data
- **Never** log passwords or keys
- **Never** commit `.env` files with real secrets
- Use CI/CD secrets management (GitHub Secrets, Azure Pipelines)

### 4. Validation
- Validate critical environment variables at startup
- Fail fast if required variables are missing
- Provide clear error messages

### 5. Documentation
- Document every environment variable
- Include examples and defaults
- Explain service dependencies

---

## Troubleshooting

### Connection Issues

**Problem**: `Cannot connect to RabbitMQ`
```
Solution:
1. Verify RABBIT_HOST is correct (use 'rabbitmq' for internal Docker network)
2. Check RABBIT_PORT is 5672 (not 15671, which is Management UI)
3. Verify RABBIT_USER and RABBIT_PASSWORD match
4. Check RabbitMQ service is healthy: docker-compose logs rabbitmq
```

**Problem**: `PostgreSQL connection refused`
```
Solution:
1. Verify DB_HOST matches service name ('db') or Azure hostname
2. Check POSTGRES_PASSWORD matches DB_PASSWORD
3. Ensure PostgreSQL service is running and healthy
4. Check database port (default 5432)
```

### Variable Not Being Read

**Problem**: `KeyError: RABBIT_HOST not in environment`
```
Solution:
1. Verify variable is defined in docker-compose.yml under environment:
2. Check for typos in variable name
3. Ensure .env file exists and is loaded
4. Restart container after changing variables
```

---

## Summary

Your Kassa deployment uses environment variables to configure:
- **Database**: PostgreSQL on Azure infrastructure
- **Message Queue**: RabbitMQ with AMQP protocol
- **Odoo**: Web server on port 8069, accessed via nginx reverse proxy
- **Custom Services**: POS receiver; heartbeat runs inside the Odoo image/container

All services read these variables at startup, ensuring consistency across development, testing, and production environments.
