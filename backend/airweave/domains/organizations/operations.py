"""Organization lifecycle operations — create and delete.

Saga pattern: external calls (Auth0, Stripe) first, local UoW second.
On local failure, compensate external resources.
On delete: local commit first, external cleanup best-effort after.
"""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from airweave import schemas
from airweave.core.config import settings
from airweave.core.context import BaseContext
from airweave.core.events.organization import OrganizationLifecycleEvent
from airweave.core.logging import logger
from airweave.core.protocols.event_bus import EventBus
from airweave.core.protocols.identity import IdentityProvider, IdentityProviderError
from airweave.core.protocols.payment import PaymentGatewayProtocol, PaymentProviderError
from airweave.core.protocols.webhooks import WebhookAdmin
from airweave.db.unit_of_work import UnitOfWork
from airweave.domains.billing.operations import BillingOperationsProtocol
from airweave.domains.billing.repository import OrganizationBillingRepositoryProtocol
from airweave.domains.organizations import logic
from airweave.domains.organizations.protocols import (
    OrganizationRepositoryProtocol,
    UserOrganizationRepositoryProtocol,
)
from airweave.models.user import User
from airweave.schemas.api_key import APIKeyCreate


class OrganizationLifecycleOperations:
    """Handles organization create and delete with proper saga/compensation."""

    def __init__(
        self,
        *,
        org_repo: OrganizationRepositoryProtocol,
        user_org_repo: UserOrganizationRepositoryProtocol,
        identity_provider: IdentityProvider,
        payment_gateway: PaymentGatewayProtocol,
        billing_ops: BillingOperationsProtocol,
        billing_repo: OrganizationBillingRepositoryProtocol,
        webhook_admin: WebhookAdmin,
        event_bus: EventBus,
    ) -> None:
        """Initialize OrganizationLifecycleOperations."""
        self._org_repo = org_repo
        self._user_org_repo = user_org_repo
        self._identity = identity_provider
        self._payment = payment_gateway
        self._billing_ops = billing_ops
        self._billing_repo = billing_repo
        self._webhook_admin = webhook_admin
        self._event_bus = event_bus

    # ------------------------------------------------------------------
    # Create
    # ------------------------------------------------------------------

    async def create_organization(
        self,
        db: AsyncSession,
        org_data: schemas.OrganizationCreate,
        owner_user: User,
    ) -> schemas.Organization:
        """Create organization: identity provider → payment → local DB.

        Saga order: external resources first, local UoW last.
        On failure, compensate exactly the external resources that were created.
        After local commit, never compensate (point of no return).
        """
        auth0_org_id: str | None = None
        stripe_customer_id: str | None = None

        try:
            auth0_org_id = await self._provision_identity_org(org_data.name, owner_user)
            stripe_customer_id = await self._provision_payment_customer(
                org_data, owner_user, auth0_org_id
            )
            organization = await self._create_local(
                db, org_data, owner_user, auth0_org_id, stripe_customer_id
            )
        except (IdentityProviderError, PaymentProviderError):
            logger.exception("External provider failed during org creation — compensating")
            await self._compensate_create(auth0_org_id, stripe_customer_id)
            raise
        except Exception:
            logger.exception("Unexpected failure during org creation — compensating")
            await self._compensate_create(auth0_org_id, stripe_customer_id)
            raise

        await self._event_bus.publish(
            OrganizationLifecycleEvent.created(
                organization_id=organization.id,
                organization_name=organization.name,
                owner_email=owner_user.email,
            )
        )
        return organization

    async def _provision_identity_org(self, org_name_display: str, owner_user: User) -> str | None:
        """Create identity provider org, add owner, enable connections.

        Returns the identity org ID, or None if the provider is disabled.
        On partial failure (org created but subsequent step fails), the org
        is deleted before re-raising so the caller doesn't need to track it.
        """
        org_name = logic.generate_org_name(org_name_display)
        auth0_org = await self._identity.create_organization(
            name=org_name, display_name=org_name_display
        )
        if not auth0_org:
            return None

        auth0_org_id = auth0_org["id"]
        try:
            await self._identity.add_user_to_organization(auth0_org_id, owner_user.auth0_id)

            all_conns = await self._identity.get_all_connections()
            for conn_id in logic.select_default_connections(all_conns):
                await self._identity.add_enabled_connection(auth0_org_id, conn_id)
        except Exception:
            try:
                await self._identity.delete_organization(auth0_org_id)
                logger.info(f"Rolled back partially-provisioned identity org {auth0_org_id}")
            except Exception:
                logger.critical(
                    f"COMPENSATION FAILED: orphaned identity org {auth0_org_id} — "
                    "requires manual cleanup",
                    exc_info=True,
                )
            raise

        logger.info(f"Provisioned identity org: {auth0_org_id}")
        return auth0_org_id  # type: ignore[no-any-return]

    async def _provision_payment_customer(
        self,
        org_data: schemas.OrganizationCreate,
        owner_user: User,
        auth0_org_id: str | None,
    ) -> str | None:
        """Create payment customer. Returns customer ID, or None if payments disabled."""
        test_clock_id = None
        if settings.ENVIRONMENT != "prd":
            test_clock_id = settings.STRIPE_TEST_CLOCK

        customer = await self._payment.create_customer(
            email=owner_user.email,
            name=org_data.name,
            metadata={
                "auth0_org_id": auth0_org_id or "",
                "owner_user_id": str(owner_user.id),
                "organization_name": org_data.name,
            },
            test_clock=test_clock_id,
        )
        if not customer:
            return None

        logger.info(f"Provisioned payment customer: {customer.id}")
        return customer.id  # type: ignore[no-any-return]

    async def _create_local(
        self,
        db: AsyncSession,
        org_data: schemas.OrganizationCreate,
        owner_user: User,
        auth0_org_id: str | None,
        stripe_customer_id: str | None,
    ) -> schemas.Organization:
        """Create all local records in a single UoW."""
        async with UnitOfWork(db) as uow:
            org_dict = org_data.model_dump()
            org_dict["auth0_org_id"] = auth0_org_id

            local_org = await self._org_repo.create_with_owner(
                db, obj_in=schemas.OrganizationCreate(**org_dict), owner_user=owner_user, uow=uow
            )

            await db.flush()
            await db.refresh(local_org)

            organization = schemas.Organization(
                id=local_org.id,  # type: ignore[arg-type]
                name=local_org.name,
                description=local_org.description,
                auth0_org_id=local_org.auth0_org_id,
                created_at=local_org.created_at,  # type: ignore[arg-type]
                modified_at=local_org.modified_at,  # type: ignore[arg-type]
                org_metadata=local_org.org_metadata,
                billing=None,
            )

            if stripe_customer_id:
                ctx = BaseContext(organization=organization)
                await self._billing_ops.create_billing_record(
                    db=db,
                    organization=local_org,
                    stripe_customer_id=stripe_customer_id,
                    billing_email=owner_user.email,
                    ctx=ctx,
                    uow=uow,
                )

            api_key_ctx = BaseContext(organization=organization)
            from airweave import crud

            await crud.api_key.create(db=db, obj_in=APIKeyCreate(), ctx=api_key_ctx, uow=uow)

            await uow.commit()
            return organization

    async def _compensate_create(
        self, auth0_org_id: str | None, stripe_customer_id: str | None
    ) -> None:
        """Best-effort rollback of external resources on failure.

        Compensation failures are logged at CRITICAL — they mean orphaned
        resources that require manual intervention.
        """
        if auth0_org_id:
            try:
                await self._identity.delete_organization(auth0_org_id)
                logger.info(f"Compensated: deleted identity org {auth0_org_id}")
            except Exception:
                logger.critical(
                    f"COMPENSATION FAILED: orphaned identity org {auth0_org_id} — "
                    "requires manual cleanup",
                    exc_info=True,
                )

        if stripe_customer_id:
            try:
                await self._payment.delete_customer(stripe_customer_id)
                logger.info(f"Compensated: deleted payment customer {stripe_customer_id}")
            except Exception:
                logger.critical(
                    f"COMPENSATION FAILED: orphaned payment customer {stripe_customer_id} — "
                    "requires manual cleanup",
                    exc_info=True,
                )

    # ------------------------------------------------------------------
    # Delete
    # ------------------------------------------------------------------

    async def delete_organization(
        self,
        db: AsyncSession,
        organization_id: UUID,
        deleting_user: User,
    ) -> bool:
        """Delete org: local commit first, external cleanup best-effort after.

        1. Fetch org + billing data (while rows still exist)
        2. Single UoW: delete memberships + delete org (CASCADE)
        3. After commit: identity, payment, webhook cleanup (best-effort)
        4. Publish domain event
        """
        org = await self._org_repo.get_by_id(
            db, organization_id=organization_id, skip_access_validation=True
        )
        if not org:
            raise ValueError("Organization not found")

        org_name = org.name
        org_auth0_id = org.auth0_org_id

        billing = await self._billing_repo.get_by_org_id(db, organization_id=organization_id)
        stripe_sub_id = billing.stripe_subscription_id if billing else None

        logger.info(f"Deleting organization {org_name} ({organization_id})")

        async with UnitOfWork(db) as uow:
            affected_emails = await self._user_org_repo.delete_all_for_org(
                db, organization_id=organization_id
            )
            await self._org_repo.delete(db, organization_id=organization_id)
            await uow.commit()

        # Point of no return — local delete committed.
        # External cleanup is best-effort; failures are logged, never swallowed silently.
        await self._cleanup_external_resources(org_auth0_id, stripe_sub_id, organization_id)

        await self._event_bus.publish(
            OrganizationLifecycleEvent.deleted(
                organization_id=organization_id,
                organization_name=org_name,
                affected_user_emails=affected_emails,
            )
        )

        logger.info(f"Deleted organization: {org_name}")
        return True

    async def _cleanup_external_resources(
        self,
        auth0_org_id: str | None,
        stripe_sub_id: str | None,
        organization_id: UUID,
    ) -> None:
        """Best-effort external cleanup after local delete is committed."""
        if auth0_org_id:
            try:
                await self._identity.delete_organization(auth0_org_id)
            except Exception:
                logger.error(
                    f"Failed to delete identity org {auth0_org_id} for {organization_id} — "
                    "orphaned resource requires manual cleanup",
                    exc_info=True,
                )

        if stripe_sub_id:
            try:
                await self._payment.cancel_subscription(
                    subscription_id=stripe_sub_id, at_period_end=False
                )
            except Exception:
                logger.error(
                    f"Failed to cancel subscription {stripe_sub_id} for {organization_id} — "
                    "orphaned resource requires manual cleanup",
                    exc_info=True,
                )

        try:
            await self._webhook_admin.delete_organization(organization_id)
        except Exception:
            logger.error(
                f"Failed to delete webhook org {organization_id} — "
                "orphaned resource requires manual cleanup",
                exc_info=True,
            )
