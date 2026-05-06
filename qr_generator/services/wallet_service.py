import logging
import sqlite3
from datetime import datetime
from typing import Optional

from db import get_connection
from models.qr_wallet import QrWallet

logger = logging.getLogger(__name__)


def _row_to_wallet(row: sqlite3.Row) -> QrWallet:
    return QrWallet(
        id=row['id'],
        user_id=row['user_id'],
        qr_token=row['qr_token'],
        balance=float(row['balance']),
        is_active=bool(row['is_active']),
        created_at=row['created_at'],
        updated_at=row['updated_at'],
    )


def create_wallet(user_id: str) -> QrWallet:
    wallet = QrWallet(user_id=user_id)
    valid, error = wallet.validate()
    if not valid:
        raise ValueError(error)

    with get_connection() as conn:
        existing = conn.execute(
            "SELECT id FROM qr_wallets WHERE user_id = ?", (user_id,)
        ).fetchone()
        if existing:
            raise ValueError(f"Wallet bestaat al voor gebruiker {user_id}")

        cursor = conn.execute(
            """INSERT INTO qr_wallets (user_id, qr_token, balance, is_active, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (wallet.user_id, wallet.qr_token, wallet.balance,
             int(wallet.is_active), wallet.created_at, wallet.updated_at),
        )
        wallet.id = cursor.lastrowid
        conn.commit()

    logger.info("Wallet aangemaakt voor gebruiker %s (token: %s)", user_id, wallet.qr_token)
    return wallet


def get_wallet_by_user(user_id: str) -> Optional[QrWallet]:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM qr_wallets WHERE user_id = ?", (user_id,)
        ).fetchone()
    return _row_to_wallet(row) if row else None


def get_wallet_by_token(qr_token: str) -> Optional[QrWallet]:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM qr_wallets WHERE qr_token = ?", (qr_token,)
        ).fetchone()
    return _row_to_wallet(row) if row else None


def topup_wallet(user_id: str, amount: float) -> QrWallet:
    if amount <= 0:
        raise ValueError("Opwaardeerbedrag moet groter zijn dan 0")

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM qr_wallets WHERE user_id = ?", (user_id,)
        ).fetchone()
        if not row:
            raise ValueError(f"Geen wallet gevonden voor gebruiker {user_id}")

        wallet = _row_to_wallet(row)
        if not wallet.is_active:
            raise ValueError(f"Wallet van gebruiker {user_id} is gedeactiveerd")

        new_balance = round(wallet.balance + amount, 2)
        updated_at = datetime.utcnow().isoformat() + 'Z'

        conn.execute(
            "UPDATE qr_wallets SET balance = ?, updated_at = ? WHERE user_id = ?",
            (new_balance, updated_at, user_id),
        )
        conn.commit()

    wallet.balance = new_balance
    wallet.updated_at = updated_at
    logger.info(
        "Wallet opgewaardeerd voor gebruiker %s met %.2f (nieuw saldo: %.2f)",
        user_id, amount, new_balance,
    )
    return wallet


def deactivate_wallet(user_id: str) -> QrWallet:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM qr_wallets WHERE user_id = ?", (user_id,)
        ).fetchone()
        if not row:
            raise ValueError(f"Geen wallet gevonden voor gebruiker {user_id}")

        updated_at = datetime.utcnow().isoformat() + 'Z'
        conn.execute(
            "UPDATE qr_wallets SET is_active = 0, updated_at = ? WHERE user_id = ?",
            (updated_at, user_id),
        )
        conn.commit()

    wallet = _row_to_wallet(row)
    wallet.is_active = False
    wallet.updated_at = updated_at
    logger.info("Wallet gedeactiveerd voor gebruiker %s", user_id)
    return wallet
