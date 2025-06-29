"""Module for securely handling API keys, private keys and other sensitive credentials."""

import logging
import hashlib
import time
from typing import Optional, Dict, Any
from functools import wraps

from airweave.core.secrets import secret_manager
from airweave.core.credentials import encrypt, decrypt
from airweave.core.config import settings

logger = logging.getLogger(__name__)

# Define key prefixes for different key types
KEY_PREFIX_API = "api_key_"
KEY_PREFIX_PRIVATE_KEY = "private_key_"
KEY_PREFIX_TOKEN = "token_"


class KeyAccessMonitor:
    """Monitor and log access to sensitive keys and credentials."""
    
    def __init__(self):
        """Initialize the key access monitor."""
        self.access_log: Dict[str, Dict[str, Any]] = {}
    
    def log_access(self, key_id: str, access_type: str, source: str) -> None:
        """Log access to a key.
        
        Args:
            key_id: The identifier for the key (hashed or masked)
            access_type: Type of access (read/write/delete)
            source: Source of the access (function/method name)
        """
        timestamp = time.time()
        key_hash = self._hash_key_id(key_id)
        
        if key_hash not in self.access_log:
            self.access_log[key_hash] = {
                "first_access": timestamp,
                "access_count": 0,
                "access_history": []
            }
            
        # Update access log
        self.access_log[key_hash]["access_count"] += 1
        self.access_log[key_hash]["last_access"] = timestamp
        
        # Keep last 10 accesses
        access_entry = {"timestamp": timestamp, "type": access_type, "source": source}
        self.access_log[key_hash]["access_history"].append(access_entry)
        if len(self.access_log[key_hash]["access_history"]) > 10:
            self.access_log[key_hash]["access_history"].pop(0)
        
        # Log the access for security auditing
        logger.info(
            f"Secure key access: {self._mask_key_id(key_id)} - {access_type} from {source}"
        )
    
    def _hash_key_id(self, key_id: str) -> str:
        """Create a hash of the key ID for internal tracking.
        
        Args:
            key_id: The key identifier
            
        Returns:
            Hashed key ID
        """
        return hashlib.sha256(f"{key_id}-{settings.ENCRYPTION_KEY}".encode()).hexdigest()
    
    def _mask_key_id(self, key_id: str) -> str:
        """Create a masked version of the key ID for logging.
        
        Args:
            key_id: The key identifier
            
        Returns:
            Masked key ID
        """
        if len(key_id) <= 8:
            return "***" + key_id[-2:] if len(key_id) >= 2 else "***"
        else:
            return key_id[:3] + "***" + key_id[-2:]
    
    def get_access_statistics(self) -> Dict[str, Any]:
        """Get statistics about key access.
        
        Returns:
            Dictionary with access statistics
        """
        result = {
            "total_keys_tracked": len(self.access_log),
            "total_accesses": sum(log["access_count"] for log in self.access_log.values()),
            "keys": {}
        }
        
        # Add per-key statistics (without revealing the actual keys)
        for key_hash, log in self.access_log.items():
            key_prefix = key_hash[:6]  # Use part of hash as identifier
            result["keys"][key_prefix] = {
                "access_count": log["access_count"],
                "first_access": log["first_access"],
                "last_access": log.get("last_access", log["first_access"])
            }
        
        return result


# Create singleton instance
key_monitor = KeyAccessMonitor()


