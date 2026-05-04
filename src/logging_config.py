"""Central logging configuration for the Kassa project.

Configures a console handler, optional rotating file handler, and RabbitMQ handler.
Reads environment variables:
- LOG_LEVEL (default: INFO)
- LOG_FILE (optional): if set, enables a RotatingFileHandler
- LOG_FILE_MAX_BYTES (default: 5_242_880 = 5MB)
- LOG_FILE_BACKUP_COUNT (default: 5)
- ENABLE_RABBITMQ_LOGS (default: true): publish logs to RabbitMQ/Controlroom
"""
import logging
import os
import threading
import queue
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler, QueueHandler, QueueListener
from lxml import etree

try:
    import aio_pika
    import asyncio
    HAS_AIOPIKA = True
except ImportError:
    HAS_AIOPIKA = False


# Mapping from Python logging levels to XML LogEvent severity types
SEVERITY_MAP = {
    logging.DEBUG: "DEBUG",
    logging.INFO: "INFO",
    logging.WARNING: "WARN",
    logging.ERROR: "ERROR",
    logging.CRITICAL: "PANIC",
}


class RabbitMQLogHandler(logging.Handler):
    """
    Async logging handler that publishes logs as XML LogEvent to RabbitMQ.
    Uses a background thread to avoid blocking the logging pipeline.
    """

    def __init__(self, service_name: str = "KASSA"):
        super().__init__()
        self.service_name = service_name
        self.log_queue = queue.Queue()
        self.stop_event = threading.Event()
        
        # Start background thread for async publishing
        self.thread = threading.Thread(target=self._worker_thread, daemon=True)
        self.thread.start()

    def emit(self, record: logging.LogRecord) -> None:
        """Queue the log record for async publishing."""
        try:
            self.log_queue.put_nowait(record)
        except queue.Full:
            # If queue is full, drop silently to avoid blocking
            pass

    def _worker_thread(self) -> None:
        """Background thread: pull from queue and publish to RabbitMQ."""
        if not HAS_AIOPIKA:
            return

        loop = None
        connection = None

        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            while not self.stop_event.is_set():
                try:
                    # Get record with timeout
                    record = self.log_queue.get(timeout=1.0)
                    
                    # Publish asynchronously
                    loop.run_until_complete(
                        self._publish_to_rabbitmq(record)
                    )
                except queue.Empty:
                    continue
                except Exception as e:
                    # Log to stderr but don't crash
                    import sys
                    print(f"RabbitMQLogHandler error: {e}", file=sys.stderr)

        finally:
            if loop:
                loop.close()

    async def _publish_to_rabbitmq(self, record: logging.LogRecord) -> None:
        """Publish a log record as XML to RabbitMQ."""
        try:
            from config import RABBIT_HOST, RABBIT_PORT, RABBIT_USER, RABBIT_PASSWORD, RABBIT_VHOST

            connection = await aio_pika.connect_robust(
                f"amqp://{RABBIT_USER}:{RABBIT_PASSWORD}@{RABBIT_HOST}:{RABBIT_PORT}/{RABBIT_VHOST}"
            )
            channel = await connection.channel()

            # Build XML LogEvent
            root = etree.Element("LogEvent")
            etree.SubElement(root, "level").text = SEVERITY_MAP.get(
                record.levelno, "INFO"
            )
            etree.SubElement(root, "timestamp").text = datetime.fromtimestamp(
                record.created, tz=timezone.utc
            ).isoformat()
            etree.SubElement(root, "service").text = self.service_name
            etree.SubElement(root, "data").text = record.getMessage()

            xml_bytes = etree.tostring(root, xml_declaration=True, encoding="UTF-8")

            # Publish to logs.direct exchange
            await channel.default_exchange.publish(
                aio_pika.Message(body=xml_bytes),
                routing_key="routing.log",
            )

            await connection.close()

        except Exception:
            # Silently fail to avoid disrupting the logging system
            pass

    def close(self) -> None:
        """Stop the worker thread and clean up."""
        self.stop_event.set()
        if self.thread.is_alive():
            self.thread.join(timeout=2.0)
        super().close()



def configure_logging() -> None:
    level_name = os.environ.get('LOG_LEVEL', 'INFO').upper()
    level = getattr(logging, level_name, logging.INFO)

    root = logging.getLogger()
    if root.handlers:
        # Already configured
        return

    root.setLevel(level)

    fmt = os.environ.get(
        'LOG_FORMAT', '%(asctime)s %(levelname)s %(name)s: %(message)s'
    )
    datefmt = os.environ.get('LOG_DATEFMT', '%Y-%m-%d %H:%M:%S')

    console = logging.StreamHandler()
    console.setLevel(level)
    console.setFormatter(logging.Formatter(fmt=fmt, datefmt=datefmt))
    root.addHandler(console)

    log_file = os.environ.get('LOG_FILE')
    if log_file:
        try:
            max_bytes = int(os.environ.get('LOG_FILE_MAX_BYTES', 5242880))
            backup_count = int(os.environ.get('LOG_FILE_BACKUP_COUNT', 5))
        except ValueError:
            max_bytes = 5242880
            backup_count = 5

        fh = RotatingFileHandler(log_file, maxBytes=max_bytes, backupCount=backup_count)
        fh.setLevel(level)
        fh.setFormatter(logging.Formatter(fmt=fmt, datefmt=datefmt))
        root.addHandler(fh)

    # Add RabbitMQ handler to send logs to Controlroom
    enable_rabbitmq = os.environ.get('ENABLE_RABBITMQ_LOGS', 'true').lower() in ('true', '1', 'yes')
    if enable_rabbitmq and HAS_AIOPIKA:
        try:
            rabbitmq_handler = RabbitMQLogHandler(service_name="KASSA")
            rabbitmq_handler.setLevel(level)
            root.addHandler(rabbitmq_handler)
        except Exception as e:
            # If RabbitMQ handler fails to initialize, continue without it
            import sys
            print(f"Warning: RabbitMQ logging handler failed to initialize: {e}", file=sys.stderr)



# Configure on import so modules don't have to call this explicitly.
configure_logging()
