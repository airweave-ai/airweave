"""Unit tests for OAuthCredentialRefresher and AuthProviderCredentialRefresher."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from airweave.core.exceptions import TokenRefreshError
from airweave.domains.credentials.refresher import (
    AuthProviderCredentialRefresher,
    OAuthCredentialRefresher,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_ctx():
    ctx = MagicMock()
    ctx.logger = MagicMock()
    return ctx


def _mock_oauth2_service(access_token: str = "new-oauth-token"):
    svc = MagicMock()
    resp = MagicMock()
    resp.access_token = access_token
    svc.refresh_access_token = AsyncMock(return_value=resp)
    return svc


def _mock_auth_provider(creds: dict | None = None):
    provider = MagicMock()
    provider.get_creds_for_source = AsyncMock(
        return_value=creds or {"access_token": "new-ap-token", "refresh_token": "rt"}
    )
    return provider


# ---------------------------------------------------------------------------
# OAuthCredentialRefresher
# ---------------------------------------------------------------------------


class TestOAuthCredentialRefresher:
    @pytest.mark.asyncio
    async def test_refresh_returns_new_access_token(self):
        oauth2 = _mock_oauth2_service("fresh-token")
        cred_id = uuid4()
        conn_id = uuid4()

        refresher = OAuthCredentialRefresher(
            source_short_name="github",
            connection_id=conn_id,
            integration_credential_id=cred_id,
            ctx=_mock_ctx(),
            config_fields=None,
            oauth2_service=oauth2,
        )

        fake_credential = MagicMock()
        fake_credential.encrypted_credentials = "encrypted"

        with (
            patch(
                "airweave.db.session.get_db_context"
            ) as mock_db_ctx,
            patch("airweave.domains.credentials.refresher.crud") as mock_crud,
            patch(
                "airweave.domains.credentials.refresher.credential_utils"
            ) as mock_cred_utils,
        ):
            mock_db = AsyncMock()
            mock_db_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_db)
            mock_db_ctx.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_crud.integration_credential.get = AsyncMock(
                return_value=fake_credential
            )
            mock_cred_utils.decrypt.return_value = {"access_token": "old", "refresh_token": "rt"}

            token = await refresher.refresh()

        assert token == "fresh-token"
        oauth2.refresh_access_token.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_refresh_raises_on_missing_credential(self):
        oauth2 = _mock_oauth2_service()

        refresher = OAuthCredentialRefresher(
            source_short_name="github",
            connection_id=uuid4(),
            integration_credential_id=uuid4(),
            ctx=_mock_ctx(),
            config_fields=None,
            oauth2_service=oauth2,
        )

        with (
            patch(
                "airweave.db.session.get_db_context"
            ) as mock_db_ctx,
            patch("airweave.domains.credentials.refresher.crud") as mock_crud,
        ):
            mock_db = AsyncMock()
            mock_db_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_db)
            mock_db_ctx.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_crud.integration_credential.get = AsyncMock(return_value=None)

            with pytest.raises(TokenRefreshError, match="not found"):
                await refresher.refresh()


# ---------------------------------------------------------------------------
# AuthProviderCredentialRefresher
# ---------------------------------------------------------------------------


class TestAuthProviderCredentialRefresher:
    @pytest.mark.asyncio
    async def test_refresh_returns_access_token(self):
        provider = _mock_auth_provider({"access_token": "ap-fresh", "extra": "data"})

        refresher = AuthProviderCredentialRefresher(
            auth_provider_instance=provider,
            source_short_name="jira",
            integration_credential_id=uuid4(),
            ctx=_mock_ctx(),
            runtime_auth_all_fields=["access_token", "refresh_token"],
            runtime_auth_optional_fields=set(),
        )

        with patch(
            "airweave.db.session.get_db_context"
        ) as mock_db_ctx, patch(
            "airweave.domains.credentials.refresher.crud"
        ) as mock_crud, patch(
            "airweave.domains.credentials.refresher.credential_utils"
        ) as mock_cred_utils:
            mock_db = AsyncMock()
            mock_db_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_db)
            mock_db_ctx.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_crud.integration_credential.get = AsyncMock(return_value=MagicMock())
            mock_crud.integration_credential.update = AsyncMock()
            mock_cred_utils.encrypt.return_value = "encrypted-blob"

            token = await refresher.refresh()

        assert token == "ap-fresh"
        provider.get_creds_for_source.assert_awaited_once_with(
            source_short_name="jira",
            source_auth_config_fields=["access_token", "refresh_token"],
            optional_fields=set(),
        )

    @pytest.mark.asyncio
    async def test_refresh_raises_when_no_access_token_returned(self):
        provider = _mock_auth_provider({"refresh_token": "rt-only"})

        refresher = AuthProviderCredentialRefresher(
            auth_provider_instance=provider,
            source_short_name="jira",
            integration_credential_id=None,
            ctx=_mock_ctx(),
            runtime_auth_all_fields=["access_token"],
            runtime_auth_optional_fields=set(),
        )

        with pytest.raises(TokenRefreshError, match="No access token"):
            await refresher.refresh()

    @pytest.mark.asyncio
    async def test_refresh_succeeds_even_when_persist_fails(self):
        provider = _mock_auth_provider({"access_token": "good-token"})

        refresher = AuthProviderCredentialRefresher(
            auth_provider_instance=provider,
            source_short_name="jira",
            integration_credential_id=uuid4(),
            ctx=_mock_ctx(),
            runtime_auth_all_fields=["access_token"],
            runtime_auth_optional_fields=set(),
        )

        with patch(
            "airweave.db.session.get_db_context"
        ) as mock_db_ctx, patch(
            "airweave.domains.credentials.refresher.credential_utils"
        ) as mock_cred_utils:
            mock_cred_utils.encrypt.return_value = "encrypted-blob"
            mock_db_ctx.return_value.__aenter__ = AsyncMock(
                side_effect=Exception("DB down")
            )
            mock_db_ctx.return_value.__aexit__ = AsyncMock(return_value=False)

            token = await refresher.refresh()

        assert token == "good-token"