def log_key_access(access_type: str):
    """Decorator to log key access.
    
    Args:
        access_type: Type of access (read/write/delete)
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Get key_id from args or kwargs
            key_id = None
            if len(args) > 1:
                key_id = args[1]  # Assuming first arg is self, second is key_id
            elif "key_id" in kwargs:
                key_id = kwargs["key_id"]
                
            if key_id:
                source = func.__name__
                key_monitor.log_access(key_id, access_type, source)
                
            return await func(*args, **kwargs)
        return wrapper
    return decorator


class SecureKeyManager:
    """Manager for securely handling sensitive keys and credentials."""
    
    def __init__(self):
        """Initialize the secure key manager."""
        pass
    
    @log_key_access("read")
    async def get_api_key(self, key_id: str) -> Optional[str]:
        """Securely retrieve an API key.
        
        Args:
            key_id: The key identifier
            
        Returns:
            The API key or None if not found
        """
        secret_key = f"{KEY_PREFIX_API}{key_id}"
        
        # Try to get from secure storage first
        key_value = await secret_manager.get_secret(secret_key)
        if key_value:
            return key_value
            
        # If not in secure storage, check for encrypted value
        # This could be used during migration from old storage to new
        try:
            # Check if there's an encrypted version in the database 
            # (implementation would depend on your database structure)
            # This is a placeholder for actual implementation
            return None
        except Exception as e:
            logger.error(f"Error retrieving API key: {e}")
            return None
            
    @log_key_access("write")
    async def store_api_key(self, key_id: str, api_key: str) -> bool:
        """Securely store an API key.
        
        Args:
            key_id: The key identifier
            api_key: The API key to store
            
        Returns:
            True if successful, False otherwise
        """
        secret_key = f"{KEY_PREFIX_API}{key_id}"
        
        # Store in secure storage
        success = await secret_manager.set_secret(secret_key, api_key)
        
        if not success:
            logger.error(f"Failed to store API key in secure storage")
            
        return success
            
    @log_key_access("read")
    async def get_private_key(self, key_id: str) -> Optional[str]:
        """Securely retrieve a private key.
        
        Args:
            key_id: The key identifier
            
        Returns:
            The private key or None if not found
        """
        secret_key = f"{KEY_PREFIX_PRIVATE_KEY}{key_id}"
        
        # Try to get from secure storage first
        key_value = await secret_manager.get_secret(secret_key)
        if key_value:
            return key_value
            
        # If not in secure storage, check for encrypted value
        return None
            
    @log_key_access("write")
    async def store_private_key(self, key_id: str, private_key: str) -> bool:
        """Securely store a private key.
        
        Args:
            key_id: The key identifier
            private_key: The private key to store
            
        Returns:
            True if successful, False otherwise
        """
        secret_key = f"{KEY_PREFIX_PRIVATE_KEY}{key_id}"
        
        # Store in secure storage
        success = await secret_manager.set_secret(secret_key, private_key)
        
        if not success:
            logger.error(f"Failed to store private key in secure storage")
            
        return success
    
    @log_key_access("read")
    async def get_token(self, token_id: str) -> Optional[Dict[str, Any]]:
        """Securely retrieve a token (such as OAuth2 tokens).
        
        Args:
            token_id: The token identifier
            
        Returns:
            The token data or None if not found
        """
        secret_key = f"{KEY_PREFIX_TOKEN}{token_id}"
        
        # Try to get from secure storage first
        token_value = await secret_manager.get_secret(secret_key)
        if token_value:
            try:
                # Token may be stored as JSON string
                if token_value.startswith("{") and token_value.endswith("}"):
                    import json
                    return json.loads(token_value)
                # Or it might be a simple string
                return {"token": token_value}
            except Exception as e:
                logger.error(f"Error parsing token data: {e}")
                return {"token": token_value}
                
        # If not in secure storage, try to get from encrypted storage
        try:
            # Implementation would depend on your database structure
            return None
        except Exception as e:
            logger.error(f"Error retrieving token: {e}")
            return None
            
    @log_key_access("write")
    async def store_token(self, token_id: str, token_data: Dict[str, Any]) -> bool:
        """Securely store a token.
        
        Args:
            token_id: The token identifier
            token_data: The token data to store
            
        Returns:
            True if successful, False otherwise
        """
        secret_key = f"{KEY_PREFIX_TOKEN}{token_id}"
        
        try:
            # Convert token data to string for storage
            import json
            token_value = json.dumps(token_data)
            
            # Store in secure storage
            success = await secret_manager.set_secret(secret_key, token_value)
            
            if not success:
                logger.error(f"Failed to store token in secure storage")
                
            return success
        except Exception as e:
            logger.error(f"Error storing token: {e}")
            return False
    
    @log_key_access("delete")
    async def delete_key(self, key_type: str, key_id: str) -> bool:
        """Delete a key from secure storage.
        
        Args:
            key_type: Type of key (api_key, private_key, token)
            key_id: The key identifier
            
        Returns:
            True if successful, False otherwise
        """
        if key_type == "api_key":
            prefix = KEY_PREFIX_API
        elif key_type == "private_key":
            prefix = KEY_PREFIX_PRIVATE_KEY
        elif key_type == "token":
            prefix = KEY_PREFIX_TOKEN
        else:
            logger.error(f"Unsupported key type: {key_type}")
            return False
            
        secret_key = f"{prefix}{key_id}"
        
        # Implement deletion from secure storage
        # This is a placeholder - actual implementation would depend on your secret manager
        try:
            # For now we just nullify the secret by setting it to an empty string
            # A full implementation would include a delete method in the SecretManager
            success = await secret_manager.set_secret(secret_key, "")
            return success
        except Exception as e:
            logger.error(f"Error deleting key: {e}")
            return False
    
    def get_access_statistics(self) -> Dict[str, Any]:
        """Get statistics about key access.
        
        Returns:
            Dictionary with access statistics
        """
        return key_monitor.get_access_statistics()


# Create singleton instance
secure_key_manager = SecureKeyManager()