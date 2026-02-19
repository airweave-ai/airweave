"""Unit tests for SecretsProvider implementations."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from airweave.adapters.secrets.fake import FakeSecretsProvider
from airweave.adapters.secrets.in_memory import InMemorySecretsProvider


# ---------------------------------------------------------------------------
# InMemorySecretsProvider
# ---------------------------------------------------------------------------


class TestInMemorySecretsProvider:
    """Smoke tests for the dict-backed local/CI provider."""

    @pytest.mark.asyncio
    async def test_get_seeded_secret(self):
        provider = InMemorySecretsProvider({"db-password": "hunter2"})
        assert await provider.get_secret("db-password") == "hunter2"

    @pytest.mark.asyncio
    async def test_missing_key_raises_key_error(self):
        provider = InMemorySecretsProvider()
        with pytest.raises(KeyError, match="no-such-key"):
            await provider.get_secret("no-such-key")

    @pytest.mark.asyncio
    async def test_empty_provider_raises_key_error(self):
        provider = InMemorySecretsProvider(secrets=None)
        with pytest.raises(KeyError):
            await provider.get_secret("anything")

    @pytest.mark.asyncio
    async def test_multiple_secrets(self):
        provider = InMemorySecretsProvider({"a": "1", "b": "2"})
        assert await provider.get_secret("a") == "1"
        assert await provider.get_secret("b") == "2"


# ---------------------------------------------------------------------------
# FakeSecretsProvider
# ---------------------------------------------------------------------------


class TestFakeSecretsProvider:
    """Tests for the dict-backed fake."""

    @pytest.mark.asyncio
    async def test_get_seeded_secret(self):
        fake = FakeSecretsProvider({"api-key": "s3cret"})
        assert await fake.get_secret("api-key") == "s3cret"

    @pytest.mark.asyncio
    async def test_missing_key_raises_key_error(self):
        fake = FakeSecretsProvider()
        with pytest.raises(KeyError, match="no-such-key"):
            await fake.get_secret("no-such-key")

    @pytest.mark.asyncio
    async def test_access_log_tracks_retrievals(self):
        fake = FakeSecretsProvider({"a": "1", "b": "2"})
        await fake.get_secret("a")
        await fake.get_secret("b")
        await fake.get_secret("a")
        assert fake.access_log == ["a", "b", "a"]

    @pytest.mark.asyncio
    async def test_access_log_records_failed_lookups(self):
        fake = FakeSecretsProvider()
        with pytest.raises(KeyError):
            await fake.get_secret("missing")
        assert fake.access_log == ["missing"]

    @pytest.mark.asyncio
    async def test_seed_overwrites_existing(self):
        fake = FakeSecretsProvider({"k": "old"})
        fake.seed("k", "new")
        assert await fake.get_secret("k") == "new"

    @pytest.mark.asyncio
    async def test_seed_adds_new(self):
        fake = FakeSecretsProvider()
        fake.seed("k", "val")
        assert await fake.get_secret("k") == "val"

    def test_clear_resets_everything(self):
        fake = FakeSecretsProvider({"k": "v"})
        fake.access_log.append("k")
        fake.clear()
        assert fake.access_log == []
        assert fake._secrets == {}


# ---------------------------------------------------------------------------
# AzureKeyVaultSecretsProvider
# ---------------------------------------------------------------------------

_AZURE_MODULE = "airweave.adapters.secrets.azure_keyvault"


class TestAzureKeyVaultSecretsProvider:
    """Tests that the Azure adapter unwraps .value correctly."""

    def _make_provider(self, mock_client):
        """Create provider with a mocked SDK client."""
        with patch(
            f"{_AZURE_MODULE}.SecretClient",
            return_value=mock_client,
        ), patch(
            f"{_AZURE_MODULE}.DefaultAzureCredential",
        ):
            from airweave.adapters.secrets.azure_keyvault import (
                AzureKeyVaultSecretsProvider,
            )

            return AzureKeyVaultSecretsProvider(vault_name="test-vault")

    @pytest.mark.asyncio
    async def test_get_secret_unwraps_value(self):
        """The adapter should return secret.value, not the SDK object."""
        mock_kv_secret = MagicMock()
        mock_kv_secret.value = "plain-string"

        mock_client = AsyncMock()
        mock_client.get_secret.return_value = mock_kv_secret

        provider = self._make_provider(mock_client)
        result = await provider.get_secret("my-secret")

        assert result == "plain-string"
        mock_client.get_secret.assert_awaited_once_with("my-secret")

    @pytest.mark.asyncio
    async def test_none_value_raises_key_error(self):
        """A secret that exists but has no value should raise KeyError."""
        mock_kv_secret = MagicMock()
        mock_kv_secret.value = None

        mock_client = AsyncMock()
        mock_client.get_secret.return_value = mock_kv_secret

        provider = self._make_provider(mock_client)

        with pytest.raises(KeyError, match="exists but has no value"):
            await provider.get_secret("empty-secret")

    @pytest.mark.asyncio
    async def test_not_found_raises_key_error(self):
        """ResourceNotFoundError from Azure SDK should become KeyError."""
        from azure.core.exceptions import ResourceNotFoundError

        mock_client = AsyncMock()
        mock_client.get_secret.side_effect = ResourceNotFoundError("not found")

        provider = self._make_provider(mock_client)

        with pytest.raises(KeyError, match="Secret not found"):
            await provider.get_secret("no-such-secret")

    @pytest.mark.asyncio
    async def test_azure_sdk_error_raises_connection_error(self):
        """Non-404 Azure SDK errors should become ConnectionError."""
        from azure.core.exceptions import ServiceRequestError

        mock_client = AsyncMock()
        mock_client.get_secret.side_effect = ServiceRequestError("DNS failure")

        provider = self._make_provider(mock_client)

        with pytest.raises(ConnectionError, match="Key Vault unreachable"):
            await provider.get_secret("any-secret")
