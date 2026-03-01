"""Tests for OrganizationLifecycleOperations saga logic.

Verifies the create and delete sagas handle every failure mode correctly:
- Typed exceptions propagate (loud 500s, never swallowed)
- Compensation cleans up exactly the resources that were created
- After local commit, external resources are NOT rolled back
- Delete cleanup failures are best-effort and don't block the delete
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch
from uuid import UUID, uuid4

import pytest

from airweave import schemas
from airweave.adapters.event_bus.fake import FakeEventBus
from airweave.adapters.identity.fake import FakeIdentityProvider
from airweave.adapters.payment.fake import FakePaymentGateway
from airweave.adapters.webhooks.fake import FakeWebhookAdmin
from airweave.core.protocols.identity import (
    IdentityProviderError,
    IdentityProviderRateLimitError,
    IdentityProviderUnavailableError,
)
from airweave.core.protocols.payment import (
    PaymentProviderError,
    PaymentProviderRateLimitError,
)
from airweave.domains.billing.fakes.operations import FakeBillingOperations
from airweave.domains.organizations.fakes.repository import (
    FakeOrganizationRepository,
    FakeUserOrganizationRepository,
)
from airweave.domains.organizations.operations import OrganizationLifecycleOperations


# ---------------------------------------------------------------------------
# Minimal fake for OrganizationBillingRepositoryProtocol (only get_by_org_id)
# ---------------------------------------------------------------------------


class _FakeBillingRepo:
    """Stub for OrganizationBillingRepositoryProtocol used in delete tests."""

    def __init__(self):
        self._records: dict[UUID, object] = {}

    def seed(self, organization_id: UUID, *, stripe_subscription_id: str):
        self._records[organization_id] = type(
            "_B", (), {"stripe_subscription_id": stripe_subscription_id}
        )()

    async def get_by_org_id(self, db, *, organization_id: UUID):
        return self._records.get(organization_id)


# ---------------------------------------------------------------------------
# Helpers — plain stubs to avoid SQLAlchemy instrumentation
# ---------------------------------------------------------------------------


class _UserStub:
    """Lightweight stand-in for models.User (no SQLAlchemy descriptor overhead)."""

    def __init__(self, *, user_id=None, email="owner@test.com", auth0_id="auth0|user123"):
        self.id = user_id or uuid4()
        self.email = email
        self.auth0_id = auth0_id
        self.full_name = "Test Owner"


class _OrgStub:
    """Lightweight stand-in for models.Organization."""

    def __init__(self, *, org_id=None, name="Test Org", auth0_org_id=None):
        self.id = org_id or uuid4()
        self.name = name
        self.auth0_org_id = auth0_org_id


def _make_user(**kwargs):
    return _UserStub(**kwargs)


def _make_org_model(**kwargs):
    return _OrgStub(**kwargs)


def _make_org_schema(org_id=None, name="Test Org"):
    return schemas.Organization(
        id=org_id or uuid4(),
        name=name,
        description=None,
        auth0_org_id="org_abc",
        created_at=datetime.now(timezone.utc),
        modified_at=datetime.now(timezone.utc),
        org_metadata=None,
        role="owner",
    )


def _make_operations(
    *,
    identity=None,
    payment=None,
    event_bus=None,
    org_repo=None,
    user_org_repo=None,
    billing_ops=None,
    billing_repo=None,
    webhook_admin=None,
):
    return OrganizationLifecycleOperations(
        org_repo=org_repo or FakeOrganizationRepository(),
        user_org_repo=user_org_repo or FakeUserOrganizationRepository(),
        identity_provider=identity or FakeIdentityProvider(),
        payment_gateway=payment or FakePaymentGateway(),
        billing_ops=billing_ops or FakeBillingOperations(),
        billing_repo=billing_repo or _FakeBillingRepo(),
        webhook_admin=webhook_admin or FakeWebhookAdmin(),
        event_bus=event_bus or FakeEventBus(),
    )


ORG_DATA = schemas.OrganizationCreate(name="Acme Corp", description="Test org")


# ===========================================================================
# CREATE — happy path
# ===========================================================================


class TestCreateHappyPath:
    @pytest.mark.asyncio
    async def test_returns_organization_schema(self):
        identity = FakeIdentityProvider()
        payment = FakePaymentGateway()
        event_bus = FakeEventBus()
        ops = _make_operations(identity=identity, payment=payment, event_bus=event_bus)
        fake_org = _make_org_schema()

        with patch.object(ops, "_create_local", new_callable=AsyncMock, return_value=fake_org):
            result = await ops.create_organization(AsyncMock(), ORG_DATA, _make_user())

        assert result.id == fake_org.id
        assert result.name == fake_org.name

    @pytest.mark.asyncio
    async def test_calls_identity_provider(self):
        identity = FakeIdentityProvider()
        ops = _make_operations(identity=identity)

        with patch.object(ops, "_create_local", new_callable=AsyncMock, return_value=_make_org_schema()):
            await ops.create_organization(AsyncMock(), ORG_DATA, _make_user())

        identity.assert_called("create_organization")
        identity.assert_called("add_user_to_organization")
        identity.assert_called("get_all_connections")

    @pytest.mark.asyncio
    async def test_calls_payment_provider(self):
        payment = FakePaymentGateway()
        ops = _make_operations(payment=payment)

        with patch.object(ops, "_create_local", new_callable=AsyncMock, return_value=_make_org_schema()):
            await ops.create_organization(AsyncMock(), ORG_DATA, _make_user())

        assert payment.call_count("create_customer") == 1

    @pytest.mark.asyncio
    async def test_publishes_created_event(self):
        event_bus = FakeEventBus()
        ops = _make_operations(event_bus=event_bus)

        with patch.object(ops, "_create_local", new_callable=AsyncMock, return_value=_make_org_schema()):
            await ops.create_organization(AsyncMock(), ORG_DATA, _make_user())

        event_bus.assert_published("organization.created")


# ===========================================================================
# CREATE — identity provider failures
# ===========================================================================


class TestCreateIdentityFailures:
    @pytest.mark.asyncio
    async def test_create_org_error_propagates(self):
        """IdentityProviderError on create_organization must propagate — loud 500."""
        identity = FakeIdentityProvider()
        identity.fail_with = IdentityProviderError("Auth0 down")
        ops = _make_operations(identity=identity)

        with pytest.raises(IdentityProviderError, match="Auth0 down"):
            await ops.create_organization(AsyncMock(), ORG_DATA, _make_user())

    @pytest.mark.asyncio
    async def test_create_org_error_no_compensation_needed(self):
        """If create_organization fails, no org was created — nothing to compensate."""
        identity = FakeIdentityProvider()
        identity.fail_with = IdentityProviderError("boom")
        payment = FakePaymentGateway()
        ops = _make_operations(identity=identity, payment=payment)

        with pytest.raises(IdentityProviderError):
            await ops.create_organization(AsyncMock(), ORG_DATA, _make_user())

        assert payment.call_count("create_customer") == 0
        assert payment.call_count("delete_customer") == 0

    @pytest.mark.asyncio
    async def test_rate_limit_propagates_as_typed_error(self):
        """Rate limit must surface as IdentityProviderRateLimitError, not generic."""
        identity = FakeIdentityProvider()
        identity.fail_with = IdentityProviderRateLimitError("slow down")
        ops = _make_operations(identity=identity)

        with pytest.raises(IdentityProviderRateLimitError):
            await ops.create_organization(AsyncMock(), ORG_DATA, _make_user())

    @pytest.mark.asyncio
    async def test_add_user_fails_compensates_identity_org(self):
        """If add_user fails, the identity org was created and must be cleaned up."""
        identity = FakeIdentityProvider()
        payment = FakePaymentGateway()
        ops = _make_operations(identity=identity, payment=payment)

        call_count = 0

        original_add_user = identity.add_user_to_organization

        async def fail_on_add_user(org_id, user_id):
            nonlocal call_count
            call_count += 1
            raise IdentityProviderError("add_user exploded")

        identity.add_user_to_organization = fail_on_add_user

        with pytest.raises(IdentityProviderError, match="add_user exploded"):
            await ops.create_organization(AsyncMock(), ORG_DATA, _make_user())

        # Org was created then deleted in compensation
        assert identity.call_count("create_organization") == 1
        assert identity.call_count("delete_organization") == 1

    @pytest.mark.asyncio
    async def test_setup_connections_fails_compensates_identity_org(self):
        """If _setup_connections fails, identity org must be cleaned up."""
        identity = FakeIdentityProvider()
        ops = _make_operations(identity=identity)

        async def fail_get_connections():
            identity._calls.append(("get_all_connections",))
            raise IdentityProviderUnavailableError("connections unavailable")

        identity.get_all_connections = fail_get_connections

        with pytest.raises(IdentityProviderUnavailableError):
            await ops.create_organization(AsyncMock(), ORG_DATA, _make_user())

        assert identity.call_count("delete_organization") == 1


# ===========================================================================
# CREATE — payment provider failures
# ===========================================================================


class TestCreatePaymentFailures:
    @pytest.mark.asyncio
    async def test_payment_error_propagates(self):
        """PaymentProviderError must propagate — loud 500."""
        payment = FakePaymentGateway(should_raise=PaymentProviderError("Stripe down"))
        ops = _make_operations(payment=payment)

        with pytest.raises(PaymentProviderError, match="Stripe down"):
            await ops.create_organization(AsyncMock(), ORG_DATA, _make_user())

    @pytest.mark.asyncio
    async def test_payment_error_compensates_identity_org(self):
        """Payment failure after identity success → identity org cleaned up."""
        identity = FakeIdentityProvider()
        payment = FakePaymentGateway(should_raise=PaymentProviderError("boom"))
        ops = _make_operations(identity=identity, payment=payment)

        with pytest.raises(PaymentProviderError):
            await ops.create_organization(AsyncMock(), ORG_DATA, _make_user())

        assert identity.call_count("create_organization") == 1
        assert identity.call_count("delete_organization") == 1

    @pytest.mark.asyncio
    async def test_payment_rate_limit_propagates_as_typed_error(self):
        """Rate limit must surface as PaymentProviderRateLimitError."""
        payment = FakePaymentGateway(should_raise=PaymentProviderRateLimitError("throttled"))
        ops = _make_operations(payment=payment)

        with pytest.raises(PaymentProviderRateLimitError):
            await ops.create_organization(AsyncMock(), ORG_DATA, _make_user())

    @pytest.mark.asyncio
    async def test_payment_failure_does_not_try_to_delete_customer(self):
        """If create_customer fails, there is no customer to delete."""
        payment = FakePaymentGateway(should_raise=PaymentProviderError("nope"))
        ops = _make_operations(payment=payment)

        with pytest.raises(PaymentProviderError):
            await ops.create_organization(AsyncMock(), ORG_DATA, _make_user())

        assert payment.call_count("delete_customer") == 0


# ===========================================================================
# CREATE — local DB failure
# ===========================================================================


class TestCreateLocalFailure:
    @pytest.mark.asyncio
    async def test_local_failure_compensates_both_external_resources(self):
        """If local UoW fails, both identity org and payment customer are cleaned up."""
        identity = FakeIdentityProvider()
        payment = FakePaymentGateway()
        ops = _make_operations(identity=identity, payment=payment)

        with patch.object(
            ops, "_create_local", new_callable=AsyncMock, side_effect=RuntimeError("DB exploded")
        ):
            with pytest.raises(RuntimeError, match="DB exploded"):
                await ops.create_organization(AsyncMock(), ORG_DATA, _make_user())

        assert identity.call_count("delete_organization") == 1
        assert payment.call_count("delete_customer") == 1

    @pytest.mark.asyncio
    async def test_local_failure_does_not_publish_event(self):
        """If local UoW fails, no event should be published."""
        event_bus = FakeEventBus()
        ops = _make_operations(event_bus=event_bus)

        with patch.object(
            ops, "_create_local", new_callable=AsyncMock, side_effect=RuntimeError("DB down")
        ):
            with pytest.raises(RuntimeError):
                await ops.create_organization(AsyncMock(), ORG_DATA, _make_user())

        event_bus.assert_not_published("organization.created")


# ===========================================================================
# CREATE — compensation itself fails
# ===========================================================================


class TestCreateCompensationFailure:
    @pytest.mark.asyncio
    async def test_original_error_propagates_when_compensation_also_fails(self):
        """If the primary call AND compensation both fail, the ORIGINAL error propagates."""
        identity = FakeIdentityProvider()
        payment = FakePaymentGateway(should_raise=PaymentProviderError("primary fail"))
        ops = _make_operations(identity=identity, payment=payment)

        # Make compensation also fail
        async def exploding_delete(org_id):
            raise RuntimeError("compensation also failed")

        identity.delete_organization = exploding_delete

        with pytest.raises(PaymentProviderError, match="primary fail"):
            await ops.create_organization(AsyncMock(), ORG_DATA, _make_user())


# ===========================================================================
# CREATE — event bus failure after commit (the bug we fixed)
# ===========================================================================


class TestCreateEventBusFailureAfterCommit:
    @pytest.mark.asyncio
    async def test_event_bus_failure_does_not_compensate_external_resources(self):
        """After local commit, event bus failure must NOT roll back external resources.

        This was a real bug: the event publish was inside the compensation
        try/except, so an event bus failure would delete Auth0 + Stripe
        while the local DB record persisted → orphaned org.
        """
        identity = FakeIdentityProvider()
        payment = FakePaymentGateway()
        failing_bus = FakeEventBus()

        original_publish = failing_bus.publish

        async def explode_on_publish(event):
            raise RuntimeError("event bus exploded")

        failing_bus.publish = explode_on_publish

        ops = _make_operations(identity=identity, payment=payment, event_bus=failing_bus)

        with patch.object(ops, "_create_local", new_callable=AsyncMock, return_value=_make_org_schema()):
            with pytest.raises(RuntimeError, match="event bus exploded"):
                await ops.create_organization(AsyncMock(), ORG_DATA, _make_user())

        # External resources must NOT be cleaned up
        assert identity.call_count("delete_organization") == 0
        assert payment.call_count("delete_customer") == 0


# ===========================================================================
# DELETE — happy path
# ===========================================================================


class TestDeleteHappyPath:
    @pytest.mark.asyncio
    async def test_returns_true(self):
        org_repo = FakeOrganizationRepository()
        user_org_repo = FakeUserOrganizationRepository()
        event_bus = FakeEventBus()
        org_id = uuid4()

        org = _make_org_model(org_id=org_id, name="Doomed Org", auth0_org_id="org_xyz")
        org_repo.seed(org_id, org)

        ops = _make_operations(
            org_repo=org_repo, user_org_repo=user_org_repo, event_bus=event_bus,
        )
        result = await ops.delete_organization(AsyncMock(), org_id, _make_user())
        assert result is True

    @pytest.mark.asyncio
    async def test_publishes_deleted_event(self):
        org_repo = FakeOrganizationRepository()
        user_org_repo = FakeUserOrganizationRepository()
        event_bus = FakeEventBus()
        org_id = uuid4()

        org = _make_org_model(org_id=org_id, name="Doomed", auth0_org_id=None)
        org_repo.seed(org_id, org)

        ops = _make_operations(
            org_repo=org_repo, user_org_repo=user_org_repo, event_bus=event_bus,
        )
        await ops.delete_organization(AsyncMock(), org_id, _make_user())
        event_bus.assert_published("organization.deleted")


# ===========================================================================
# DELETE — org not found
# ===========================================================================


class TestDeleteOrgNotFound:
    @pytest.mark.asyncio
    async def test_raises_value_error(self):
        """Deleting a nonexistent org must raise — not silently return."""
        ops = _make_operations()

        with pytest.raises(ValueError, match="Organization not found"):
            await ops.delete_organization(AsyncMock(), uuid4(), _make_user())


# ===========================================================================
# DELETE — external cleanup failures (best-effort)
# ===========================================================================


class TestDeleteExternalCleanupFailures:
    @pytest.mark.asyncio
    async def test_identity_cleanup_failure_does_not_block_delete(self):
        """Identity provider failure during cleanup must not prevent delete."""
        identity = FakeIdentityProvider()
        event_bus = FakeEventBus()
        org_repo = FakeOrganizationRepository()
        user_org_repo = FakeUserOrganizationRepository()
        org_id = uuid4()

        org = _make_org_model(org_id=org_id, name="Test", auth0_org_id="org_fail")
        org_repo.seed(org_id, org)

        async def fail_delete(oid):
            raise IdentityProviderError("Auth0 cleanup failed")

        identity.delete_organization = fail_delete

        ops = _make_operations(
            org_repo=org_repo, user_org_repo=user_org_repo,
            identity=identity, event_bus=event_bus,
        )
        result = await ops.delete_organization(AsyncMock(), org_id, _make_user())
        assert result is True
        event_bus.assert_published("organization.deleted")

    @pytest.mark.asyncio
    async def test_payment_cleanup_failure_does_not_block_delete(self):
        """Payment provider failure during cleanup must not prevent delete."""
        payment = FakePaymentGateway()
        event_bus = FakeEventBus()
        org_repo = FakeOrganizationRepository()
        user_org_repo = FakeUserOrganizationRepository()
        billing_repo = _FakeBillingRepo()
        org_id = uuid4()

        org = _make_org_model(org_id=org_id, name="Test", auth0_org_id=None)
        org_repo.seed(org_id, org)
        billing_repo.seed(org_id, stripe_subscription_id="sub_xyz")

        async def fail_cancel(**kwargs):
            raise PaymentProviderError("Stripe cleanup failed")

        payment.cancel_subscription = fail_cancel

        ops = _make_operations(
            org_repo=org_repo, user_org_repo=user_org_repo,
            payment=payment, billing_repo=billing_repo, event_bus=event_bus,
        )
        result = await ops.delete_organization(AsyncMock(), org_id, _make_user())
        assert result is True
        event_bus.assert_published("organization.deleted")

    @pytest.mark.asyncio
    async def test_all_external_cleanup_fails_delete_still_succeeds(self):
        """Even if every external cleanup fails, delete returns True and publishes event."""
        identity = FakeIdentityProvider()
        payment = FakePaymentGateway()
        webhook_admin = FakeWebhookAdmin()
        event_bus = FakeEventBus()
        org_repo = FakeOrganizationRepository()
        user_org_repo = FakeUserOrganizationRepository()
        billing_repo = _FakeBillingRepo()
        org_id = uuid4()

        org = _make_org_model(org_id=org_id, name="Doomed", auth0_org_id="org_xyz")
        org_repo.seed(org_id, org)
        billing_repo.seed(org_id, stripe_subscription_id="sub_123")

        async def fail_identity(oid):
            raise IdentityProviderError("identity boom")

        async def fail_payment(**kw):
            raise PaymentProviderError("payment boom")

        async def fail_webhook(oid):
            raise RuntimeError("webhook boom")

        identity.delete_organization = fail_identity
        payment.cancel_subscription = fail_payment
        webhook_admin.delete_organization = fail_webhook

        ops = _make_operations(
            org_repo=org_repo, user_org_repo=user_org_repo,
            identity=identity, payment=payment,
            webhook_admin=webhook_admin, billing_repo=billing_repo,
            event_bus=event_bus,
        )
        result = await ops.delete_organization(AsyncMock(), org_id, _make_user())
        assert result is True
        event_bus.assert_published("organization.deleted")
