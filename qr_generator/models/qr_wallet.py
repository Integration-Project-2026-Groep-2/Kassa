import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Tuple


@dataclass
class QrWallet:
    user_id: str
    qr_token: str = field(default_factory=lambda: str(uuid.uuid4()))
    balance: float = 0.0
    is_active: bool = True
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat() + 'Z')
    updated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat() + 'Z')
    id: Optional[int] = None

    def validate(self) -> Tuple[bool, Optional[str]]:
        if not self.user_id:
            return False, "user_id is required"
        if not self._is_valid_uuid(self.user_id):
            return False, f"user_id must be a valid UUID v4: {self.user_id}"
        if self.balance < 0:
            return False, "balance cannot be negative"
        return True, None

    @staticmethod
    def _is_valid_uuid(value: str) -> bool:
        pattern = r'^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$'
        return bool(re.match(pattern, value, re.IGNORECASE))

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'user_id': self.user_id,
            'qr_token': self.qr_token,
            'balance': round(self.balance, 2),
            'is_active': self.is_active,
            'created_at': self.created_at,
            'updated_at': self.updated_at,
        }
