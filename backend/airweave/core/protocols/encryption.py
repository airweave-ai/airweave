"""Credential encryption protocol.

Defines the structural typing contract for encrypting/decrypting
credential dicts. Uses :class:`typing.Protocol` so implementations
don't need to inherit.

Usage::

    from airweave.core.protocols.encryption import CredentialEncryptor


    def refresh_token(encryptor: CredentialEncryptor) -> ...:
        creds = encryptor.decrypt(encrypted_blob)
        creds["access_token"] = new_token
        encrypted = encryptor.encrypt(creds)
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class CredentialEncryptor(Protocol):
    """Encrypt/decrypt credential dicts to/from opaque strings."""

    def encrypt(self, data: dict[str, Any]) -> str:
        """Encrypt a credential dict to an opaque string."""
        ...

    def decrypt(self, encrypted: str) -> dict[str, Any]:
        """Decrypt an opaque string back to a credential dict."""
        ...
