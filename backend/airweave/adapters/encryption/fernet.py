"""Fernet-based credential encryption adapter."""

from __future__ import annotations

import json

from cryptography.fernet import Fernet


class FernetCredentialEncryptor:
    """Encrypt/decrypt credential dicts using Fernet symmetric encryption."""

    def __init__(self, encryption_key: str) -> None:
        self._fernet = Fernet(encryption_key.encode())

    def encrypt(self, data: dict) -> str:
        return self._fernet.encrypt(json.dumps(data).encode()).decode()

    def decrypt(self, encrypted: str) -> dict:
        return json.loads(self._fernet.decrypt(encrypted).decode())
