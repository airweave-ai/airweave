"""Tests for UserService create-or-update and org query logic.

All I/O is faked — no database or external providers.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from airweave import schemas
from airweave.adapters.email.fake import FakeEmailService
from airweave.domains.organizations.fakes.repository import FakeUserOrganizationRepository
from airweave.domains.organizations.fakes.service import FakeOrganizationService
from airweave.domains.users.fakes.repository import FakeUserRepository
from airweave.domains.users.service import UserService

# ---------------------------------------------------------------------------
# Stubs
# ---------------------------------------------------------------------------


class _Auth0UserStub:
    """Lightweight stand-in for fastapi_auth0.Auth0User."""

    def __init__(self, *, user_id="auth0|user123", email="user@test.com"):
        self.id = user_id
        self.email = email


def _make_user_create(email="user@test.com", full_name="Test User", auth0_id=None):
    return schemas.UserCreate(email=email, full_name=full_name, auth0_id=auth0_id)


class _UserStub:
    """Lightweight stand-in for models.User (no SQLAlchemy descriptor overhead)."""

    def __init__(
        self, *, user_id=None, email="user@test.com", auth0_id="auth0|user123", full_name="Test"
    ):
        self.id = user_id or uuid4()
        self.email = email
        self.auth0_id = auth0_id
        self.full_name = full_name


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def _make_service(
    *,
    user_repo=None,
    org_service=None,
    user_org_repo=None,
    email_service=None,
):
    return UserService(
        user_repo=user_repo or FakeUserRepository(),
        org_service=org_service or FakeOrganizationService(),
        user_org_repo=user_org_repo or FakeUserOrganizationRepository(),
        email_service=email_service or FakeEmailService(),
    )


# ===========================================================================
# create_or_update — new user (happy path)
# ===========================================================================


class TestCreateOrUpdateNewUser:
    @pytest.mark.asyncio
    async def test_creates_new_user_via_org_service(self):
        user_repo = FakeUserRepository()
        org_service = FakeOrganizationService()

        new_user = _UserStub(email="new@test.com")
        org_service.provision_new_user = AsyncMock(return_value=new_user)

        svc = _make_service(user_repo=user_repo, org_service=org_service)
        db = AsyncMock()

        result = await svc.create_or_update(
            db, _make_user_create(email="new@test.com"), _Auth0UserStub(email="new@test.com")
        )

        assert result.is_new is True
        assert result.user.email == "new@test.com"
        org_service.provision_new_user.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_sets_auth0_id_from_auth0_user(self):
        user_repo = FakeUserRepository()
        org_service = FakeOrganizationService()

        captured_data = {}

        async def capture_provision(db, user_dict, *, create_org=False):
            captured_data.update(user_dict)
            return _UserStub(email=user_dict["email"], auth0_id=user_dict.get("auth0_id"))

        org_service.provision_new_user = capture_provision

        svc = _make_service(user_repo=user_repo, org_service=org_service)
        db = AsyncMock()

        await svc.create_or_update(
            db,
            _make_user_create(email="new@test.com"),
            _Auth0UserStub(user_id="auth0|new123", email="new@test.com"),
        )

        assert captured_data["auth0_id"] == "auth0|new123"


# ===========================================================================
# create_or_update — existing user (happy path)
# ===========================================================================


class TestCreateOrUpdateExistingUser:
    @pytest.mark.asyncio
    async def test_syncs_orgs_for_existing_user(self):
        existing = _UserStub(email="exist@test.com", auth0_id="auth0|existing")
        user_repo = FakeUserRepository()
        user_repo.seed("exist@test.com", existing)

        org_service = FakeOrganizationService()
        org_service.sync_user_organizations = AsyncMock(return_value=existing)

        svc = _make_service(user_repo=user_repo, org_service=org_service)
        db = AsyncMock()

        result = await svc.create_or_update(
            db,
            _make_user_create(email="exist@test.com"),
            _Auth0UserStub(user_id="auth0|existing", email="exist@test.com"),
        )

        assert result.is_new is False
        assert result.user.email == "exist@test.com"
        org_service.sync_user_organizations.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_returns_existing_user_when_sync_fails(self):
        existing = _UserStub(email="exist@test.com", auth0_id="auth0|existing")
        user_repo = FakeUserRepository()
        user_repo.seed("exist@test.com", existing)

        org_service = FakeOrganizationService()
        org_service.sync_user_organizations = AsyncMock(side_effect=RuntimeError("sync failed"))

        svc = _make_service(user_repo=user_repo, org_service=org_service)
        db = AsyncMock()

        result = await svc.create_or_update(
            db,
            _make_user_create(email="exist@test.com"),
            _Auth0UserStub(user_id="auth0|existing", email="exist@test.com"),
        )

        assert result.is_new is False
        assert result.user.email == "exist@test.com"

    @pytest.mark.asyncio
    async def test_does_not_send_welcome_email(self):
        existing = _UserStub(email="exist@test.com", auth0_id="auth0|existing")
        user_repo = FakeUserRepository()
        user_repo.seed("exist@test.com", existing)

        org_service = FakeOrganizationService()
        org_service.sync_user_organizations = AsyncMock(return_value=existing)
        email = FakeEmailService()

        svc = _make_service(user_repo=user_repo, org_service=org_service, email_service=email)
        db = AsyncMock()

        await svc.create_or_update(
            db,
            _make_user_create(email="exist@test.com"),
            _Auth0UserStub(user_id="auth0|existing", email="exist@test.com"),
        )

        email.assert_not_called("send_welcome")


# ===========================================================================
# create_or_update — auth0_id update (email is source of truth)
# ===========================================================================


class TestCreateOrUpdateAuth0IdUpdate:
    @pytest.mark.asyncio
    async def test_updates_auth0_id_on_mismatch(self):
        existing = _UserStub(email="user@test.com", auth0_id="auth0|old_id")
        user_repo = FakeUserRepository()
        user_repo.seed("user@test.com", existing)

        org_service = FakeOrganizationService()
        org_service.sync_user_organizations = AsyncMock(return_value=existing)

        svc = _make_service(user_repo=user_repo, org_service=org_service)
        db = AsyncMock()

        result = await svc.create_or_update(
            db,
            _make_user_create(email="user@test.com"),
            _Auth0UserStub(user_id="auth0|new_id", email="user@test.com"),
        )

        assert result.is_new is False
        assert existing.auth0_id == "auth0|new_id"
        assert user_repo.call_count("update_user_no_auth") == 1

    @pytest.mark.asyncio
    async def test_sets_auth0_id_when_none(self):
        existing = _UserStub(email="user@test.com", auth0_id=None)
        user_repo = FakeUserRepository()
        user_repo.seed("user@test.com", existing)

        org_service = FakeOrganizationService()
        org_service.sync_user_organizations = AsyncMock(return_value=existing)

        svc = _make_service(user_repo=user_repo, org_service=org_service)
        db = AsyncMock()

        result = await svc.create_or_update(
            db,
            _make_user_create(email="user@test.com"),
            _Auth0UserStub(user_id="auth0|new_id", email="user@test.com"),
        )
        assert result.is_new is False
        assert existing.auth0_id == "auth0|new_id"

    @pytest.mark.asyncio
    async def test_no_update_when_ids_match(self):
        existing = _UserStub(email="user@test.com", auth0_id="auth0|same")
        user_repo = FakeUserRepository()
        user_repo.seed("user@test.com", existing)

        org_service = FakeOrganizationService()
        org_service.sync_user_organizations = AsyncMock(return_value=existing)

        svc = _make_service(user_repo=user_repo, org_service=org_service)
        db = AsyncMock()

        result = await svc.create_or_update(
            db,
            _make_user_create(email="user@test.com"),
            _Auth0UserStub(user_id="auth0|same", email="user@test.com"),
        )
        assert result.is_new is False
        assert user_repo.call_count("update_user_no_auth") == 0


# ===========================================================================
# create_or_update — provisioning fallback
# ===========================================================================


class TestCreateOrUpdateFallback:
    @pytest.mark.asyncio
    async def test_falls_back_to_crud_when_provision_fails(self):
        user_repo = FakeUserRepository()
        org_service = FakeOrganizationService()
        org_service.provision_new_user = AsyncMock(side_effect=RuntimeError("Auth0 down"))

        svc = _make_service(user_repo=user_repo, org_service=org_service)
        db = AsyncMock()

        from airweave.domains.users.types import CreateOrUpdateResult

        svc._fallback_create = AsyncMock(
            return_value=CreateOrUpdateResult(
                user=schemas.User.model_validate(_UserStub(email="new@test.com")),
                is_new=True,
            )
        )

        result = await svc.create_or_update(
            db, _make_user_create(email="new@test.com"), _Auth0UserStub(email="new@test.com")
        )

        assert result.is_new is True
        svc._fallback_create.assert_awaited_once()


# ===========================================================================
# create_or_update — welcome email
# ===========================================================================


class TestCreateOrUpdateWelcomeEmail:
    @pytest.mark.asyncio
    async def test_sends_welcome_email_for_new_user(self):
        user_repo = FakeUserRepository()
        org_service = FakeOrganizationService()
        email = FakeEmailService()

        new_user = _UserStub(email="new@test.com", full_name="New User")
        org_service.provision_new_user = AsyncMock(return_value=new_user)

        svc = _make_service(user_repo=user_repo, org_service=org_service, email_service=email)
        db = AsyncMock()

        await svc.create_or_update(
            db, _make_user_create(email="new@test.com"), _Auth0UserStub(email="new@test.com")
        )

        email.assert_called("send_welcome")
        assert email.call_count("send_welcome") == 1
        call = email.get_calls("send_welcome")[0]
        assert call[1] == "new@test.com"

    @pytest.mark.asyncio
    async def test_email_failure_does_not_block_user_creation(self):
        user_repo = FakeUserRepository()
        org_service = FakeOrganizationService()
        email = FakeEmailService(should_raise=RuntimeError("SMTP down"))

        new_user = _UserStub(email="new@test.com")
        org_service.provision_new_user = AsyncMock(return_value=new_user)

        svc = _make_service(user_repo=user_repo, org_service=org_service, email_service=email)
        db = AsyncMock()

        result = await svc.create_or_update(
            db, _make_user_create(email="new@test.com"), _Auth0UserStub(email="new@test.com")
        )

        assert result.is_new is True
        assert result.user.email == "new@test.com"


# ===========================================================================
# get_user_organizations
# ===========================================================================


class TestGetUserOrganizations:
    @pytest.mark.asyncio
    async def test_delegates_to_user_org_repo(self):
        user_org_repo = FakeUserOrganizationRepository()
        svc = _make_service(user_org_repo=user_org_repo)
        db = AsyncMock()
        user_id = uuid4()

        result = await svc.get_user_organizations(db, user_id=user_id)

        assert isinstance(result, list)
        assert ("get_user_memberships_with_orgs", user_id) in user_org_repo._calls


# ===========================================================================
# _track_analytics — best-effort, never crashes
# ===========================================================================


class TestTrackAnalytics:
    def test_does_not_raise_on_analytics_failure(self):
        svc = _make_service()

        user_stub = SimpleNamespace(
            id=uuid4(), email="u@test.com", full_name="Test", auth0_id="auth0|x"
        )
        svc._track_analytics(user_stub)

    def test_swallows_exception_from_business_events(self):
        from unittest.mock import patch

        svc = _make_service()
        user_stub = SimpleNamespace(
            id=uuid4(), email="u@test.com", full_name="Test", auth0_id="auth0|x"
        )
        with patch(
            "airweave.domains.users.service.business_events.track_user_created",
            side_effect=RuntimeError("PostHog unreachable"),
        ):
            svc._track_analytics(user_stub)


# ===========================================================================
# _send_welcome_from_schema — best-effort, swallows errors
# ===========================================================================


class TestSendWelcomeFromSchema:
    @pytest.mark.asyncio
    async def test_swallows_exception(self):
        email = FakeEmailService(should_raise=RuntimeError("SMTP down"))
        svc = _make_service(email_service=email)

        user_schema = schemas.User.model_validate(_UserStub(email="u@test.com", full_name="User"))
        await svc._send_welcome_from_schema(user_schema)

    @pytest.mark.asyncio
    async def test_sends_via_email_service(self):
        email = FakeEmailService()
        svc = _make_service(email_service=email)

        user_schema = schemas.User.model_validate(_UserStub(email="u@test.com", full_name="User"))
        await svc._send_welcome_from_schema(user_schema)

        email.assert_called("send_welcome")
        call = email.get_calls("send_welcome")[0]
        assert call[1] == "u@test.com"
        assert call[2] == "User"


# ===========================================================================
# _fallback_create — CRUD path when Auth0 integration is unavailable
# ===========================================================================


class TestFallbackCreate:
    @pytest.mark.asyncio
    async def test_creates_user_via_crud(self):
        from unittest.mock import patch

        fake_user = _UserStub(email="fallback@test.com", full_name="Fallback")
        fake_org = SimpleNamespace(id=uuid4(), name="Test Org")

        mock_uow = AsyncMock()
        mock_uow.__aenter__ = AsyncMock(return_value=mock_uow)
        mock_uow.__aexit__ = AsyncMock(return_value=False)

        svc = _make_service()
        db = AsyncMock()

        with (
            patch(
                "airweave.domains.users.service.UnitOfWork",
                return_value=mock_uow,
            ),
            patch(
                "airweave.domains.users.service.crud.user.create_with_organization",
                new_callable=AsyncMock,
                return_value=(fake_user, fake_org),
            ) as mock_create,
        ):
            result = await svc._fallback_create(db, _make_user_create(email="fallback@test.com"))

        assert result.is_new is True
        assert result.user.email == "fallback@test.com"
        mock_create.assert_awaited_once()
