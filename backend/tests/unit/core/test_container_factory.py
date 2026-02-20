"""Tests for container factory helper ``_create_secrets_provider``."""

from unittest.mock import patch

import pytest

from airweave.adapters.secrets import InMemorySecretsProvider
from airweave.adapters.secrets.azure_keyvault import AzureKeyVaultSecretsProvider
from airweave.core.config import Settings
from airweave.core.container.factory import _create_secrets_provider


@pytest.mark.parametrize(
    "access_key, secret_key, expected_keys",
    [
        ("AKID", "SECRET", {"aws-iam-access-key-id", "aws-iam-secret-access-key"}),
        ("AKID", None, {"aws-iam-access-key-id"}),
        (None, "SECRET", {"aws-iam-secret-access-key"}),
        (None, None, set()),
    ],
    ids=["both-keys", "access-key-only", "secret-key-only", "no-keys"],
)
def test_in_memory_provider_seeded_from_settings(access_key, secret_key, expected_keys):
    """InMemorySecretsProvider is seeded with S3 credentials from settings."""
    settings = Settings(
        AWS_S3_DESTINATION_ACCESS_KEY_ID=access_key,
        AWS_S3_DESTINATION_SECRET_ACCESS_KEY=secret_key,
    )

    provider = _create_secrets_provider(settings)

    assert isinstance(provider, InMemorySecretsProvider)
    assert set(provider._secrets) == expected_keys


def test_azure_keyvault_when_configured():
    """AzureKeyVaultSecretsProvider is returned when vault is configured."""
    settings = Settings(ENVIRONMENT="dev", AZURE_KEYVAULT_NAME="my-vault")

    with patch.object(AzureKeyVaultSecretsProvider, "__init__", return_value=None):
        provider = _create_secrets_provider(settings)

    assert isinstance(provider, AzureKeyVaultSecretsProvider)
