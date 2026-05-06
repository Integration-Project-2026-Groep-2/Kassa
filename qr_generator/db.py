import logging
import os
import sqlite3

logger = logging.getLogger(__name__)

DB_PATH = os.environ.get('QR_DB_PATH', 'qr_wallets.db')


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS qr_wallets (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id    TEXT NOT NULL UNIQUE,
                qr_token   TEXT NOT NULL UNIQUE,
                balance    REAL NOT NULL DEFAULT 0.0,
                is_active  INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_user_id  ON qr_wallets (user_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_qr_token ON qr_wallets (qr_token)")
        conn.commit()
    logger.info("Database klaar op %s", DB_PATH)
