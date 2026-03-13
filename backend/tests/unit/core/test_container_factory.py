"""Tests for container factory helper ``_create_secrets_provider``."""

from unittest.mock import patch

from airweave.adapters.secrets import InMemorySecretsProvider
from airweave.adapters.secrets.azure_keyvault import AzureKeyVaultSecretsProvider
from airweave.core.config import Settings
from airweave.core.container.factory import _create_secrets_provider


def test_in_memory_provider_for_local():
    """InMemorySecretsProvider is returned when no vault is configured."""
    settings = Settings()

    provider = _create_secrets_provider(settings)

    assert isinstance(provider, InMemorySecretsProvider)
    assert provider._secrets == {}


def test_azure_keyvault_when_configured():
    """AzureKeyVaultSecretsProvider is returned when vault is configured."""
    settings = Settings(ENVIRONMENT="dev", AZURE_KEYVAULT_NAME="my-vault")

    with patch.object(AzureKeyVaultSecretsProvider, "__init__", return_value=None):
        provider = _create_secrets_provider(settings)

    assert isinstance(provider, AzureKeyVaultSecretsProvider)
