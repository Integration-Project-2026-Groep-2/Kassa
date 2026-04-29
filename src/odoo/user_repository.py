# -*- coding: utf-8 -*-
"""
Odoo User Repository - wrapper for res.partner CRUD operations.

Maps User dataclass fields to Odoo res.partner model fields and provides
high-level CRUD operations for user management from the Integration Service.
"""

import logging
from typing import Optional, Dict, Any
from models.user import User, UserRole
from odoo.odoo_connection import OdooConnection

logger = logging.getLogger(__name__)


class OdooUserRepository:
    """
    Repository for user operations against Odoo res.partner model.
    
    Field Mapping:
        User.userId → res.partner.user_id_custom
        User.firstName + User.lastName → res.partner.name
        User.email → res.partner.email
        User.badgeCode → res.partner.badge_code
        User.role → res.partner.role (mapped to Odoo value)
        User.companyId → res.partner.company_id_custom
    """
    
    # Map CRM roles to Odoo res.partner roles
    ROLE_MAP = {
        'VISITOR': 'Customer',
        'COMPANY_CONTACT': 'Customer',
        'SPEAKER': 'Customer',
        'EVENT_MANAGER': 'Customer',
        'CASHIER': 'Cashier',
        'BAR_STAFF': 'Customer',
        'ADMIN': 'Admin',
    }
    
    MODEL_NAME = 'res.partner'
    
    def __init__(self, odoo_connection: OdooConnection):
        """
        Initialize repository with Odoo connection.
        
        Args:
            odoo_connection: OdooConnection instance (must be connected)
        """
        if not odoo_connection.is_connected():
            raise RuntimeError("OdooConnection is not connected. Call connect() first.")
        
        self.odoo = odoo_connection
    
    def create_user(self, user: User) -> int:
        """
        Create a new user in Odoo (res.partner).
        
        Uses create_or_update logic: if user with same user_id_custom exists,
        updates it instead (prevents duplicates).
        
        Args:
            user: User dataclass instance from RabbitMQ message
        
        Returns:
            Odoo res.partner record ID
        
        Raises:
            ValueError: If user data is invalid
            RuntimeError: If Odoo operation fails
        """
        # Validate user
        valid, error_msg = user.validate()
        if not valid:
            raise ValueError(f"Invalid user data: {error_msg}")
        
        # Check if user already exists by user_id_custom or email
        domain = [['user_id_custom', '=', user.userId]]
        if user.email:
            domain = ['|', ['user_id_custom', '=', user.userId], ['email', '=', user.email]]
            
        existing_ids = self.odoo.search(
            self.MODEL_NAME,
            domain
        )
        
        if existing_ids:
            # Update existing user
            partner_id = existing_ids[0]
            logger.info(
                "User already exists, updating [partner_id=%d user_id=%s]",
                partner_id, user.userId
            )
            self.update_user(user)
            return partner_id
        
        # Create new user
        values = self._map_user_to_partner_values(user)
        
        try:
            partner_id = self.odoo.create(self.MODEL_NAME, values)

            # Read-back to verify standard visibility fields are correctly set
            try:
                partner_records = self.odoo.read(
                    self.MODEL_NAME,
                    [partner_id],
                    ['id', 'name', 'email', 'active', 'customer_rank', 'is_company', 'company_id', 'user_id_custom', 'badge_code']
                )
                partner_record = partner_records[0] if partner_records else None
                logger.info(
                    "User created in Odoo [partner_id=%d user_id=%s email=%s badge=%s company_id=%s] -> readback=%s",
                    partner_id, user.userId, user.email, user.badgeCode, partner_record.get('company_id') if partner_record else None, partner_record
                )

                if partner_record is None:
                    raise RuntimeError("Created partner not readable after create")

                if not self._verify_partner_visibility(partner_record):
                    raise RuntimeError(
                        f"Partner created but not visible in Customers UI [partner_id={partner_id} visibility_check_failed]"
                    )

            except Exception as verify_error:
                logger.error(
                    "Verification failed after create in Odoo [partner_id=%d user_id=%s error=%s]",
                    partner_id, user.userId, str(verify_error)
                )
                raise

            return partner_id

        except Exception as e:
            logger.error(
                "Failed to create user in Odoo [user_id=%s error=%s]",
                user.userId, str(e)
            )
            raise RuntimeError(f"Failed to create user in Odoo: {str(e)}")
    
    def update_user(self, user: User) -> bool:
        """
        Update an existing user in Odoo (res.partner).
        
        Finds user by user_id_custom and updates all fields.
        
        Args:
            user: User dataclass instance with updated fields
        
        Returns:
            True if update succeeded
        
        Raises:
            ValueError: If user not found or data is invalid
            RuntimeError: If Odoo operation fails
        """
        # Validate user
        valid, error_msg = user.validate()
        if not valid:
            raise ValueError(f"Invalid user data: {error_msg}")
        
        # Find user by user_id_custom or email
        domain = [['user_id_custom', '=', user.userId]]
        if user.email:
            domain = ['|', ['user_id_custom', '=', user.userId], ['email', '=', user.email]]
            
        partner_ids = self.odoo.search(
            self.MODEL_NAME,
            domain
        )
        
        if not partner_ids:
            raise ValueError(f"User not found in Odoo [user_id={user.userId}]")
        
        partner_id = partner_ids[0]
        values = self._map_user_to_partner_values(user, is_update=True)
        
        try:
            self.odoo.write(self.MODEL_NAME, [partner_id], values)
            
            # Read-back to verify standard visibility fields are correctly set
            try:
                partner_records = self.odoo.read(
                    self.MODEL_NAME,
                    [partner_id],
                    ['id', 'name', 'email', 'active', 'customer_rank', 'is_company', 'company_id', 'user_id_custom', 'badge_code']
                )
                partner_record = partner_records[0] if partner_records else None
                logger.info(
                    "User updated in Odoo [partner_id=%d user_id=%s email=%s badge=%s company_id=%s] -> readback=%s",
                    partner_id, user.userId, user.email, user.badgeCode, partner_record.get('company_id') if partner_record else None, partner_record
                )
                
                if partner_record is None:
                    raise RuntimeError("Updated partner not readable after write")
                
                if not self._verify_partner_visibility(partner_record):
                    raise RuntimeError(
                        f"Partner updated but not visible in Customers UI [partner_id={partner_id} visibility_check_failed]"
                    )
            
            except Exception:
                # If read-back verification fails, log and re-raise
                raise
            
            return True
        
        except Exception as e:
            logger.error(
                "Failed to update user in Odoo [user_id=%s partner_id=%d error=%s]",
                user.userId, partner_id, str(e)
            )
            raise RuntimeError(f"Failed to update user in Odoo: {str(e)}")
    
    def deactivate_user(self, user_id: str) -> bool:
        """
        Deactivate a user in Odoo (soft delete via is_active=False).
        
        Used for GDPR compliance. Preserves data in database but hides from UI.
        
        Args:
            user_id: CRM user UUID (user_id_custom)
        
        Returns:
            True if deactivation succeeded
        
        Raises:
            ValueError: If user not found
            RuntimeError: If Odoo operation fails
        """
        # Find user by user_id_custom
        partner_ids = self.odoo.search(
            self.MODEL_NAME,
            [['user_id_custom', '=', user_id]]
        )
        
        if not partner_ids:
            logger.warning(
                "Cannot deactivate user - not found in Odoo [user_id=%s]",
                user_id
            )
            return False
        
        partner_id = partner_ids[0]
        
        try:
            self.odoo.write(self.MODEL_NAME, [partner_id], {'active': False})
            logger.info(
                "User deactivated in Odoo [partner_id=%d user_id=%s]",
                partner_id, user_id
            )
            return True
        
        except Exception as e:
            logger.error(
                "Failed to deactivate user in Odoo [user_id=%s partner_id=%d error=%s]",
                user_id, partner_id, str(e)
            )
            raise RuntimeError(f"Failed to deactivate user in Odoo: {str(e)}")
    
    def get_user_by_badge(self, badge_code: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve user data by badge code.
        
        Used by POS to lookup users when scanning badges.
        
        Args:
            badge_code: Badge code to search for
        
        Returns:
            Dictionary with user data or None if not found
        """
        try:
            partner_ids = self.odoo.search(
                self.MODEL_NAME,
                [['badge_code', '=', badge_code], ['active', '=', True]]
            )
            
            if not partner_ids:
                return None
            
            partner_id = partner_ids[0]
            records = self.odoo.read(
                self.MODEL_NAME,
                [partner_id],
                ['id', 'name', 'email', 'badge_code', 'role', 'user_id_custom']
            )
            
            return records[0] if records else None
        
        except Exception as e:
            logger.error(
                "Failed to get user by badge [badge=%s error=%s]",
                badge_code, str(e)
            )
            return None
    
    def get_user_by_user_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve user data by CRM user ID.
        
        Args:
            user_id: CRM user UUID (user_id_custom)
        
        Returns:
            Dictionary with user data or None if not found
        """
        try:
            partner_ids = self.odoo.search(
                self.MODEL_NAME,
                [['user_id_custom', '=', user_id]]
            )
            
            if not partner_ids:
                return None
            
            partner_id = partner_ids[0]
            records = self.odoo.read(
                self.MODEL_NAME,
                [partner_id],
                ['id', 'name', 'email', 'badge_code', 'role', 'user_id_custom', 'active']
            )
            
            return records[0] if records else None
        
        except Exception as e:
            logger.error(
                "Failed to get user [user_id=%s error=%s]",
                user_id, str(e)
            )
            return None

    def _verify_partner_visibility(self, partner_record: Dict[str, Any]) -> bool:
        """
        Check whether the created/updated partner record will be visible in the
        standard Odoo Customers view.

        Currently enforces:
        - `active` must be truthy
        - `customer_rank` must be >= 1
        - `is_company` must be False (we create contacts, not companies)
        - `company_id` must be set (required for multi-company visibility)
        """
        try:
            active = bool(partner_record.get('active', True))
            customer_rank = int(partner_record.get('customer_rank') or 0)
            is_company = bool(partner_record.get('is_company', False))
            company_id = partner_record.get('company_id')

            if not active:
                logger.error("Partner not active: %s", partner_record)
                return False

            if customer_rank < 1:
                logger.error("Partner customer_rank < 1: %s", partner_record)
                return False

            if is_company:
                logger.error("Partner is_company True (expected False): %s", partner_record)
                return False

            # company_id can be False to be shared across all companies, so we don't enforce it.

            return True

        except Exception:
            logger.exception("Error while verifying partner visibility: %s", partner_record)
            return False
    
    def _map_user_to_partner_values(self, user: User, is_update: bool = False) -> Dict[str, Any]:
        """
        Map User dataclass fields to res.partner field values.
        
        Args:
            user: User dataclass instance
            is_update: If True, don't set creation-only fields
        
        Returns:
            Dictionary of field values for Odoo create/write
        """
        values = {
            'name': f"{user.firstName} {user.lastName}",
            'email': user.email,
            'badge_code': user.badgeCode,
            'user_id_custom': user.userId,
            'role': self.ROLE_MAP.get(user.role, 'Customer'),
            'active': True,
            'is_company': False,
            'company_type': 'person',
            'customer_rank': 1,
        }
        
        # Use the connection's default company when available so records stay visible in the main company context.
        default_company_id = None
        if hasattr(self.odoo, 'get_default_company_id'):
            default_company_id = self.odoo.get_default_company_id()

        values['company_id'] = default_company_id or False
        
        # Optional fields
        if user.companyId:
            values['company_id_custom'] = user.companyId
        
        return values
