# -*- coding: utf-8 -*-
"""
User message consumer for the Integration Service.

Handles incoming user messages:
- User messages (create/update operations)
- UserConfirmed messages (from CRM)
- UserUpdated messages (from CRM)
- UserDeactivated messages (from CRM)

Processes XML payloads, validates them, and stores user data.
"""

import logging
import xml.etree.ElementTree as ET
from typing import Optional, Callable
from models.user import User, UserStore
from messaging.message_builders import parse_user_xml
from xml_validator import validate_xml

logger = logging.getLogger(__name__)


class UserConsumer:
    """
    Consumer for processing user-related messages from RabbitMQ.
    
    Subscribes to user queues and processes:
    - Create operations (from integration service)
    - Update operations (from CRM)
    - Deactivation operations (from CRM)
    """

    def __init__(self, user_store: UserStore, on_error: Optional[Callable] = None):
        """
        Initialize the user consumer.
        
        Args:
            user_store: UserStore instance for CRUD operations
            on_error: Optional callback function(message_type, error) for error handling
        """
        self.user_store = user_store
        self.on_error = on_error

    def process_user_message(self, xml_payload: str) -> bool:
        """
        Process a User XML message.
        
        Handles both User (basic CRUD) and CRM-originated messages
        (UserConfirmed, UserUpdated, UserDeactivated).
        
        Args:
            xml_payload: XML string containing user data
        
        Returns:
            True if processing succeeded, False otherwise
        """
        # Validate XML against schema
        valid, error = validate_xml(xml_payload)
        if not valid:
            logger.error("User message validation failed: %s", error)
            if self.on_error:
                self.on_error('User', error)
            return False

        try:
            root = ET.fromstring(xml_payload)
            message_type = root.tag
            
            if message_type == 'User':
                return self._handle_user_message(root)
            elif message_type == 'UserConfirmed':
                return self._handle_user_confirmed(root)
            elif message_type == 'UserUpdated':
                return self._handle_user_updated(root)
            elif message_type == 'UserDeactivated':
                return self._handle_user_deactivated(root)
            else:
                logger.warning("Unknown user message type: %s", message_type)
                return False
        
        except ET.ParseError as e:
            error = f"Failed to parse user message XML: {str(e)}"
            logger.error(error)
            if self.on_error:
                self.on_error('User', error)
            return False
        except Exception as e:
            error = f"Unexpected error processing user message: {str(e)}"
            logger.error(error)
            if self.on_error:
                self.on_error('User', error)
            return False

    def _handle_user_message(self, root: ET.Element) -> bool:
        """
        Handle a User message (create or update operation).
        
        Args:
            root: XML Element of type User
        
        Returns:
            True on success, False otherwise
        """
        # Parse user data from XML
        success, error, user_data = parse_user_xml(ET.tostring(root, encoding='unicode'))
        if not success:
            logger.error("Failed to parse user data: %s", error)
            if self.on_error:
                self.on_error('User', error)
            return False

        # Create User object
        try:
            user = User(**user_data)
        except (TypeError, ValueError) as e:
            error = f"Failed to create User object: {str(e)}"
            logger.error(error)
            if self.on_error:
                self.on_error('User', error)
            return False

        # Check if user exists to determine create vs update
        existing_user = self.user_store.get_user_by_id(user.userId)
        
        if not existing_user:
            # Create new user
            success, error, created_user = self.user_store.create_user(user)
            if not success:
                logger.error("Failed to create user: %s", error)
                if self.on_error:
                    self.on_error('User', error)
                return False
            logger.info("User created via message: userId=%s", user.userId)
            return True
        else:
            # Update existing user
            updates = {k: v for k, v in user_data.items() if v is not None}
            success, error, updated_user = self.user_store.update_user(user.userId, updates)
            if not success:
                logger.error("Failed to update user: %s", error)
                if self.on_error:
                    self.on_error('User', error)
                return False
            logger.info("User updated via message: userId=%s", user.userId)
            return True

    def _handle_user_confirmed(self, root: ET.Element) -> bool:
        """
        Handle a UserConfirmed message from CRM.
        
        Creates or updates user based on CRM confirmation.
        
        Args:
            root: XML Element of type UserConfirmed
        
        Returns:
            True on success, False otherwise
        """
        return self._handle_crm_user_snapshot(root, 'UserConfirmed')

    def _handle_user_updated(self, root: ET.Element) -> bool:
        """
        Handle a UserUpdated message from CRM.
        
        Updates existing user or creates if doesn't exist.
        
        Args:
            root: XML Element of type UserUpdated
        
        Returns:
            True on success, False otherwise
        """
        return self._handle_crm_user_snapshot(root, 'UserUpdated')

    def _handle_user_deactivated(self, root: ET.Element) -> bool:
        """
        Handle a UserDeactivated message from CRM.
        
        Deletes/deactivates user from the store.
        
        Args:
            root: XML Element of type UserDeactivated
        
        Returns:
            True on success, False otherwise
        """
        try:
            user_id = root.findtext('id', '').strip()
            existing_user = self.user_store.get_user_by_id(user_id)

            if not existing_user:
                error = f"Cannot deactivate unknown user: {user_id}"
                logger.error(error)
                if self.on_error:
                    self.on_error('UserDeactivated', error)
                return False

            existing_user.isActive = False
            deactivated_at = root.findtext('deactivatedAt', '').strip()
            if deactivated_at:
                existing_user.updatedAt = deactivated_at
                setattr(existing_user, 'deactivatedAt', deactivated_at)

            logger.info("UserDeactivated processed: userId=%s (soft delete)", user_id)
            return True

        except Exception as e:
            error = f"Error handling UserDeactivated: {str(e)}"
            logger.error(error)
            if self.on_error:
                self.on_error('UserDeactivated', error)
            return False

    def _handle_crm_user_snapshot(self, root: ET.Element, message_type: str) -> bool:
        """Replace the local user snapshot from a CRM UserConfirmed/UserUpdated message."""
        try:
            user_id = root.findtext('id', '').strip()
            if not user_id:
                raise ValueError('id is required')

            badge_code = root.findtext('badgeCode', '').strip()
            if not badge_code:
                badge_code = f"DEFAULT_{user_id}"
                logger.warning("%s missing badgeCode, using fallback for userId=%s", message_type, user_id)

            user_data = {
                'userId': user_id,
                'firstName': root.findtext('firstName', '').strip(),
                'lastName': root.findtext('lastName', '').strip(),
                'email': root.findtext('email', '').strip(),
                'badgeCode': badge_code,
                'role': root.findtext('role', '').strip(),
            }

            company_id = root.findtext('companyId', '').strip()
            if company_id:
                user_data['companyId'] = company_id

            if message_type == 'UserConfirmed':
                confirmed_at = root.findtext('confirmedAt', '').strip()
                if confirmed_at:
                    user_data['createdAt'] = confirmed_at
                    user_data['updatedAt'] = confirmed_at
            else:
                updated_at = root.findtext('updatedAt', '').strip()
                if updated_at:
                    user_data['updatedAt'] = updated_at

            user = User(**user_data)
            setattr(user, 'isActive', root.findtext('isActive', 'true').strip().lower() == 'true')

            gdpr_consent = root.findtext('gdprConsent', '').strip()
            if gdpr_consent:
                setattr(user, 'gdprConsent', gdpr_consent.lower() == 'true')

            for field_name in ('phone', 'street', 'houseNumber', 'postalCode', 'city', 'country'):
                value = root.findtext(field_name, '').strip()
                if value:
                    setattr(user, field_name, value)

            success, error = self._replace_user_snapshot(user)
            if not success:
                logger.error("Failed to replace CRM user snapshot: %s", error)
                if self.on_error:
                    self.on_error(message_type, error)
                return False

            logger.info("%s processed: userId=%s (full replace)", message_type, user.userId)
            return True

        except Exception as e:
            error = f"Error handling {message_type}: {str(e)}"
            logger.error(error)
            if self.on_error:
                self.on_error(message_type, error)
            return False

    def _replace_user_snapshot(self, user: User) -> tuple[bool, Optional[str]]:
        """Replace the stored user object without merging partial fields."""
        existing_owner = self.user_store._badge_index.get(user.badgeCode)
        if existing_owner and existing_owner != user.userId:
            return False, f"badgeCode already in use: {user.badgeCode}"

        existing_user = self.user_store._users.get(user.userId)
        if existing_user and existing_user.badgeCode in self.user_store._badge_index:
            del self.user_store._badge_index[existing_user.badgeCode]

        self.user_store._users[user.userId] = user
        self.user_store._badge_index[user.badgeCode] = user.userId
        return True, None
