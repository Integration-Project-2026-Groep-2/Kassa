# Kassa Code Examples - Reading Environment Variables

> **Purpose**: Practical Python code examples for reading environment variables in custom Odoo modules and backend services
> **For**: Developers implementing POS features, RabbitMQ integration, and monitoring services

---

## Table of Contents
1. [Configuration Module Pattern](#configuration-module-pattern)
2. [RabbitMQ Connection Examples](#rabbitmq-connection-examples)
3. [Odoo Custom Module Examples](#odoo-custom-module-examples)
4. [Startup Validation](#startup-validation)
5. [Docker Entrypoint Script](#docker-entrypoint-script)

---

## Configuration Module Pattern

### Recommended Approach: Centralized Config Class

Create `src/config.py`:

```python
"""
Configuration module for Kassa services.

Reads environment variables and provides a centralized configuration object
for all services (Odoo module, POS receiver, Heartbeat, etc.).

Usage:
    from config import Config
    
    # Access configuration
    print(Config.RABBIT_HOST)
    print(Config.DB_HOST)
    
    # Validate on startup
    Config.validate()
"""

import os
from typing import Optional
from functools import lru_cache
import logging

logger = logging.getLogger(__name__)


class Config:
    """Centralized application configuration from environment variables."""
    
    # ========== DATABASE CONFIGURATION ==========
    
    @staticmethod
    def db_host() -> str:
        """PostgreSQL hostname or service name."""
        return os.environ.get('DB_HOST', 'db')
    
    @staticmethod
    def db_port() -> int:
        """PostgreSQL port."""
        return int(os.environ.get('DB_PORT', '5432'))
    
    @staticmethod
    def db_name() -> str:
        """PostgreSQL database name."""
        return os.environ.get('POSTGRES_DB', 'kassa_db')
    
    @staticmethod
    def db_user() -> str:
        """PostgreSQL username."""
        return os.environ.get('POSTGRES_USER', 'kassa')
    
    @staticmethod
    def db_password() -> Optional[str]:
        """PostgreSQL password (required in production)."""
        return os.environ.get('POSTGRES_PASSWORD')
    
    @staticmethod
    def db_connection_string() -> str:
        """PostgreSQL connection string for psycopg2/SQLAlchemy."""
        password = Config.db_password() or 'password'
        return (
            f"postgresql://{Config.db_user()}:{password}@"
            f"{Config.db_host()}:{Config.db_port()}/{Config.db_name()}"
        )
    
    # ========== RABBITMQ CONFIGURATION ==========
    
    @staticmethod
    def rabbit_host() -> str:
        """RabbitMQ hostname or service name."""
        return os.environ.get('RABBIT_HOST', 'rabbitmq')
    
    @staticmethod
    def rabbit_port() -> int:
        """RabbitMQ AMQP port (NOT management port 15671)."""
        return int(os.environ.get('RABBIT_PORT', '5672'))
    
    @staticmethod
    def rabbit_user() -> str:
        """RabbitMQ username."""
        return os.environ.get('RABBIT_USER', 'guest')
    
    @staticmethod
    def rabbit_password() -> Optional[str]:
        """RabbitMQ password (required in production)."""
        return os.environ.get('RABBIT_PASSWORD')
    
    @staticmethod
    def rabbit_vhost() -> str:
        """RabbitMQ virtual host."""
        return os.environ.get('RABBIT_VHOST', '/')
    
    # ========== ODOO CONFIGURATION ==========
    
    @staticmethod
    def odoo_port() -> int:
        """Odoo internal port."""
        return int(os.environ.get('ODOO_PORT', '8069'))
    
    @staticmethod
    def odoo_domain() -> str:
        """Odoo public domain (via reverse proxy)."""
        return os.environ.get('ODOO_DOMAIN', 'localhost')
    
    @staticmethod
    def odoo_base_url() -> str:
        """Odoo public base URL for external references."""
        domain = Config.odoo_domain()
        # Use HTTPS if domain is not localhost
        protocol = 'https' if 'localhost' not in domain else 'http'
        return f'{protocol}://{domain}'
    
    # ========== HEARTBEAT CONFIGURATION ==========
    
    @staticmethod
    def heartbeat_interval() -> int:
        """Heartbeat interval in seconds."""
        return int(os.environ.get('HEARTBEAT_INTERVAL_SECONDS', '1'))
    
    @staticmethod
    def heartbeat_exchange() -> str:
        """RabbitMQ exchange for heartbeat messages."""
        return os.environ.get('HEARTBEAT_EXCHANGE', 'heartbeat.direct')
    
    @staticmethod
    def heartbeat_routing_key() -> str:
        """RabbitMQ routing key for heartbeat."""
        return os.environ.get('HEARTBEAT_ROUTING_KEY', 'routing.heartbeat')
    
    @staticmethod
    def heartbeat_queue() -> str:
        """RabbitMQ queue name for heartbeat."""
        return os.environ.get('HEARTBEAT_QUEUE', 'heartbeat_queue')
    
    # ========== VALIDATION ==========
    
    @staticmethod
    def validate() -> bool:
        """
        Validate critical environment variables are set.
        
        Raises:
            EnvironmentError: If critical variables are missing
            
        Returns:
            True if validation passes
        """
        critical_vars = {
            'RABBIT_HOST': Config.rabbit_host,
            'RABBIT_PASSWORD': Config.rabbit_password,
            'POSTGRES_PASSWORD': Config.db_password,
            'ODOO_DOMAIN': Config.odoo_domain,
        }
        
        missing = []
        for var_name, getter in critical_vars.items():
            value = getter()
            if not value:
                missing.append(var_name)
        
        if missing:
            raise EnvironmentError(
                f"Missing critical environment variables: {', '.join(missing)}"
            )
        
        logger.info("✓ All critical environment variables are set")
        return True
    
    @staticmethod
    def log_configuration() -> None:
        """
        Log current configuration (without sensitive values).
        
        Useful for debugging deployment issues.
        """
        logger.info("=" * 60)
        logger.info("KASSA CONFIGURATION")
        logger.info("=" * 60)
        logger.info(f"Database: {Config.db_host()}:{Config.db_port()}/{Config.db_name()}")
        logger.info(f"RabbitMQ: {Config.rabbit_host()}:{Config.rabbit_port()} (vhost: {Config.rabbit_vhost()})")
        logger.info(f"Odoo Domain: {Config.odoo_domain()}")
        logger.info(f"Heartbeat Interval: {Config.heartbeat_interval()}s")
        logger.info("=" * 60)


# Convenience aliases for backward compatibility
DB_HOST = Config.db_host
DB_PORT = Config.db_port
DB_NAME = Config.db_name
DB_USER = Config.db_user
DB_PASSWORD = Config.db_password

RABBIT_HOST = Config.rabbit_host
RABBIT_PORT = Config.rabbit_port
RABBIT_USER = Config.rabbit_user
RABBIT_PASSWORD = Config.rabbit_password
RABBIT_VHOST = Config.rabbit_vhost

ODOO_PORT = Config.odoo_port
ODOO_DOMAIN = Config.odoo_domain
ODOO_BASE_URL = Config.odoo_base_url
```

---

## RabbitMQ Connection Examples

### Using the Config Module

Create `src/messaging/rabbitmq_utils.py`:

```python
"""
RabbitMQ connection utilities using environment variables.

Usage:
    from messaging.rabbitmq_utils import get_rabbitmq_connection, RabbitMQConfig
    
    # Get connection
    connection = get_rabbitmq_connection()
    channel = connection.channel()
    
    # Declare queue and exchange
    channel.exchange_declare(
        exchange='pos.events',
        exchange_type='topic',
        durable=True
    )
    channel.queue_declare(queue='pos_messages', durable=True)
    channel.queue_bind(
        exchange='pos.events',
        queue='pos_messages',
        routing_key='pos.#'
    )
"""

import os
import pika
import logging
from typing import Optional
from config import Config

logger = logging.getLogger(__name__)


class RabbitMQConfig:
    """RabbitMQ configuration helper."""
    
    @staticmethod
    def get_credentials() -> pika.PlainCredentials:
        """Get RabbitMQ credentials from environment."""
        return pika.PlainCredentials(
            username=Config.rabbit_user(),
            password=Config.rabbit_password() or '',
        )
    
    @staticmethod
    def get_connection_parameters() -> pika.ConnectionParameters:
        """Get RabbitMQ connection parameters."""
        return pika.ConnectionParameters(
            host=Config.rabbit_host(),
            port=Config.rabbit_port(),
            virtual_host=Config.rabbit_vhost(),
            credentials=RabbitMQConfig.get_credentials(),
            connection_attempts=5,
            retry_delay=2,
            heartbeat=600,  # 10 minute heartbeat
            blocked_connection_timeout=300,
        )


def get_rabbitmq_connection() -> pika.BlockingConnection:
    """
    Establish RabbitMQ connection with credentials from environment.
    
    Returns:
        pika.BlockingConnection: Connection to RabbitMQ broker
        
    Raises:
        pika.exceptions.AMQPConnectionError: If connection fails
        
    Example:
        >>> connection = get_rabbitmq_connection()
        >>> channel = connection.channel()
        >>> channel.basic_publish(exchange='pos.events', routing_key='pos.user_registered', body=json.dumps(data))
    """
    try:
        connection = pika.BlockingConnection(
            RabbitMQConfig.get_connection_parameters()
        )
        logger.info(
            f"✓ Connected to RabbitMQ: {Config.rabbit_host()}:{Config.rabbit_port()}"
        )
        return connection
    except pika.exceptions.AMQPConnectionError as e:
        logger.error(f"✗ Failed to connect to RabbitMQ: {e}")
        raise


def declare_kassa_infrastructure(channel: pika.adapters.blocking_connection.BlockingChannel) -> None:
    """
    Declare all Kassa exchanges and queues.
    
    Args:
        channel: RabbitMQ channel
        
    Example:
        >>> connection = get_rabbitmq_connection()
        >>> channel = connection.channel()
        >>> declare_kassa_infrastructure(channel)
    """
    
    # POS Events Exchange and Queue
    channel.exchange_declare(
        exchange='pos.events',
        exchange_type='topic',
        durable=True,
        arguments={'x-message-ttl': 3600000}  # 1 hour TTL
    )
    
    channel.queue_declare(
        queue='pos_messages',
        durable=True,
        arguments={'x-max-length': 10000}  # Max 10k messages
    )
    
    channel.queue_bind(
        exchange='pos.events',
        queue='pos_messages',
        routing_key='pos.#'
    )
    
    # Heartbeat Exchange and Queue
    channel.exchange_declare(
        exchange=Config.heartbeat_exchange(),
        exchange_type='direct',
        durable=True,
        arguments={'x-message-ttl': 60000}  # 1 minute TTL
    )
    
    channel.queue_declare(
        queue=Config.heartbeat_queue(),
        durable=True,
        arguments={'x-max-length': 1000}  # Max 1k messages
    )
    
    channel.queue_bind(
        exchange=Config.heartbeat_exchange(),
        queue=Config.heartbeat_queue(),
        routing_key=Config.heartbeat_routing_key()
    )
    
    logger.info("✓ RabbitMQ infrastructure declared")
```

### Use in POS Receiver Service

Update `src/main_pos_receiver.py`:

```python
"""
POS Message Receiver - Consumes messages from RabbitMQ.

This service runs continuously, listening for POS-related events
published to the 'pos.events' exchange.
"""

import json
import logging
from config import Config
from messaging.rabbitmq_utils import get_rabbitmq_connection, declare_kassa_infrastructure

logging.basicConfig(
    level=getattr(logging, Config.log_level().upper(), 'INFO')
)
logger = logging.getLogger(__name__)


def callback(ch, method, properties, body):
    """Callback for message consumption."""
    try:
        message = json.loads(body)
        logger.info(f"Received message: {message}")
        
        # Process message based on type
        message_type = message.get('type')
        if message_type == 'user_registered':
            process_user_registration(message)
        elif message_type == 'user_logged_in':
            process_user_login(message)
        
        # Acknowledge message
        ch.basic_ack(delivery_tag=method.delivery_tag)
        
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in message: {e}")
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
    except Exception as e:
        logger.error(f"Error processing message: {e}")
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)


def process_user_registration(message):
    """Handle user registration event."""
    logger.info(f"Processing user registration: {message}")
    # TODO: Connect to Odoo API, create user


def process_user_login(message):
    """Handle user login event."""
    logger.info(f"Processing user login: {message}")
    # TODO: Log user activity


if __name__ == '__main__':
    logger.info("Starting POS Receiver Service...")
    
    # Validate configuration
    try:
        Config.validate()
        Config.log_configuration()
    except EnvironmentError as e:
        logger.error(f"Configuration Error: {e}")
        exit(1)
    
    try:
        # Connect to RabbitMQ
        connection = get_rabbitmq_connection()
        channel = connection.channel()
        
        # Declare infrastructure
        declare_kassa_infrastructure(channel)
        
        # Set quality of service
        channel.basic_qos(prefetch_count=1)
        
        # Set up consumer
        channel.basic_consume(
            queue='pos_messages',
            on_message_callback=callback,
            auto_ack=False
        )
        
        logger.info("✓ Listening for messages on 'pos_messages' queue...")
        channel.start_consuming()
        
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        connection.close()
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        exit(1)
```

---

## Odoo Custom Module Examples

### Reading Environment Variables in Odoo Models

Update `kassa_pos/models/user_registration.py`:

```python
"""Custom Odoo model for user registration via RabbitMQ."""

import os
import json
import logging
import pika
from odoo import models, fields, api

_logger = logging.getLogger(__name__)


class UserRegistration(models.Model):
    """POS user registration model."""
    
    _name = 'kassa.user.registration'
    _description = 'User Registration'
    
    name = fields.Char(string='Name', required=True)
    email = fields.Char(string='Email', required=True)
    phone = fields.Char(string='Phone')
    created_at = fields.Datetime(default=fields.Datetime.now)
    
    def get_rabbitmq_credentials(self):
        """Get RabbitMQ credentials from environment variables."""
        return {
            'host': os.environ.get('RABBITMQ_HOST', 'rabbitmq'),
            'port': int(os.environ.get('RABBITMQ_PORT', '5672')),
            'user': os.environ.get('RABBITMQ_USER', 'guest'),
            'password': os.environ.get('RABBITMQ_PASS', 'guest'),
            'vhost': os.environ.get('RABBITMQ_VHOST', '/'),
        }
    
    def publish_registration_event(self):
        """Publish user registration event to RabbitMQ."""
        try:
            # Get credentials
            creds = self.get_rabbitmq_credentials()
            
            # Create connection
            credentials = pika.PlainCredentials(creds['user'], creds['password'])
            connection = pika.BlockingConnection(
                pika.ConnectionParameters(
                    host=creds['host'],
                    port=creds['port'],
                    virtual_host=creds['vhost'],
                    credentials=credentials,
                )
            )
            
            channel = connection.channel()
            
            # Declare exchange
            channel.exchange_declare(
                exchange='pos.events',
                exchange_type='topic',
                durable=True
            )
            
            # Publish message
            message = {
                'type': 'user_registered',
                'user_id': self.id,
                'name': self.name,
                'email': self.email,
            }
            
            channel.basic_publish(
                exchange='pos.events',
                routing_key='pos.user_registered',
                body=json.dumps(message),
                properties=pika.BasicProperties(
                    delivery_mode=2,  # Persistent
                    content_type='application/json',
                )
            )
            
            _logger.info(f"✓ Published registration event for user {self.name}")
            connection.close()
            
        except Exception as e:
            _logger.error(f"✗ Failed to publish registration event: {e}")
            raise
    
    @api.model
    def create(self, vals):
        """Create user and publish registration event."""
        user = super().create(vals)
        user.publish_registration_event()
        return user
```

### Using Config in Odoo Module

Create `kassa_pos/utils/config.py`:

```python
"""Configuration helper for Kassa Odoo module."""

import os
from typing import Optional


class OdooConfig:
    """Odoo configuration from environment variables."""
    
    @staticmethod
    def rabbitmq_host() -> str:
        return os.environ.get('RABBITMQ_HOST', 'rabbitmq')
    
    @staticmethod
    def rabbitmq_port() -> int:
        return int(os.environ.get('RABBITMQ_PORT', '5672'))
    
    @staticmethod
    def rabbitmq_user() -> str:
        return os.environ.get('RABBITMQ_USER', 'guest')
    
    @staticmethod
    def rabbitmq_password() -> Optional[str]:
        return os.environ.get('RABBITMQ_PASS')
    
    @staticmethod
    def rabbitmq_vhost() -> str:
        return os.environ.get('RABBITMQ_VHOST', '/')
    
    @staticmethod
    def odoo_domain() -> str:
        return os.environ.get('ODOO_DOMAIN', 'localhost')
```

---

## Startup Validation

### Test All Configurations

Create `test_configuration.py`:

```python
"""Test script to validate all environment variables and connections."""

import sys
import os
import logging
from config import Config
from messaging.rabbitmq_utils import get_rabbitmq_connection

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def test_environment_variables():
    """Test that all critical environment variables are set."""
    logger.info("\n" + "=" * 60)
    logger.info("TESTING ENVIRONMENT VARIABLES")
    logger.info("=" * 60)
    
    try:
        Config.validate()
        Config.log_configuration()
        logger.info("✓ All environment variables OK")
        return True
    except EnvironmentError as e:
        logger.error(f"✗ Configuration Error: {e}")
        return False


def test_database_connection():
    """Test PostgreSQL database connection."""
    logger.info("\n" + "=" * 60)
    logger.info("TESTING DATABASE CONNECTION")
    logger.info("=" * 60)
    
    try:
        import psycopg2
        conn = psycopg2.connect(
            host=Config.db_host(),
            port=Config.db_port(),
            database=Config.db_name(),
            user=Config.db_user(),
            password=Config.db_password(),
        )
        cursor = conn.cursor()
        cursor.execute("SELECT version();")
        version = cursor.fetchone()[0]
        logger.info(f"✓ Connected to database: {version}")
        conn.close()
        return True
    except Exception as e:
        logger.error(f"✗ Database connection failed: {e}")
        return False


def test_rabbitmq_connection():
    """Test RabbitMQ connection."""
    logger.info("\n" + "=" * 60)
    logger.info("TESTING RABBITMQ CONNECTION")
    logger.info("=" * 60)
    
    try:
        connection = get_rabbitmq_connection()
        logger.info("✓ Connected to RabbitMQ")
        connection.close()
        return True
    except Exception as e:
        logger.error(f"✗ RabbitMQ connection failed: {e}")
        return False


if __name__ == '__main__':
    results = []
    
    # Run all tests
    results.append(("Environment Variables", test_environment_variables()))
    results.append(("Database Connection", test_database_connection()))
    results.append(("RabbitMQ Connection", test_rabbitmq_connection()))
    
    # Summary
    logger.info("\n" + "=" * 60)
    logger.info("TEST SUMMARY")
    logger.info("=" * 60)
    
    for test_name, passed in results:
        status = "✓ PASSED" if passed else "✗ FAILED"
        logger.info(f"{test_name}: {status}")
    
    all_passed = all(result[1] for result in results)
    sys.exit(0 if all_passed else 1)
```

Run tests:
```bash
python test_configuration.py
```

---

## Docker Entrypoint Script

### Validate Before Starting Service

Create `entrypoint.sh`:

```bash
#!/bin/bash
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}========================================${NC}"
echo "Kassa Odoo Startup Validation"
echo -e "${GREEN}========================================${NC}"

# Check critical environment variables
echo -e "\n${YELLOW}Checking environment variables...${NC}"

CRITICAL_VARS=(
    "RABBIT_HOST"
    "RABBIT_PORT"
    "RABBIT_USER"
    "RABBIT_PASSWORD"
    "RABBITMQ_VHOST"
    "DB_HOST"
    "DB_PORT"
    "POSTGRES_DB"
    "POSTGRES_USER"
    "POSTGRES_PASSWORD"
    "ODOO_DOMAIN"
)

MISSING=()
for var in "${CRITICAL_VARS[@]}"; do
    if [ -z "${!var}" ]; then
        MISSING+=("$var")
    else
        echo -e "${GREEN}✓${NC} $var = ${!var}"
    fi
done

# Check for missing variables
if [ ${#MISSING[@]} -gt 0 ]; then
    echo -e "${RED}✗ Missing critical environment variables:${NC}"
    for var in "${MISSING[@]}"; do
        echo -e "  ${RED}-${NC} $var"
    done
    exit 1
fi

# Try to connect to RabbitMQ
echo -e "\n${YELLOW}Testing RabbitMQ connection...${NC}"
python3 << 'PYTHON_EOF'
import pika
import os

try:
    credentials = pika.PlainCredentials(
        os.environ.get('RABBIT_USER'),
        os.environ.get('RABBIT_PASSWORD')
    )
    connection = pika.BlockingConnection(
        pika.ConnectionParameters(
            host=os.environ.get('RABBIT_HOST'),
            port=int(os.environ.get('RABBIT_PORT', '5672')),
            virtual_host=os.environ.get('RABBIT_VHOST', '/'),
            credentials=credentials,
        )
    )
    print("✓ RabbitMQ connection successful")
    connection.close()
except Exception as e:
    print(f"✗ RabbitMQ connection failed: {e}")
    exit(1)
PYTHON_EOF

if [ $? -ne 0 ]; then
    exit 1
fi

# Try to connect to PostgreSQL
echo -e "\n${YELLOW}Testing PostgreSQL connection...${NC}"
python3 << 'PYTHON_EOF'
import psycopg2
import os

try:
    conn = psycopg2.connect(
        host=os.environ.get('DB_HOST'),
        port=int(os.environ.get('DB_PORT', '5432')),
        database=os.environ.get('POSTGRES_DB'),
        user=os.environ.get('POSTGRES_USER'),
        password=os.environ.get('POSTGRES_PASSWORD'),
    )
    print("✓ PostgreSQL connection successful")
    conn.close()
except Exception as e:
    print(f"✗ PostgreSQL connection failed: {e}")
    exit 1
PYTHON_EOF

if [ $? -ne 0 ]; then
    exit 1
fi

echo -e "\n${GREEN}========================================${NC}"
echo "All validations passed!"
echo -e "${GREEN}========================================${NC}\n"

# Execute the main service command
exec "$@"
```

Update `Dockerfile` to use entrypoint:

```dockerfile
FROM odoo:latest

USER root
RUN pip3 install pika psycopg2-binary

COPY entrypoint.sh /
RUN chmod +x /entrypoint.sh

USER odoo

ENTRYPOINT ["/entrypoint.sh"]
CMD ["odoo"]
```

---

## Summary

Use these patterns in your Kassa project:

1. **Config Module** - Centralize all environment variable reads
2. **RabbitMQ Utils** - Share connection logic across services
3. **Odoo Models** - Read environment variables directly when needed
4. **Validation** - Test configuration at startup
5. **Entrypoint Script** - Fail fast if configuration is invalid

This ensures:
- ✓ Consistent configuration across all services
- ✓ Clear documentation of environment variables
- ✓ Early detection of configuration errors
- ✓ Easy testing and debugging
- ✓ Production-ready error handling
