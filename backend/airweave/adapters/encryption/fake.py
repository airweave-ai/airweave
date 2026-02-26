"""Fake credential encryptor for testing.

Round-trips dicts through a predictable transform without real crypto.
Records calls for assertions.
"""

from __future__ import annotations

from typing import Any, Optional


class FakeCredentialEncryptor:
    """Test implementation of CredentialEncryptor.

    Usage::

        fake = FakeCredentialEncryptor()
        blob = fake.encrypt({"access_token": "tok"})
        assert fake.decrypt(blob) == {}  # unless seeded

        fake.seed_decrypt({"access_token": "tok"})
        assert fake.decrypt(blob) == {"access_token": "tok"}
    """

    def __init__(self) -> None:
        self._encrypt_calls: list[dict[str, Any]] = []
        self._decrypt_calls: list[str] = []
        self._decrypt_return: Optional[dict[str, Any]] = None

    def seed_decrypt(self, result: dict[str, Any]) -> None:
        """Set the dict that :meth:`decrypt` will return."""
        self._decrypt_return = result

    def encrypt(self, data: dict[str, Any]) -> str:
        self._encrypt_calls.append(data)
        return f"encrypted:{id(data)}"

    def decrypt(self, encrypted: str) -> dict[str, Any]:
        self._decrypt_calls.append(encrypted)
        if self._decrypt_return is not None:
            return dict(self._decrypt_return)
        return {}
