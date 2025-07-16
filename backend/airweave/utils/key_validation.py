"""Utilities for validating and sanitizing private keys and other sensitive credentials."""

import re
import logging
from typing import Optional, Dict, List, Union, Any

logger = logging.getLogger(__name__)

# Regular expressions for validation
ETHEREUM_PRIVATE_KEY_PATTERN = r"^(0x)?[0-9a-fA-F]{64}$"
ETHEREUM_ADDRESS_PATTERN = r"^(0x)?[0-9a-fA-F]{40}$"
API_KEY_PATTERN = r"^[A-Za-z0-9\-_]{8,}$"  # Minimum 8 characters of alphanumeric, dash, underscore


def is_valid_ethereum_private_key(private_key: str) -> bool:
    """Validate if a string is a valid Ethereum private key.
    
    Args:
        private_key: The private key to validate
        
    Returns:
        True if the private key format is valid, False otherwise
    """
    if not private_key:
        return False
        
    # Remove 0x prefix if present
    if private_key.startswith("0x"):
        private_key = private_key[2:]
        
    # Check if it's a 64-character hex string
    return len(private_key) == 64 and all(c in "0123456789abcdefABCDEF" for c in private_key)


def is_valid_ethereum_address(address: str) -> bool:
    """Validate if a string is a valid Ethereum address format.
    
    Args:
        address: The address to validate
        
    Returns:
        True if the address format is valid, False otherwise
    """
    if not address:
        return False
        
    # Match against pattern
    if not re.match(ETHEREUM_ADDRESS_PATTERN, address):
        return False
    
    # Remove 0x prefix if present for further validation
    if address.startswith("0x"):
        address = address[2:]
    
    # Check if it's a 40-character hex string
    return len(address) == 40 and all(c in "0123456789abcdefABCDEF" for c in address)


def is_valid_api_key(api_key: str) -> bool:
    """Validate if a string matches typical API key patterns.
    
    Args:
        api_key: The API key to validate
        
    Returns:
        True if the API key format is valid, False otherwise
    """
    if not api_key or len(api_key) < 8:
        return False
        
    # Check for common API key patterns
    return re.match(API_KEY_PATTERN, api_key) is not None


def sanitize_private_key(private_key: str) -> str:
    """Sanitize a private key for storage.
    
    Args:
        private_key: The private key to sanitize
        
    Returns:
        The sanitized private key
    """
    if not private_key:
        return ""
        
    # Trim whitespace
    sanitized = private_key.strip()
    
    # Ensure 0x prefix
    if not sanitized.startswith("0x") and is_valid_ethereum_private_key(sanitized):
        sanitized = f"0x{sanitized}"
        
    return sanitized


def mask_private_key(private_key: str) -> str:
    """Mask a private key for logging or display.
    
    Args:
        private_key: The private key to mask
        
    Returns:
        The masked private key
    """
    if not private_key:
        return ""
        
    # Remove 0x prefix if present
    has_prefix = False
    if private_key.startswith("0x"):
        private_key = private_key[2:]
        has_prefix = True
        
    # Keep first 4 and last 4 characters, mask the rest
    if len(private_key) <= 8:
        masked = "**" + private_key[-2:] if len(private_key) >= 2 else "****"
    else:
        masked = private_key[:4] + "*" * (len(private_key) - 8) + private_key[-4:]
        
    # Restore 0x prefix if it was present
    if has_prefix:
        masked = f"0x{masked}"
        
    return masked


def validate_and_sanitize_key_input(key_data: Dict[str, Any]) -> Dict[str, Any]:
    """Validate and sanitize key input data.
    
    Args:
        key_data: Dictionary containing key information
        
    Returns:
        Sanitized key data dictionary
        
    Raises:
        ValueError: If the key data is invalid
    """
    # Make a copy to avoid modifying the original
    sanitized = key_data.copy()
    
    # Check key type
    key_type = sanitized.get("key_type")
    if not key_type:
        raise ValueError("Key type is required")
    
    # Validate and sanitize based on key type
    if key_type == "ethereum_private_key":
        private_key = sanitized.get("key_value")
        if not private_key:
            raise ValueError("Private key value is required")
            
        if not is_valid_ethereum_private_key(private_key):
            raise ValueError("Invalid Ethereum private key format")
            
        sanitized["key_value"] = sanitize_private_key(private_key)
        
    elif key_type == "api_key":
        api_key = sanitized.get("key_value")
        if not api_key:
            raise ValueError("API key value is required")
            
        if not is_valid_api_key(api_key):
            raise ValueError("Invalid API key format")
            
        # API keys are usually not transformed, just trimmed
        sanitized["key_value"] = api_key.strip()
        
    else:
        # Generic handling for other key types
        if not sanitized.get("key_value"):
            raise ValueError("Key value is required")
            
    # Ensure key has an ID for storage
    if not sanitized.get("key_id"):
        raise ValueError("Key ID is required")
        
    return sanitized