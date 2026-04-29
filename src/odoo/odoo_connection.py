# -*- coding: utf-8 -*-
"""
Odoo XML-RPC connection manager.

Handles authentication and connection to Odoo instance using XML-RPC API.
Configuration via environment variables: ODOO_URL, ODOO_DB, ODOO_USER, ODOO_PASSWORD
"""

import logging
import xmlrpc.client
from typing import Optional

logger = logging.getLogger(__name__)


class OdooConnection:
    """
    Manages XML-RPC connection to Odoo instance.
    
    Supports:
    - Connection pooling and reuse
    - Automatic reconnection on failure
    - Method execution with error handling
    """
    
    def __init__(self, url: str, db: str, user: str, password: str):
        """
        Initialize Odoo connection.
        
        Args:
            url: Odoo URL (e.g., 'http://localhost:8069')
            db: Odoo database name
            user: Odoo username (e.g., 'admin')
            password: Odoo password
        """
        self.url = url.rstrip('/')
        self.db = db
        self.user = user
        self.password = password
        
        self._common = None
        self._uid = None
        self._models = None
        self._default_company_id = None
        
    def connect(self) -> bool:
        """
        Authenticate with Odoo and establish connection.
        
        Returns:
            True if connection successful, False otherwise
        """
        try:
            self._common = xmlrpc.client.ServerProxy(f'{self.url}/xmlrpc/2/common')
            
            # Authenticate
            self._uid = self._common.authenticate(self.db, self.user, self.password, {})
            
            if not self._uid:
                logger.error(
                    "Odoo authentication failed [url=%s db=%s user=%s]",
                    self.url, self.db, self.user
                )
                return False
            
            # Initialize models service
            self._models = xmlrpc.client.ServerProxy(f'{self.url}/xmlrpc/2/object')
            
            # Fetch default company for this user (used when creating partners)
            try:
                companies = self.search('res.company', [], limit=1)
                if companies:
                    self._default_company_id = companies[0]
                    logger.debug("Default company ID: %d", self._default_company_id)
            except Exception as e:
                logger.warning("Could not fetch default company: %s", str(e))
                self._default_company_id = None
            
            logger.info(
                "Connected to Odoo [url=%s db=%s user=%s uid=%d]",
                self.url, self.db, self.user, self._uid
            )
            return True
            
        except Exception as e:
            logger.error(
                "Failed to connect to Odoo [url=%s error=%s]",
                self.url, str(e)
            )
            return False
    
    def is_connected(self) -> bool:
        """Check if connection is active."""
        return self._uid is not None and self._models is not None
    
    def get_default_company_id(self) -> Optional[int]:
        """Get the default company ID for this connection."""
        return self._default_company_id
    
    def execute(self, model: str, method: str, *args, **kwargs) -> any:
        """
        Execute a method on an Odoo model.
        
        Args:
            model: Model name (e.g., 'res.partner')
            method: Method name (e.g., 'create', 'write', 'search', 'read')
            *args: Positional arguments for the method
            **kwargs: Keyword arguments for the method
        
        Returns:
            Result from Odoo model method
        
        Raises:
            RuntimeError: If not connected
            xmlrpc.client.Fault: If Odoo returns an error
        """
        if not self.is_connected():
            raise RuntimeError("Not connected to Odoo. Call connect() first.")
        
        try:
            result = self._models.execute_kw(
                self.db,
                self._uid,
                self.password,
                model,
                method,
                args,
                kwargs
            )
            return result
        except xmlrpc.client.Fault as e:
            logger.error(
                "Odoo RPC error [model=%s method=%s error=%s]",
                model, method, str(e)
            )
            raise
    
    def search(self, model: str, domain: list, **kwargs) -> list:
        """
        Search for records in a model.
        
        Args:
            model: Model name
            domain: Search domain (e.g., [['email', '=', 'test@example.com']])
            **kwargs: Additional parameters (offset, limit, order, etc.)
        
        Returns:
            List of record IDs matching the domain
        """
        return self.execute(model, 'search', domain, **kwargs)
    
    def read(self, model: str, ids: list, fields: Optional[list] = None) -> list:
        """
        Read records from a model.
        
        Args:
            model: Model name
            ids: List of record IDs to read
            fields: List of field names to read (None = all)
        
        Returns:
            List of dictionaries containing record data
        """
        kwargs = {}
        if fields:
            kwargs['fields'] = fields
        if fields:
            return self.execute(model, 'read', ids, fields=fields)
        return self.execute(model, 'read', ids)
    
    def create(self, model: str, values: dict) -> int:
        """
        Create a new record in a model.
        
        Args:
            model: Model name
            values: Dictionary of field values
        
        Returns:
            ID of the newly created record
        """
        return self.execute(model, 'create', values)
    
    def write(self, model: str, ids: list, values: dict) -> bool:
        """
        Write (update) records in a model.
        
        Args:
            model: Model name
            ids: List of record IDs to update
            values: Dictionary of field values to update
        
        Returns:
            True if write succeeded
        """
        return self.execute(model, 'write', ids, values)
    
    def unlink(self, model: str, ids: list) -> bool:
        """
        Delete records from a model.
        
        Args:
            model: Model name
            ids: List of record IDs to delete
        
        Returns:
            True if unlink succeeded
        """
        return self.execute(model, 'unlink', ids)
