"""Azure Key Vault adapter for SecretsProvider.

Wraps the Azure SDK ``SecretClient`` so that consumers depend only on the
``SecretsProvider`` protocol, never on Azure types directly.
"""

from azure.core.exceptions import AzureError, ResourceNotFoundError
from azure.identity.aio import DefaultAzureCredential
from azure.keyvault.secrets.aio import SecretClient

from airweave.core.protocols.secrets_provider import SecretsProvider


class AzureKeyVaultSecretsProvider(SecretsProvider):
    """SecretsProvider backed by Azure Key Vault.

    The constructor accepts a *vault_name* (injected by the container
    factory from ``settings.AZURE_KEYVAULT_NAME``).  The SDK client is
    created eagerly so connection problems surface at startup.

    Implements: ``SecretsProvider``
    """

    def __init__(self, vault_name: str) -> None:
        """Create provider for the given Key Vault instance."""
        vault_url = f"https://{vault_name}.vault.azure.net/"
        self._client = SecretClient(
            vault_url=vault_url,
            credential=DefaultAzureCredential(),
        )

    async def get_secret(self, name: str) -> str:
        """Retrieve a secret from Azure Key Vault.

        Args:
            name: The secret identifier in Key Vault.

        Returns:
            The secret value as a plain string.

        Raises:
            KeyError: If the secret does not exist or has no value.
            ConnectionError: If Key Vault is unreachable.
        """
        try:
            secret = await self._client.get_secret(name)
        except ResourceNotFoundError:
            raise KeyError(f"Secret not found: {name}") from None
        except AzureError as e:
            raise ConnectionError(f"Key Vault unreachable: {e}") from e

        if secret.value is None:
            raise KeyError(f"Secret '{name}' exists but has no value")

        return secret.value
