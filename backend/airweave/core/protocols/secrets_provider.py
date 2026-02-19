"""SecretsProvider protocol for secret retrieval.

Abstracts access to a secrets store (e.g. Azure Key Vault) behind a
simple async interface so that consumers never depend on a specific SDK.

Usage:
    secret = await secrets_provider.get_secret("my-api-key")

Raises:
    KeyError: If the requested secret does not exist.
    ConnectionError: If the secrets store is unreachable.
"""

from typing import Protocol, runtime_checkable


@runtime_checkable
class SecretsProvider(Protocol):
    """Protocol for retrieving secrets by name.

    Implementations must return the secret value as a plain ``str``.
    SDK-specific wrappers (e.g. unwrapping ``.value`` from Azure
    ``KeyVaultSecret``) are the adapter's responsibility.

    Raises:
        KeyError: If the secret does not exist in the store.
        ConnectionError: If the store is unreachable.
    """

    async def get_secret(self, name: str) -> str:
        """Retrieve a secret by name.

        Args:
            name: The identifier of the secret (e.g. ``"my-api-key"``).

        Returns:
            The secret value as a plain string.
        """
        ...
