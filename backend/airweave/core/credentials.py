"""The module that contains the logic for credentials."""

import json
from typing import Any, cast

from cryptography.fernet import Fernet

from airweave.core.config import settings


def get_encryption_fernet() -> Fernet:
    """Get Fernet instance for encryption/decryption.

    Returns:
    -------
        Fernet: The Fernet instance.
    """
    # Convert string key to bytes and create Fernet instance
    key = settings.ENCRYPTION_KEY.encode()
    return Fernet(key)


def encrypt(data: dict) -> str:
    """Encrypt dictionary data.

    Args:
    ----
        data (dict): The data to encrypt.

    Returns:
    -------
        str: The encrypted data.
    """
    f = get_encryption_fernet()
    # Convert dict to JSON string, encode to bytes, then encrypt
    json_str = json.dumps(data)
    encrypted_data = f.encrypt(json_str.encode())
    return encrypted_data.decode()


def decrypt(data: str) -> dict:
    """Decrypt dictionary data.

    Args:
    ----
        data (str): The encrypted data.

    Returns:
    -------
        dict: The decrypted data.
    """
    f = get_encryption_fernet()
    # Get encrypted data, decrypt it, decode to string, parse JSON
    decrypted_bytes = f.decrypt(data)
    return cast("dict[Any, Any]", json.loads(decrypted_bytes.decode()))
