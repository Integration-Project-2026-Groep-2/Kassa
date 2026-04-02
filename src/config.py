from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv


load_dotenv()


@dataclass(frozen=True)
class Settings:
    rabbitmq_url: str
    odoo_url: str
    odoo_database: str
    odoo_username: str
    odoo_password: str
    heartbeat_interval_seconds: int
    heartbeat_exchange: str
    heartbeat_routing_key: str
    status_check_interval_seconds: int
    system_name: str
    log_level: str
    schema_path: str

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            rabbitmq_url=os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/"),
            odoo_url=os.getenv("ODOO_URL", "http://localhost:8069"),
            odoo_database=os.getenv("ODOO_DATABASE", "kassa_db"),
            odoo_username=os.getenv("ODOO_USERNAME", "admin"),
            odoo_password=os.getenv("ODOO_PASSWORD", "changeme"),
            heartbeat_interval_seconds=int(os.getenv("HEARTBEAT_INTERVAL_SECONDS", "1")),
            heartbeat_exchange=os.getenv("HEARTBEAT_EXCHANGE", "heartbeat.direct"),
            heartbeat_routing_key=os.getenv("HEARTBEAT_ROUTING_KEY", "heartbeat.direct"),
            status_check_interval_seconds=int(os.getenv("STATUS_CHECK_INTERVAL_SECONDS", "30")),
            system_name=os.getenv("SYSTEM_NAME", "KASSA"),
            log_level=os.getenv("LOG_LEVEL", "INFO"),
            schema_path=os.getenv("SCHEMA_PATH", "src/schema/kassa-schema-v1.xsd"),
        )
