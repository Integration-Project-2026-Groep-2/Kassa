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

The UserStore provides in-memory storage and database abstraction.
For production, this should be backed by a persistent database (PostgreSQL, MongoDB, etc.).
"""

import logging
import re
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
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
            self.createdAt = datetime.now(timezone.utc).isoformat() + 'Z'
        
        if not self.updatedAt:
            self.updatedAt = datetime.now(timezone.utc).isoformat() + 'Z'

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


class UserStore:
    """
    In-memory store for user data.
    
    Provides CRUD operations with validation and error handling.
    For production, this should be backed by a persistent database.
    """

    def __init__(self):
        """Initialize the user store."""
        self._users: Dict[str, User] = {}
        self._badge_index: Dict[str, str] = {}  # badgeCode -> userId mapping

    # ─────────────── CREATE ───────────────

    def create_user(self, user: User) -> Tuple[bool, Optional[str], Optional[User]]:
        """
        Create a new user.
        
        Args:
            user: User object to create
        
        Returns:
            (True, None, created_user) on success
            (False, error_message, None) on failure
        """
        # Validate user data
        valid, error = user.validate()
        if not valid:
            logger.error("User validation failed: %s", error)
            return False, error, None

        # Check if userId already exists
        if user.userId in self._users:
            error = f"User with userId '{user.userId}' already exists"
            logger.error(error)
            return False, error, None

        # Check if badgeCode already exists
        if user.badgeCode in self._badge_index:
            error = f"User with badgeCode '{user.badgeCode}' already exists"
            logger.error(error)
            return False, error, None

        # Store user
        self._users[user.userId] = user
        self._badge_index[user.badgeCode] = user.userId
        logger.info("User created: userId=%s, email=%s", user.userId, user.email)
        
        return True, None, user

    # ─────────────── READ ───────────────

    def get_user_by_id(self, user_id: str) -> Optional[User]:
        """
        Retrieve a user by userId.
        
        Args:
            user_id: User's UUID
        
        Returns:
            User object if found, None otherwise
        """
        user = self._users.get(user_id)
        if not user:
            logger.warning("User not found by userId: %s", user_id)
            return None
        return user

    def get_user_by_badge(self, badge_code: str) -> Optional[User]:
        """
        Retrieve a user by badgeCode (for scanner functionality).
        
        Args:
            badge_code: Badge code
        
        Returns:
            User object if found, None otherwise
        """
        user_id = self._badge_index.get(badge_code)
        if not user_id:
            logger.warning("User not found by badgeCode: %s", badge_code)
            return None
        return self._users.get(user_id)

    def get_user_by_email(self, email: str) -> Optional[User]:
        """
        Retrieve a user by email.
        
        Args:
            email: User's email address
        
        Returns:
            User object if found, None otherwise
        """
        for user in self._users.values():
            if user.email == email:
                return user
        logger.warning("User not found by email: %s", email)
        return None

    def get_all_users(self) -> List[User]:
        """
        Retrieve all users.
        
        Returns:
            List of all User objects
        """
        return list(self._users.values())

    # ─────────────── UPDATE ───────────────

    def update_user(self, user_id: str, updates: Dict) -> Tuple[bool, Optional[str], Optional[User]]:
        """
        Update an existing user.
        
        Args:
            user_id: User's UUID
            updates: Dictionary of fields to update
        
        Returns:
            (True, None, updated_user) on success
            (False, error_message, None) on failure
        """
        user = self._users.get(user_id)
        if not user:
            error = f"User not found: {user_id}"
            logger.error(error)
            return False, error, None

        # Handle badgeCode updates (update index)
        if 'badgeCode' in updates and updates['badgeCode'] != user.badgeCode:
            new_badge = updates['badgeCode']
            if new_badge in self._badge_index:
                error = f"badgeCode already in use: {new_badge}"
                logger.error(error)
                return False, error, None
            
            # Remove old mapping and add new
            del self._badge_index[user.badgeCode]
            self._badge_index[new_badge] = user_id

        # Update user fields
        for key, value in updates.items():
            if hasattr(user, key):
                setattr(user, key, value)

        # Update timestamp
        user.updatedAt = datetime.now(timezone.utc).isoformat() + 'Z'

        # Validate updated user
        valid, error = user.validate()
        if not valid:
            logger.error("Updated user validation failed: %s", error)
            return False, error, None

        logger.info("User updated: userId=%s", user_id)
        return True, None, user

    # ─────────────── DELETE ───────────────

    def delete_user(self, user_id: str) -> Tuple[bool, Optional[str]]:
        """
        Delete (deactivate) a user.
        
        Args:
            user_id: User's UUID
        
        Returns:
            (True, None) on success
            (False, error_message) on failure
        """
        user = self._users.get(user_id)
        if not user:
            error = f"User not found: {user_id}"
            logger.error(error)
            return False, error

        # Remove badge index mapping
        if user.badgeCode in self._badge_index:
            del self._badge_index[user.badgeCode]

        # Remove user
        del self._users[user_id]
        logger.info("User deleted: userId=%s", user_id)
        return True, None

    # ─────────────── UTILITIES ───────────────

    def get_user_count(self) -> int:
        """Get total number of users."""
        return len(self._users)

    def clear_all(self) -> None:
        """Clear all users (for testing)."""
        self._users.clear()
        self._badge_index.clear()
        logger.info("User store cleared")
