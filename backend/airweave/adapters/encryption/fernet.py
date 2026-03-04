"""Fernet-based credential encryption adapter."""

from __future__ import annotations

import json
from typing import Any

from cryptography.fernet import Fernet


class FernetCredentialEncryptor:
    """Encrypt/decrypt credential dicts using Fernet symmetric encryption."""

    def __init__(self, encryption_key: str) -> None:
        self._fernet = Fernet(encryption_key.encode())

    def encrypt(self, data: dict[str, Any]) -> str:
        return self._fernet.encrypt(json.dumps(data).encode()).decode()

    def decrypt(self, encrypted: str) -> dict[str, Any]:
        return json.loads(self._fernet.decrypt(encrypted).decode())
