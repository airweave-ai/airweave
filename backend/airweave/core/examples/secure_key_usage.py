"""Example usage of the secure key management system."""

import logging
import asyncio
from typing import Optional, Dict, Any

from airweave.core.secure_keys import secure_key_manager
from airweave.utils.key_validation import (
    is_valid_ethereum_private_key, 
    validate_and_sanitize_key_input, 
    mask_private_key
)

logger = logging.getLogger(__name__)


async def store_api_credentials(
    service_name: str, 
    api_key: str, 
    api_secret: Optional[str] = None
) -> bool:
    """Store API credentials securely.
    
    Args:
        service_name: Name of the service (e.g., "stripe", "github")
        api_key: The API key
        api_secret: Optional API secret or token
        
    Returns:
        True if successful, False otherwise
    """
    try:
        # Generate key IDs
        key_id = f"{service_name}_api_key"
        secret_id = f"{service_name}_api_secret"
        
        # Validate input
        key_data = {
            "key_type": "api_key",
            "key_id": key_id,
            "key_value": api_key
        }
        
        # Sanitize and validate
        try:
            sanitized = validate_and_sanitize_key_input(key_data)
            api_key = sanitized["key_value"]
        except ValueError as e:
            logger.error(f"Invalid API key for {service_name}: {e}")
            return False
            
        # Store the API key
        success = await secure_key_manager.store_api_key(key_id, api_key)
        if not success:
            logger.error(f"Failed to store API key for {service_name}")
            return False
            
        # Store the API secret if provided
        if api_secret:
            secret_data = {
                "key_type": "api_key",
                "key_id": secret_id,
                "key_value": api_secret
            }
            
            try:
                sanitized = validate_and_sanitize_key_input(secret_data)
                api_secret = sanitized["key_value"]
            except ValueError as e:
                logger.error(f"Invalid API secret for {service_name}: {e}")
                # Roll back the API key storage
                await secure_key_manager.delete_key("api_key", key_id)
                return False
                
            success = await secure_key_manager.store_api_key(secret_id, api_secret)
            if not success:
                logger.error(f"Failed to store API secret for {service_name}")
                # Roll back the API key storage
                await secure_key_manager.delete_key("api_key", key_id)
                return False
                
        logger.info(f"Successfully stored API credentials for {service_name}")
        return True
    except Exception as e:
        logger.error(f"Error storing API credentials for {service_name}: {e}")
        return False


async def store_ethereum_wallet(
    wallet_name: str, 
    private_key: str, 
    address: Optional[str] = None
) -> bool:
    """Store Ethereum wallet credentials securely.
    
    Args:
        wallet_name: Name or identifier for the wallet
        private_key: The private key
        address: Optional Ethereum address (will be derived if not provided)
        
    Returns:
        True if successful, False otherwise
    """
    try:
        # Generate key IDs
        key_id = f"{wallet_name}_private_key"
        
        # Validate private key
        if not is_valid_ethereum_private_key(private_key):
            logger.error(f"Invalid Ethereum private key format for {wallet_name}")
            return False
            
        # Store the private key
        masked_key = mask_private_key(private_key)
        logger.info(f"Storing private key {masked_key} for wallet {wallet_name}")
        
        success = await secure_key_manager.store_private_key(key_id, private_key)
        if not success:
            logger.error(f"Failed to store private key for {wallet_name}")
            return False
            
        logger.info(f"Successfully stored Ethereum wallet for {wallet_name}")
        return True
    except Exception as e:
        logger.error(f"Error storing Ethereum wallet for {wallet_name}: {e}")
        return False


async def retrieve_and_use_api_key(service_name: str) -> Optional[Dict[str, Any]]:
    """Retrieve and use an API key securely.
    
    Args:
        service_name: Name of the service (e.g., "stripe", "github")
        
    Returns:
        Dictionary with API response or None if failed
    """
    try:
        # Generate key ID
        key_id = f"{service_name}_api_key"
        
        # Retrieve the API key
        api_key = await secure_key_manager.get_api_key(key_id)
        if not api_key:
            logger.error(f"API key not found for {service_name}")
            return None
            
        # In a real implementation, we would use the API key to make a request
        # For this example, we just return a mock response
        logger.info(f"Using API key for {service_name} to make request")
        
        # Mock API response
        return {
            "success": True,
            "service": service_name,
            "response": "API request successful"
        }
    except Exception as e:
        logger.error(f"Error using API key for {service_name}: {e}")
        return None


async def retrieve_and_use_ethereum_wallet(wallet_name: str) -> Optional[Dict[str, Any]]:
    """Retrieve and use an Ethereum wallet securely.
    
    Args:
        wallet_name: Name or identifier for the wallet
        
    Returns:
        Dictionary with transaction data or None if failed
    """
    try:
        # Generate key ID
        key_id = f"{wallet_name}_private_key"
        
        # Retrieve the private key
        private_key = await secure_key_manager.get_private_key(key_id)
        if not private_key:
            logger.error(f"Private key not found for {wallet_name}")
            return None
            
        # In a real implementation, we would use the private key to sign a transaction
        # For this example, we just return a mock transaction
        masked_key = mask_private_key(private_key)
        logger.info(f"Using private key {masked_key} for wallet {wallet_name} to sign transaction")
        
        # Mock transaction
        return {
            "success": True,
            "wallet": wallet_name,
            "transaction": {
                "hash": "0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef",
                "status": "confirmed"
            }
        }
    except Exception as e:
        logger.error(f"Error using Ethereum wallet for {wallet_name}: {e}")
        return None


async def demo():
    """Run a demonstration of the secure key management system."""
    # Store API credentials
    await store_api_credentials(
        service_name="example_service",
        api_key="api_key_12345",
        api_secret="api_secret_67890"
    )
    
    # Store Ethereum wallet
    await store_ethereum_wallet(
        wallet_name="example_wallet",
        private_key="0x0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
    )
    
    # Use API key
    await retrieve_and_use_api_key("example_service")
    
    # Use Ethereum wallet
    await retrieve_and_use_ethereum_wallet("example_wallet")
    
    # Show access statistics
    stats = secure_key_manager.get_access_statistics()
    logger.info(f"Key access statistics: {stats}")


if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(level=logging.INFO)
    
    # Run the demo
    asyncio.run(demo())