# -*- coding: utf-8 -*-
"""
User model for the Integration Service.

Implements CRUD operations for users with the following fields:
- userId (UUID)
- firstName
- lastName
- email
- companyId (UUID, optional)
- badgeCode
- role (Customer, Cashier, Admin, etc.)

For production persistence, use OdooUserRepository to write to Odoo res.partner model.
"""

import logging
import re
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional, List, Dict, Tuple
from enum import Enum

logger = logging.getLogger(__name__)


class UserRole(str, Enum):
    """Supported user roles."""
    VISITOR = "VISITOR"
    COMPANY_CONTACT = "COMPANY_CONTACT"
    SPEAKER = "SPEAKER"
    EVENT_MANAGER = "EVENT_MANAGER"
    CASHIER = "CASHIER"
    BAR_STAFF = "BAR_STAFF"
    ADMIN = "ADMIN"


@dataclass
class User:
    """
    User entity representing a participant/contact in the system.
    
    Attributes:
        userId: UUID for user identification
        firstName: User's first name
        lastName: User's last name
        email: User's email address
        companyId: Optional UUID linking user to a company
        badgeCode: Badge code for scanner/barcode functionality
        role: User's role in the system
        createdAt: Timestamp when user was created
        updatedAt: Timestamp when user was last updated
    """
    userId: str
    firstName: str
    lastName: str
    email: str
    badgeCode: str
    role: str
    companyId: Optional[str] = None
    createdAt: Optional[str] = None
    updatedAt: Optional[str] = None

    def __post_init__(self):
        """Validate field values after initialization."""
        if not self.userId:
            self.userId = str(uuid.uuid4())
        
        if not self.createdAt:
            self.createdAt = datetime.utcnow().isoformat() + 'Z'
        
        if not self.updatedAt:
            self.updatedAt = datetime.utcnow().isoformat() + 'Z'

    def validate(self) -> Tuple[bool, Optional[str]]:
        """
        Validate user data according to schema requirements.
        
        Returns:
            (True, None) if valid
            (False, error_message) if invalid
        """
        if not self.userId:
            return False, "userId is required"
        
        if not self._is_valid_uuid(self.userId):
            return False, f"userId must be a valid UUID: {self.userId}"
        
        if not self.firstName or len(self.firstName) > 80:
            return False, "firstName is required and must be <= 80 characters"
        
        if not self.lastName or len(self.lastName) > 80:
            return False, "lastName is required and must be <= 80 characters"
        
        if not self.email or not self._is_valid_email(self.email):
            return False, f"email must be valid: {self.email}"
        
        if not self.badgeCode:
            return False, "badgeCode is required"
        
        if not self.role:
            return False, "role is required"
        
        if self.role not in [r.value for r in UserRole]:
            return False, f"role must be one of {[r.value for r in UserRole]}"
        
        if self.companyId and not self._is_valid_uuid(self.companyId):
            return False, f"companyId must be a valid UUID if provided: {self.companyId}"
        
        return True, None

    @staticmethod
    def _is_valid_uuid(value: str) -> bool:
        """
        Validate UUID format (v4).
        Pattern: [0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}
        """
        uuid_pattern = r'^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$'
        return bool(re.match(uuid_pattern, value, re.IGNORECASE))

    @staticmethod
    def _is_valid_email(email: str) -> bool:
        """Validate email format."""
        email_pattern = r'^[^@\s]+@[^@\s]+\.[^@\s]+$'
        return bool(re.match(email_pattern, email)) and len(email) <= 254

    def to_dict(self) -> Dict:
        """Convert user to dictionary representation."""
        return asdict(self)

    def to_xml_dict(self) -> Dict:
        """Convert user to dictionary suitable for XML serialization (lowerCamelCase)."""
        return {
            'userId': self.userId,
            'firstName': self.firstName,
            'lastName': self.lastName,
            'email': self.email,
            'companyId': self.companyId,
            'badgeCode': self.badgeCode,
            'role': self.role,
            'createdAt': self.createdAt,
            'updatedAt': self.updatedAt,
        }

