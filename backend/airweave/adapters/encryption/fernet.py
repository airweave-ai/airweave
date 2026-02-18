"""Fernet-based credential encryption adapter.

Delegates to :mod:`airweave.core.credentials` which manages the
``ENCRYPTION_KEY`` setting and the :class:`cryptography.fernet.Fernet` instance.
"""

from __future__ import annotations

from airweave.core import credentials as _creds


class FernetCredentialEncryptor:
    """Encrypt/decrypt credential dicts using Fernet symmetric encryption."""

    def encrypt(self, data: dict) -> str:
        return _creds.encrypt(data)

    def decrypt(self, encrypted: str) -> dict:
        return _creds.decrypt(encrypted)
