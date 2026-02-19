"""In-memory secrets provider for local development.

Dict-backed implementation that returns pre-seeded secrets.  Used by the
container factory when no external vault is configured (local / CI).
For test-specific helpers (access logging, ``seed()``, ``clear()``), see
``FakeSecretsProvider`` in ``fake.py``.
"""

from airweave.core.protocols.secrets_provider import SecretsProvider


class InMemorySecretsProvider(SecretsProvider):
    """SecretsProvider backed by a plain dict.

    Suitable for local development and CI where no vault is available.
    Secrets can be pre-seeded via the constructor.
    """

    def __init__(self, secrets: dict[str, str] | None = None) -> None:
        """Initialize with optional pre-seeded secrets."""
        self._secrets: dict[str, str] = dict(secrets) if secrets else {}

    async def get_secret(self, name: str) -> str:
        """Return a stored secret or raise ``KeyError``.

        Args:
            name: The secret identifier.

        Returns:
            The secret value.

        Raises:
            KeyError: If *name* was not stored.
        """
        try:
            return self._secrets[name]
        except KeyError:
            raise KeyError(f"Secret not found: {name}") from None
