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
            elif message_type == 'UserCreated':
                return self._handle_user_created(root)
            elif message_type == 'UserUpdatedIntegration':
                return self._handle_user_updated_integration(root)
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

    def _handle_user_created(self, root: ET.Element) -> bool:
        """
        Handle a UserCreated message from the integration service.
        Uses <userId> field (not <id>) — integration service format.
        """
        try:
            user_data = {
                'userId': root.findtext('userId', '').strip(),
                'firstName': root.findtext('firstName', '').strip(),
                'lastName': root.findtext('lastName', '').strip(),
                'email': root.findtext('email', '').strip(),
                'badgeCode': root.findtext('badgeCode', '').strip(),
                'role': root.findtext('role', '').strip(),
            }

            companyId = root.findtext('companyId', '').strip()
            if companyId:
                user_data['companyId'] = companyId

            createdAt = root.findtext('createdAt', '').strip()
            if createdAt:
                user_data['createdAt'] = createdAt

            if not user_data.get('badgeCode'):
                user_data['badgeCode'] = f"DEFAULT_{user_data['userId']}"

            user = User(**user_data)

            existing = self.user_store.get_user_by_id(user.userId)
            if not existing:
                success, error, _ = self.user_store.create_user(user)
            else:
                updates = {k: v for k, v in user_data.items() if v}
                success, error, _ = self.user_store.update_user(user.userId, updates)

            if not success:
                logger.error("Failed to process UserCreated: %s", error)
                if self.on_error:
                    self.on_error('UserCreated', error)
                return False

            logger.info("UserCreated processed: userId=%s", user.userId)
            return True

        except Exception as e:
            error = f"Error handling UserCreated: {str(e)}"
            logger.error(error)
            if self.on_error:
                self.on_error('UserCreated', error)
            return False

    def _handle_user_updated_integration(self, root: ET.Element) -> bool:
        """
        Handle a UserUpdatedIntegration message from the integration service.
        Uses <userId> field (not <id>) — integration service format.
        """
        try:
            user_id = root.findtext('userId', '').strip()

            updates = {
                'firstName': root.findtext('firstName', '').strip(),
                'lastName': root.findtext('lastName', '').strip(),
                'email': root.findtext('email', '').strip(),
                'role': root.findtext('role', '').strip(),
            }
            updates = {k: v for k, v in updates.items() if v}

            badgeCode = root.findtext('badgeCode', '').strip()
            if badgeCode:
                updates['badgeCode'] = badgeCode

            companyId = root.findtext('companyId', '').strip()
            if companyId:
                updates['companyId'] = companyId

            updatedAt = root.findtext('updatedAt', '').strip()
            if updatedAt:
                updates['updatedAt'] = updatedAt

            existing = self.user_store.get_user_by_id(user_id)
            if not existing:
                logger.warning("UserUpdatedIntegration for non-existent user, creating: userId=%s", user_id)
                if not updates.get('badgeCode'):
                    updates['badgeCode'] = f"DEFAULT_{user_id}"
                user = User(userId=user_id, **updates)
                success, error, _ = self.user_store.create_user(user)
            else:
                success, error, _ = self.user_store.update_user(user_id, updates)

            if not success:
                logger.error("Failed to process UserUpdatedIntegration: %s", error)
                if self.on_error:
                    self.on_error('UserUpdatedIntegration', error)
                return False

            logger.info("UserUpdatedIntegration processed: userId=%s", user_id)
            return True

        except Exception as e:
            error = f"Error handling UserUpdatedIntegration: {str(e)}"
            logger.error(error)
            if self.on_error:
                self.on_error('UserUpdatedIntegration', error)
            return False

    def _handle_user_confirmed(self, root: ET.Element) -> bool:
        """
        Handle a UserConfirmed message from CRM.
        
        Creates or updates user based on CRM confirmation.
        
        Args:
            root: XML Element of type UserConfirmed
        
        Returns:
            True on success, False otherwise
        """
        try:
            user_data = {
                'userId': root.findtext('id', '').strip(),
                'firstName': root.findtext('firstName', '').strip(),
                'lastName': root.findtext('lastName', '').strip(),
                'email': root.findtext('email', '').strip(),
                'badgeCode': root.findtext('badgeCode', '').strip(),
                'role': root.findtext('role', '').strip(),
            }
            
            # Optional fields
            companyId = root.findtext('companyId', '').strip()
            if companyId:
                user_data['companyId'] = companyId
            
            if not user_data.get('badgeCode'):
                user_data['badgeCode'] = f"DEFAULT_{user_data['userId']}"

            user = User(**user_data)
            
            # Create or update user
            existing_user = self.user_store.get_user_by_id(user.userId)
            if not existing_user:
                success, error, _ = self.user_store.create_user(user)
            else:
                updates = {k: v for k, v in user_data.items() if v}
                success, error, _ = self.user_store.update_user(user.userId, updates)
            
            if not success:
                logger.error("Failed to process UserConfirmed: %s", error)
                if self.on_error:
                    self.on_error('UserConfirmed', error)
                return False
            
            logger.info("UserConfirmed processed: userId=%s", user.userId)
            return True
        
        except Exception as e:
            error = f"Error handling UserConfirmed: {str(e)}"
            logger.error(error)
            if self.on_error:
                self.on_error('UserConfirmed', error)
            return False

    def _handle_user_updated(self, root: ET.Element) -> bool:
        """
        Handle a UserUpdated message from CRM.
        
        Updates existing user or creates if doesn't exist.
        
        Args:
            root: XML Element of type UserUpdated
        
        Returns:
            True on success, False otherwise
        """
        try:
            user_id = root.findtext('id', '').strip()
            
            updates = {
                'firstName': root.findtext('firstName', '').strip(),
                'lastName': root.findtext('lastName', '').strip(),
                'email': root.findtext('email', '').strip(),
                'role': root.findtext('role', '').strip(),
            }
            
            # Remove empty strings
            updates = {k: v for k, v in updates.items() if v}
            
            # Optional fields
            badgeCode = root.findtext('badgeCode', '').strip()
            if badgeCode:
                updates['badgeCode'] = badgeCode
            
            companyId = root.findtext('companyId', '').strip()
            if companyId:
                updates['companyId'] = companyId

            existing_user = self.user_store.get_user_by_id(user_id)
            if not existing_user:
                # Create user if doesn't exist
                logger.warning("UserUpdated for non-existent user, creating: userId=%s", user_id)
                # Create with minimum required fields
                if not updates.get('badgeCode'):
                    updates['badgeCode'] = f"DEFAULT_{user_id}"
                user = User(userId=user_id, **updates)
                success, error, _ = self.user_store.create_user(user)
            else:
                # Update existing user
                success, error, _ = self.user_store.update_user(user_id, updates)
            
            if not success:
                logger.error("Failed to process UserUpdated: %s", error)
                if self.on_error:
                    self.on_error('UserUpdated', error)
                return False
            
            logger.info("UserUpdated processed: userId=%s", user_id)
            return True
        
        except Exception as e:
            error = f"Error handling UserUpdated: {str(e)}"
            logger.error(error)
            if self.on_error:
                self.on_error('UserUpdated', error)
            return False

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
            
            # Delete user from store
            success, error = self.user_store.delete_user(user_id)
            if not success:
                logger.error("Failed to process UserDeactivated: %s", error)
                if self.on_error:
                    self.on_error('UserDeactivated', error)
                return False
            
            logger.info("UserDeactivated processed: userId=%s", user_id)
            return True
        
        except Exception as e:
            error = f"Error handling UserDeactivated: {str(e)}"
            logger.error(error)
            if self.on_error:
                self.on_error('UserDeactivated', error)
            return False
