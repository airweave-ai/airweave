"""Secrets adapters (SecretsProvider implementations)."""

from airweave.adapters.secrets.azure_keyvault import AzureKeyVaultSecretsProvider
from airweave.adapters.secrets.fake import FakeSecretsProvider
from airweave.adapters.secrets.in_memory import InMemorySecretsProvider

__all__ = [
    "AzureKeyVaultSecretsProvider",
    "FakeSecretsProvider",
    "InMemorySecretsProvider",
]
