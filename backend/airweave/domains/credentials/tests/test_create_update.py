"""Unit tests for CredentialService.create_credential and update_credential.

Uses FakeIntegrationCredentialRepository and patches credentials.encrypt.
"""

from dataclasses import dataclass
from typing import Any, Optional
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from airweave.domains.credentials.fake_repository import FakeIntegrationCredentialRepository
from airweave.domains.credentials.service import CredentialService
from airweave.domains.credentials.tests.conftest import FakeAuthConfig, FakeSourceClass, make_entry
from airweave.domains.sources.fake import FakeSourceRegistry
from airweave.schemas.source_connection import AuthenticationMethod


def _make_service(registry: FakeSourceRegistry) -> tuple[CredentialService, FakeIntegrationCredentialRepository]:
    repo = FakeIntegrationCredentialRepository()
    return CredentialService(source_registry=registry, credential_repo=repo), repo


def _make_ctx() -> MagicMock:
    """Build a minimal mock RequestContext with organization.id."""
    ctx = MagicMock()
    ctx.organization.id = uuid4()
    return ctx


# ---------------------------------------------------------------------------
# create_credential
# ---------------------------------------------------------------------------


class TestCreateCredential:
    @pytest.mark.asyncio
    @patch("airweave.domains.credentials.service.credentials.encrypt", return_value="encrypted-blob")
    async def test_creates_with_dict_auth_fields(self, mock_encrypt):
        registry = FakeSourceRegistry()
        registry.seed(make_entry("stripe", "Stripe"))
        svc, repo = _make_service(registry)

        ctx = _make_ctx()
        result = await svc.create_credential(
            source_short_name="stripe",
            source_name="Stripe",
            auth_fields={"api_key": "sk_test_123"},
            organization_id=ctx.organization.id,
            auth_method=AuthenticationMethod.DIRECT,
            oauth_type=None,
            auth_config_class=None,
            db=MagicMock(),
            uow=MagicMock(),
            ctx=ctx,
        )

        assert result is not None
        assert repo.created_count == 1
        mock_encrypt.assert_called_once_with({"api_key": "sk_test_123"})

    @pytest.mark.asyncio
    @patch("airweave.domains.credentials.service.credentials.encrypt", return_value="encrypted-blob")
    async def test_creates_with_pydantic_model_auth_fields(self, mock_encrypt):
        registry = FakeSourceRegistry()
        registry.seed(make_entry("stripe", "Stripe"))
        svc, repo = _make_service(registry)

        auth_model = FakeAuthConfig(api_key="sk_test_456", api_secret="sec")
        ctx = _make_ctx()

        result = await svc.create_credential(
            source_short_name="stripe",
            source_name="Stripe",
            auth_fields=auth_model,
            organization_id=ctx.organization.id,
            auth_method=AuthenticationMethod.DIRECT,
            oauth_type=None,
            auth_config_class=None,
            db=MagicMock(),
            uow=MagicMock(),
            ctx=ctx,
        )

        assert result is not None
        assert repo.created_count == 1
        mock_encrypt.assert_called_once_with({"api_key": "sk_test_456", "api_secret": "sec"})

    @pytest.mark.asyncio
    @patch("airweave.domains.credentials.service.credentials.encrypt", return_value="encrypted")
    async def test_creates_with_oauth_type(self, mock_encrypt):
        registry = FakeSourceRegistry()
        registry.seed(make_entry("notion", "Notion"))
        svc, repo = _make_service(registry)

        ctx = _make_ctx()
        result = await svc.create_credential(
            source_short_name="notion",
            source_name="Notion",
            auth_fields={"access_token": "token123"},
            organization_id=ctx.organization.id,
            auth_method=AuthenticationMethod.OAUTH_TOKEN,
            oauth_type="with_refresh",
            auth_config_class=None,
            db=MagicMock(),
            uow=MagicMock(),
            ctx=ctx,
        )

        assert result is not None


# ---------------------------------------------------------------------------
# update_credential
# ---------------------------------------------------------------------------


class TestUpdateCredential:
    @pytest.mark.asyncio
    @patch("airweave.domains.credentials.service.credentials.encrypt", return_value="re-encrypted")
    async def test_updates_existing_credential(self, mock_encrypt):
        registry = FakeSourceRegistry()
        registry.seed(make_entry("stripe", "Stripe"))
        svc, repo = _make_service(registry)

        # Pre-seed a credential
        existing = MagicMock()
        existing.id = uuid4()
        repo._store[existing.id] = existing

        await svc.update_credential(
            credential_id=existing.id,
            auth_fields={"api_key": "new_key"},
            short_name="stripe",
            db=MagicMock(),
            uow=MagicMock(),
            ctx=_make_ctx(),
        )

        # validate_auth_fields is called, encrypt is called
        mock_encrypt.assert_called_once()

    @pytest.mark.asyncio
    @patch("airweave.domains.credentials.service.credentials.encrypt", return_value="encrypted")
    async def test_update_nonexistent_credential_is_noop(self, mock_encrypt):
        registry = FakeSourceRegistry()
        registry.seed(make_entry("stripe", "Stripe"))
        svc, repo = _make_service(registry)

        # No credential in repo -- update should silently skip
        await svc.update_credential(
            credential_id=uuid4(),
            auth_fields={"api_key": "val"},
            short_name="stripe",
            db=MagicMock(),
            uow=MagicMock(),
            ctx=_make_ctx(),
        )

        # encrypt is still called (validation happens before get)
        mock_encrypt.assert_called_once()
