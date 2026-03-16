"""Fake secrets provider for testing.

Dict-backed implementation with an access log for test assertions.
Pattern matches ``FakeCircuitBreaker`` (``adapters/circuit_breaker/fake.py``).

For production/local use without test helpers, see
``InMemorySecretsProvider`` in ``in_memory.py``.
"""

from airweave.core.protocols.secrets_provider import SecretsProvider


class FakeSecretsProvider(SecretsProvider):
    """Test implementation of SecretsProvider.

    Secrets are seeded via the constructor or ``seed()`` and retrieved
    with ``get_secret()``.  Every retrieval is recorded in ``access_log``
    for assertions.

    Usage:
        fake = FakeSecretsProvider({"my-key": "s3cret"})
        value = await fake.get_secret("my-key")
        assert value == "s3cret"
        assert fake.access_log == ["my-key"]
    """

    def __init__(self, secrets: dict[str, str] | None = None) -> None:
        """Initialize with optional pre-seeded secrets."""
        self._secrets: dict[str, str] = dict(secrets) if secrets else {}
        self.access_log: list[str] = []

    async def get_secret(self, name: str) -> str:
        """Return a seeded secret or raise ``KeyError``.

        Args:
            name: The secret identifier.

        Returns:
            The seeded secret value.

        Raises:
            KeyError: If *name* was not seeded.
        """
        self.access_log.append(name)
        try:
            return self._secrets[name]
        except KeyError:
            raise KeyError(f"Secret not found: {name}") from None

    # ------------------------------------------------------------------
    # Test helpers
    # ------------------------------------------------------------------

    def seed(self, name: str, value: str) -> None:
        """Add or overwrite a secret."""
        self._secrets[name] = value

    def clear(self) -> None:
        """Reset all secrets and the access log."""
        self._secrets.clear()
        self.access_log.clear()
