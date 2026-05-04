"""Central logging configuration for the Kassa project.

Configures a console handler and optional rotating file handler.
Reads environment variables:
- LOG_LEVEL (default: INFO)
- LOG_FILE (optional): if set, enables a RotatingFileHandler
- LOG_FILE_MAX_BYTES (default: 5_242_880 = 5MB)
- LOG_FILE_BACKUP_COUNT (default: 5)
"""
import logging
import os
from logging.handlers import RotatingFileHandler


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


# Configure on import so modules don't have to call this explicitly.
configure_logging()
