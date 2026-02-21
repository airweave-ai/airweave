"""Admin-only API endpoints for organization management.

TODO: Enhance CRUD layer to support bypassing organization filtering cleanly.
Currently admin endpoints manually construct SQLAlchemy queries to bypass ctx-based
org filtering. Consider adding a `skip_org_filter=True` parameter to CRUD methods
or a dedicated `crud_admin` module for cross-org operations.
"""

from datetime import datetime
from enum import Enum
from typing import List, Optional
from uuid import UUID

from fastapi import Body, Depends, HTTPException, Query
from pydantic import ConfigDict
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from airweave import crud, schemas
from airweave.api import deps
from airweave.api.context import ApiContext
from airweave.api.deps import Inject
from airweave.api.router import TrailingSlashRouter
from airweave.core.context_cache_service import context_cache
from airweave.core.exceptions import InvalidStateError, NotFoundException
from airweave.core.organization_service import organization_service
from airweave.core.protocols.payment import PaymentGatewayProtocol
from airweave.core.shared_models import FeatureFlag as FeatureFlagEnum
from airweave.core.temporal_service import temporal_service
from airweave.crud.crud_organization_billing import organization_billing
from airweave.db.unit_of_work import UnitOfWork
from airweave.domains.billing.operations import BillingOperations
from airweave.integrations.auth0_management import auth0_management_client
from airweave.models.organization import Organization
from airweave.models.organization_billing import OrganizationBilling
from airweave.models.user_organization import UserOrganization
from airweave.platform.sync.config import SyncConfig
from airweave.schemas.organization_billing import BillingPlan, BillingStatus

router = TrailingSlashRouter()


@router.get("/feature-flags", response_model=List[dict])
async def list_available_feature_flags(
    ctx: ApiContext = Depends(deps.get_context),
) -> List[dict]:
    """Get all available feature flags in the system (admin only).

    Args:
        ctx: API context

    Returns:
        List of feature flag definitions with name and value

    Raises:
        HTTPException: If user is not an admin
    """
    _require_admin(ctx)

    # Return all feature flags from the enum
    return [{"name": flag.name, "value": flag.value} for flag in FeatureFlagEnum]


def _require_admin(ctx: ApiContext) -> None:
    """Validate that the user is an admin or superuser.

    Args:
        ctx: The API context

    Raises:
        HTTPException: If user is not an admin or superuser
    """
    # Allow both explicit admins AND superusers (for system operations and tests)
    if not ctx.has_user_context or not (ctx.user.is_admin or ctx.user.is_superuser):
        raise HTTPException(status_code=403, detail="Admin access required")


def _require_admin_permission(ctx: ApiContext, permission: FeatureFlagEnum) -> None:
    """Validate admin access with scoped API key permission support.

    This function enables CASA-compliant admin access by checking:
    1. User-based admin (traditional): User must be admin or superuser
    2. API key-based (scoped): Organization must have specific permission feature flag

    This approach provides granular, auditable admin access for programmatic operations
    while maintaining security best practices.

    Args:
        ctx: The API context
        permission: The specific permission feature flag required for API key access

    Raises:
        HTTPException: If neither user admin nor API key permission is satisfied

    Example:
        # Require API_KEY_ADMIN_SYNC for resync operations
        _require_admin_permission(ctx, FeatureFlagEnum.API_KEY_ADMIN_SYNC)
    """
    # Check 1: User-based admin (traditional path)
    if ctx.has_user_context and (ctx.user.is_admin or ctx.user.is_superuser):
        ctx.logger.debug(f"Admin access granted via user: {ctx.user.email}")
        return

    # Check 2: API key with scoped permission (CASA-compliant path)
    if ctx.is_api_key_auth and ctx.has_feature(permission):
        ctx.logger.info(
            f"Admin access granted via API key with permission: {permission.value}",
            extra={
                "permission": permission.value,
                "organization_id": str(ctx.organization.id),
                "auth_method": ctx.auth_method.value,
            },
        )
        return

    # Neither condition met - deny access
    if ctx.is_api_key_auth:
        raise HTTPException(
            status_code=403,
            detail=f"API key requires '{permission.value}' feature flag for admin access",
        )
    raise HTTPException(status_code=403, detail="Admin access required")


async def _build_org_context(
    db: AsyncSession,
    target_org_id: UUID,
    admin_ctx: ApiContext,
) -> ApiContext:
    """Build a context for a target organization (for cross-org admin operations).

    This allows admin endpoints to execute operations (CRUD, Temporal workflows) in the
    context of a different organization than the admin's API key belongs to.

    The resulting context:
    - Uses the target organization's data (id, name, feature flags)
    - Preserves admin's request_id and logger for tracing
    - Preserves auth_method and auth_metadata for audit

    Args:
        db: Database session
        target_org_id: The organization ID to build context for
        admin_ctx: The admin's original context (for logging/tracing)

    Returns:
        ApiContext configured for the target organization
    """
    from sqlalchemy import select as sa_select

    from airweave.core.logging import LoggerConfigurator

    # Fetch target organization
    org_result = await db.execute(sa_select(Organization).where(Organization.id == target_org_id))
    org_obj = org_result.scalar_one_or_none()
    if not org_obj:
        raise NotFoundException(f"Organization {target_org_id} not found")

    target_org = schemas.Organization.model_validate(org_obj, from_attributes=True)

    # Build new context with target org but preserve admin's request tracing
    return ApiContext(
        request_id=admin_ctx.request_id,
        organization=target_org,
        user=admin_ctx.user,
        auth_method=admin_ctx.auth_method,
        auth_metadata=admin_ctx.auth_metadata,
        logger=LoggerConfigurator.configure_logger(
            "airweave.admin.cross_org",
            dimensions={
                "request_id": admin_ctx.request_id,
                "organization_id": str(target_org.id),
                "organization_name": target_org.name,
                "admin_org_id": str(admin_ctx.organization.id),
                "auth_method": admin_ctx.auth_method.value,
            },
        ),
    )


def _build_sort_subqueries(query, sort_by: str):
    """Build sort subqueries based on sort_by field.

    Args:
        query: The base SQLAlchemy query to extend
        sort_by: Field to sort by

    Returns:
        Tuple of (query, subqueries_dict) where subqueries_dict contains named subqueries.
    """
    from datetime import datetime

    from sqlalchemy import select as sa_select

    from airweave.models.billing_period import BillingPeriod
    from airweave.models.source_connection import SourceConnection
    from airweave.models.usage import Usage
    from airweave.models.user import User
    from airweave.schemas.billing_period import BillingPeriodStatus

    subqueries = {}

    # For usage-based sorting, join Usage and BillingPeriod
    if sort_by in ["entity_count", "query_count"]:
        now = datetime.utcnow()
        query = query.outerjoin(
            BillingPeriod,
            and_(
                BillingPeriod.organization_id == Organization.id,
                BillingPeriod.period_start <= now,
                BillingPeriod.period_end > now,
                BillingPeriod.status.in_(
                    [
                        BillingPeriodStatus.ACTIVE,
                        BillingPeriodStatus.TRIAL,
                        BillingPeriodStatus.GRACE,
                    ]
                ),
            ),
        ).outerjoin(Usage, Usage.billing_period_id == BillingPeriod.id)
        subqueries["Usage"] = Usage

    # For user_count sorting
    if sort_by == "user_count":
        user_count_subq = (
            sa_select(
                UserOrganization.organization_id,
                func.count(UserOrganization.user_id).label("user_count"),
            )
            .group_by(UserOrganization.organization_id)
            .subquery()
        )
        query = query.outerjoin(
            user_count_subq, Organization.id == user_count_subq.c.organization_id
        )
        subqueries["user_count_subq"] = user_count_subq

    # For source_connection_count sorting
    if sort_by == "source_connection_count":
        source_connection_count_subq = (
            sa_select(
                SourceConnection.organization_id,
                func.count(SourceConnection.id).label("source_connection_count"),
            )
            .group_by(SourceConnection.organization_id)
            .subquery()
        )
        query = query.outerjoin(
            source_connection_count_subq,
            Organization.id == source_connection_count_subq.c.organization_id,
        )
        subqueries["source_connection_count_subq"] = source_connection_count_subq

    # For last_active_at sorting
    if sort_by == "last_active_at":
        max_active_subq = (
            sa_select(
                UserOrganization.organization_id,
                func.max(User.last_active_at).label("max_last_active"),
            )
            .join(User, UserOrganization.user_id == User.id)
            .group_by(UserOrganization.organization_id)
            .subquery()
        )
        query = query.outerjoin(
            max_active_subq, Organization.id == max_active_subq.c.organization_id
        )
        subqueries["max_active_subq"] = max_active_subq

    return query, subqueries


def _get_sort_column(sort_by: str, subqueries: dict):
    """Get the SQLAlchemy column to sort by."""
    from airweave.models.usage import Usage

    # Map sort_by to column
    column_map = {
        "billing_plan": OrganizationBilling.billing_plan,
        "billing_status": OrganizationBilling.billing_status,
        "entity_count": Usage.entities,
        "query_count": Usage.queries,
        "is_member": Organization.created_at,  # Handled client-side
    }

    if sort_by in column_map:
        return column_map[sort_by]
    if sort_by == "user_count" and "user_count_subq" in subqueries:
        return subqueries["user_count_subq"].c.user_count
    if sort_by == "source_connection_count" and "source_connection_count_subq" in subqueries:
        return subqueries["source_connection_count_subq"].c.source_connection_count
    if sort_by == "last_active_at" and "max_active_subq" in subqueries:
        return subqueries["max_active_subq"].c.max_last_active
    if hasattr(Organization, sort_by):
        return getattr(Organization, sort_by)
    return Organization.created_at  # Default


async def _update_or_create_membership(
    db: AsyncSession, ctx: ApiContext, organization_id: UUID, role: str
) -> bool:
    """Update existing membership or create new one. Returns True if membership changed."""
    # Check if user is already a member
    existing_user_org = None
    for user_org in ctx.user.user_organizations:
        if user_org.organization.id == organization_id:
            existing_user_org = user_org
            break

    if existing_user_org:
        return await _update_membership_role(db, ctx, organization_id, role, existing_user_org)

    return await _create_new_membership(db, ctx, organization_id, role)


async def _update_membership_role(
    db: AsyncSession, ctx: ApiContext, organization_id: UUID, role: str, existing_user_org
) -> bool:
    """Update role if different, return True if changed."""
    if existing_user_org.role == role:
        ctx.logger.info(
            f"Admin {ctx.user.email} already member of org {organization_id} with role {role}"
        )
        return False

    from sqlalchemy import update

    stmt = (
        update(UserOrganization)
        .where(
            UserOrganization.user_id == ctx.user.id,
            UserOrganization.organization_id == organization_id,
        )
        .values(role=role)
    )
    await db.execute(stmt)
    await db.commit()
    ctx.logger.info(f"Admin {ctx.user.email} updated role in org {organization_id} to {role}")
    return True


async def _create_new_membership(
    db: AsyncSession, ctx: ApiContext, organization_id: UUID, role: str
) -> bool:
    """Create new membership, return True if successful."""
    try:
        user_org = UserOrganization(
            user_id=ctx.user.id,
            organization_id=organization_id,
            role=role,
            is_primary=False,
        )
        db.add(user_org)
        await db.commit()
        ctx.logger.info(
            f"Admin {ctx.user.email} added self to org {organization_id} with role {role}"
        )
        return True
    except Exception as e:
        ctx.logger.error(f"Failed to add admin to organization: {e}")
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to add user to organization: {str(e)}")


@router.get("/organizations", response_model=List[schemas.OrganizationMetrics])
async def list_all_organizations(
    db: AsyncSession = Depends(deps.get_db),
    ctx: ApiContext = Depends(deps.get_context),
    skip: int = 0,
    limit: int = Query(1000, le=10000, description="Maximum number of organizations to return"),
    search: Optional[str] = Query(None, description="Search by organization name"),
    sort_by: str = Query("created_at", description="Field to sort by"),
    sort_order: str = Query("desc", description="Sort order (asc or desc)"),
) -> List[schemas.OrganizationMetrics]:
    """List all organizations with comprehensive metrics (admin only).

    This endpoint fetches all organizations with their billing info and usage metrics
    using optimized queries to minimize database round-trips.

    Args:
        db: Database session
        ctx: API context
        skip: Number of organizations to skip
        limit: Maximum number of organizations to return (default 1000, max 10000)
        search: Optional search term to filter by organization name
        sort_by: Field to sort by (name, created_at, billing_plan, user_count,
            source_connection_count, entity_count, query_count, last_active_at)
        sort_order: Sort order (asc or desc)

    Returns:
        List of all organizations with comprehensive metrics

    Raises:
        HTTPException: If user is not an admin
    """
    _require_admin(ctx)

    # Build the base query with billing join and eager load feature flags
    query = (
        select(Organization)
        .outerjoin(OrganizationBilling, Organization.id == OrganizationBilling.organization_id)
        .options(selectinload(Organization.feature_flags))
    )

    # Build sort subqueries based on sort_by field
    query, subqueries = _build_sort_subqueries(query, sort_by)

    # Apply search filter
    if search:
        query = query.where(Organization.name.ilike(f"%{search}%"))

    # Apply sorting (is_member sorting handled client-side)
    sort_column = _get_sort_column(sort_by, subqueries)

    if sort_order.lower() == "asc":
        query = query.order_by(sort_column.asc().nullslast())
    else:
        query = query.order_by(sort_column.desc().nullslast())

    # Apply pagination
    query = query.offset(skip).limit(limit)

    # Execute query
    result = await db.execute(query)
    orgs = list(result.scalars().all())

    if not orgs:
        return []

    org_ids = [org.id for org in orgs]

    # Fetch all billing info in one query
    billing_query = select(OrganizationBilling).where(
        OrganizationBilling.organization_id.in_(org_ids)
    )
    billing_result = await db.execute(billing_query)
    billing_map = {b.organization_id: b for b in billing_result.scalars().all()}

    # Fetch user counts in one query
    user_count_query = (
        select(
            UserOrganization.organization_id,
            func.count(UserOrganization.user_id).label("count"),
        )
        .where(UserOrganization.organization_id.in_(org_ids))
        .group_by(UserOrganization.organization_id)
    )
    user_count_result = await db.execute(user_count_query)
    user_count_map = {row.organization_id: row.count for row in user_count_result}

    # Fetch admin's memberships in these organizations
    admin_membership_query = select(UserOrganization).where(
        UserOrganization.user_id == ctx.user.id,
        UserOrganization.organization_id.in_(org_ids),
    )
    admin_membership_result = await db.execute(admin_membership_query)
    admin_membership_map = {
        uo.organization_id: uo.role for uo in admin_membership_result.scalars().all()
    }

    # Fetch last active timestamp for each organization (most recent user activity)
    from airweave.models.user import User

    last_active_query = (
        select(
            UserOrganization.organization_id,
            func.max(User.last_active_at).label("last_active"),
        )
        .join(User, UserOrganization.user_id == User.id)
        .where(UserOrganization.organization_id.in_(org_ids))
        .group_by(UserOrganization.organization_id)
    )
    last_active_result = await db.execute(last_active_query)
    last_active_map = {row.organization_id: row.last_active for row in last_active_result}

    # Fetch current usage for all organizations using CRUD layer
    usage_map = await crud.usage.get_current_usage_for_orgs(db, organization_ids=org_ids)

    # Fetch source connection counts in one query (dynamically counted, not stored in usage)
    from airweave.models.source_connection import SourceConnection

    source_connection_count_query = (
        select(
            SourceConnection.organization_id,
            func.count(SourceConnection.id).label("count"),
        )
        .where(SourceConnection.organization_id.in_(org_ids))
        .group_by(SourceConnection.organization_id)
    )
    source_connection_result = await db.execute(source_connection_count_query)
    source_connection_map = {row.organization_id: row.count for row in source_connection_result}

    # Build response with all metrics
    org_metrics = []
    for org in orgs:
        billing = billing_map.get(org.id)
        usage_record = usage_map.get(org.id)
        admin_role = admin_membership_map.get(org.id)

        # Extract enabled features from the relationship
        enabled_features = [FeatureFlagEnum(ff.flag) for ff in org.feature_flags if ff.enabled]

        org_metrics.append(
            schemas.OrganizationMetrics(
                id=org.id,
                name=org.name,
                description=org.description,
                created_at=org.created_at,
                modified_at=org.modified_at,
                auth0_org_id=org.auth0_org_id,
                billing_plan=billing.billing_plan if billing else None,
                billing_status=billing.billing_status if billing else None,
                stripe_customer_id=billing.stripe_customer_id if billing else None,
                trial_ends_at=billing.trial_ends_at if billing else None,
                user_count=user_count_map.get(org.id, 0),
                source_connection_count=source_connection_map.get(org.id, 0),
                entity_count=usage_record.entities if usage_record else 0,
                query_count=usage_record.queries if usage_record else 0,
                last_active_at=last_active_map.get(org.id),
                is_member=admin_role is not None,
                member_role=admin_role,
                enabled_features=enabled_features,
            )
        )

    ctx.logger.info(
        f"Admin retrieved {len(org_metrics)} organizations "
        f"(search={search}, sort_by={sort_by}, sort_order={sort_order})"
    )

    return org_metrics


@router.post(
    "/organizations/{organization_id}/add-self",
    response_model=schemas.OrganizationWithRole,
)
async def add_self_to_organization(
    organization_id: UUID,
    role: str = "owner",  # Default to owner for admins
    db: AsyncSession = Depends(deps.get_db),
    ctx: ApiContext = Depends(deps.get_context),
) -> schemas.OrganizationWithRole:
    """Add the admin user to an organization (admin only).

    This allows admins to join any organization for support purposes.

    Args:
        organization_id: The organization to join
        role: Role to assign (owner, admin, or member)
        db: Database session
        ctx: API context

    Returns:
        The organization with the admin's new role

    Raises:
        HTTPException: If user is not an admin or organization doesn't exist
    """
    _require_admin(ctx)

    # Validate role
    if role not in ["owner", "admin", "member"]:
        raise HTTPException(status_code=400, detail="Invalid role. Must be owner, admin, or member")

    # Check if organization exists
    org = await crud.organization.get(db, organization_id, ctx)
    if not org:
        raise NotFoundException(f"Organization {organization_id} not found")

    # Capture org values before any commits to avoid detached instance issues
    org_data = {
        "id": org.id,
        "name": org.name,
        "description": org.description,
        "created_at": org.created_at,
        "modified_at": org.modified_at,
        "auth0_org_id": org.auth0_org_id,
        "org_metadata": org.org_metadata,
    }

    membership_changed = await _update_or_create_membership(db, ctx, organization_id, role)

    # Also add to Auth0 if available
    try:
        if org_data["auth0_org_id"] and ctx.user.auth0_id and auth0_management_client:
            await auth0_management_client.add_user_to_organization(
                org_id=org_data["auth0_org_id"],
                user_id=ctx.user.auth0_id,
            )
            ctx.logger.info(f"Added admin {ctx.user.email} to Auth0 org {org_data['auth0_org_id']}")
    except Exception as e:
        ctx.logger.warning(f"Failed to add admin to Auth0 organization: {e}")
        # Don't fail the request if Auth0 fails

    if membership_changed and ctx.user and ctx.user.email:
        await context_cache.invalidate_user(ctx.user.email)

    return schemas.OrganizationWithRole(
        id=org_data["id"],
        name=org_data["name"],
        description=org_data["description"],
        created_at=org_data["created_at"],
        modified_at=org_data["modified_at"],
        role=role,
        is_primary=False,
        auth0_org_id=org_data["auth0_org_id"],
        org_metadata=org_data["org_metadata"],
    )


@router.post("/organizations/{organization_id}/upgrade-to-enterprise")
async def upgrade_organization_to_enterprise(  # noqa: C901
    organization_id: UUID,
    db: AsyncSession = Depends(deps.get_db),
    ctx: ApiContext = Depends(deps.get_context),
    payment_gw: PaymentGatewayProtocol = Inject(PaymentGatewayProtocol),
) -> schemas.Organization:
    """Upgrade an organization to enterprise plan (admin only).

    Uses the existing billing service infrastructure to properly handle
    enterprise upgrades with Stripe customer and $0 subscription management.

    For new billing: Creates Stripe customer + $0 enterprise subscription
    For existing billing: Upgrades plan using billing service

    Args:
        organization_id: The organization to upgrade
        db: Database session
        ctx: API context
        payment_gw: Payment gateway protocol

    Returns:
        The updated organization

    Raises:
        HTTPException: If user is not an admin or organization doesn't exist
    """
    _require_admin(ctx)

    # Get organization as ORM model (enrich=False) to allow mutations and db.refresh()
    org = await crud.organization.get(db, organization_id, ctx, enrich=False)
    if not org:
        raise NotFoundException(f"Organization {organization_id} not found")

    org_schema = schemas.Organization.model_validate(org, from_attributes=True)

    # Check if billing record exists
    billing = await organization_billing.get_by_organization(db, organization_id=organization_id)

    if not billing:
        # No billing record - create one using the billing service
        ctx.logger.info(f"Creating enterprise billing for org {organization_id}")

        # Get owner email
        owner_email = ctx.user.email if ctx.user else "admin@airweave.ai"
        stmt = select(UserOrganization).where(
            UserOrganization.organization_id == organization_id,
            UserOrganization.role == "owner",
        )
        result = await db.execute(stmt)
        owner_user_org = result.scalar_one_or_none()

        if owner_user_org:
            from airweave.models.user import User

            stmt = select(User).where(User.id == owner_user_org.user_id)
            result = await db.execute(stmt)
            owner_user = result.scalar_one_or_none()
            if owner_user:
                owner_email = owner_user.email

        # Set enterprise in org metadata for billing service
        if not org.org_metadata:
            org.org_metadata = {}
        org.org_metadata["plan"] = "enterprise"
        await db.flush()

        # Create system context for billing operations
        internal_ctx = ApiContext.for_system(org_schema, "admin_upgrade")

        # Create Stripe customer
        customer = await payment_gw.create_customer(
            email=owner_email,
            name=org.name,
            metadata={
                "organization_id": str(organization_id),
                "plan": "enterprise",
            },
        )
        if not customer:
            raise HTTPException(
                status_code=400,
                detail="Billing is not enabled for this instance",
            )

        # Use billing operations to create record (handles $0 subscription)
        billing_ops = BillingOperations(payment_gateway=payment_gw)
        async with UnitOfWork(db) as uow:
            await billing_ops.create_billing_record(
                db=db,
                organization=org,
                stripe_customer_id=customer.id,
                billing_email=owner_email,
                ctx=internal_ctx,
                uow=uow,
            )
            await uow.commit()

        ctx.logger.info(f"Created enterprise billing for org {organization_id}")
    else:
        # Billing exists - cancel old subscription and create new enterprise one
        # The webhook will handle updating billing record and creating periods
        ctx.logger.info(f"Upgrading org {organization_id} to enterprise")

        # Cancel existing subscription if any
        if billing.stripe_subscription_id:
            try:
                await payment_gw.cancel_subscription(
                    billing.stripe_subscription_id, at_period_end=False
                )
                ctx.logger.info(f"Cancelled subscription {billing.stripe_subscription_id}")
            except Exception as e:
                ctx.logger.warning(f"Failed to cancel subscription: {e}")

        # Create new $0 enterprise subscription
        # Webhook will update billing record with subscription_id, plan, periods, etc.
        price_id = payment_gw.get_price_for_plan(BillingPlan.ENTERPRISE)
        if price_id:
            sub = await payment_gw.create_subscription(
                customer_id=billing.stripe_customer_id,
                price_id=price_id,
                metadata={
                    "organization_id": str(organization_id),
                    "plan": "enterprise",
                },
            )
            ctx.logger.info(
                f"Created $0 enterprise subscription {sub.id}, webhook will update billing record"
            )
        else:
            raise InvalidStateError("Enterprise price ID not configured")

        await db.commit()
        ctx.logger.info(f"Enterprise subscription created for org {organization_id}")

    # Refresh and return
    await db.refresh(org)
    await context_cache.invalidate_organization(organization_id)
    return schemas.Organization.model_validate(org)


@router.post("/organizations/create-enterprise", response_model=schemas.Organization)
async def create_enterprise_organization(
    organization_data: schemas.OrganizationCreate,
    owner_email: str,
    db: AsyncSession = Depends(deps.get_db),
    ctx: ApiContext = Depends(deps.get_context),
    payment_gw: PaymentGatewayProtocol = Inject(PaymentGatewayProtocol),
) -> schemas.Organization:
    """Create a new enterprise organization (admin only).

    This creates an organization directly on the enterprise plan.

    Args:
        organization_data: The organization data
        owner_email: Email of the user who will own this organization
        db: Database session
        ctx: API context
        payment_gw: Payment gateway protocol

    Returns:
        The created organization

    Raises:
        HTTPException: If user is not an admin or owner user doesn't exist
    """
    _require_admin(ctx)

    # Find the owner user
    try:
        owner_user = await crud.user.get_by_email(db, email=owner_email)
    except NotFoundException:
        raise HTTPException(status_code=404, detail=f"User with email {owner_email} not found")

    # Create organization with enterprise billing
    async with UnitOfWork(db) as uow:
        # Create the organization (without Auth0/Stripe integration to avoid automatic trial setup)
        from airweave.core.datetime_utils import utc_now_naive
        from airweave.models.organization import Organization
        from airweave.models.organization_billing import OrganizationBilling

        org = Organization(
            name=organization_data.name,
            description=organization_data.description,
            created_by_email=ctx.user.email,
            modified_by_email=ctx.user.email,
        )
        uow.session.add(org)
        await uow.session.flush()

        # Add owner to organization
        user_org = UserOrganization(
            user_id=owner_user.id,
            organization_id=org.id,
            role="owner",
            is_primary=len(owner_user.user_organizations) == 0,  # Primary if first org
        )
        uow.session.add(user_org)

        # Create Stripe customer
        try:
            customer = await payment_gw.create_customer(
                email=owner_email,
                name=org.name,
                metadata={"organization_id": str(org.id), "plan": "enterprise"},
            )
            if not customer:
                raise HTTPException(
                    status_code=400,
                    detail="Billing is not enabled for this instance",
                )

            # Create enterprise billing record
            billing = OrganizationBilling(
                organization_id=org.id,
                stripe_customer_id=customer.id,
                stripe_subscription_id=None,
                billing_plan="enterprise",
                billing_status=BillingStatus.ACTIVE,
                billing_email=owner_email,
                payment_method_added=True,
                current_period_start=utc_now_naive(),
                current_period_end=None,
            )
            uow.session.add(billing)
        except Exception as e:
            ctx.logger.error(f"Failed to create Stripe customer for enterprise org: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to create billing: {str(e)}")

        await uow.session.commit()
        await uow.session.refresh(org)

        ctx.logger.info(f"Created enterprise organization {org.id} for {owner_email}")

    # Try to create Auth0 organization (best effort)
    try:
        if owner_user.auth0_id and auth0_management_client:
            # Create Auth0 org name (lowercase, URL-safe)
            auth0_org_name = organization_service._create_org_name(
                schemas.OrganizationCreate(name=org.name, description=org.description)
            )

            auth0_org = await auth0_management_client.create_organization(
                name=auth0_org_name,
                display_name=org.name,
            )

            # Update org with Auth0 ID
            org.auth0_org_id = auth0_org["id"]
            await db.commit()
            await db.refresh(org)

            # Add owner to Auth0 org
            await auth0_management_client.add_user_to_organization(
                org_id=auth0_org["id"],
                user_id=owner_user.auth0_id,
            )

            ctx.logger.info(f"Created Auth0 organization for {org.id}")
    except Exception as e:
        ctx.logger.warning(f"Failed to create Auth0 organization: {e}")
        # Don't fail the request if Auth0 fails

    await context_cache.invalidate_user(owner_user.email)

    return schemas.Organization.model_validate(org)


@router.post("/organizations/{organization_id}/feature-flags/{flag}/enable")
async def enable_feature_flag(
    organization_id: UUID,
    flag: str,
    db: AsyncSession = Depends(deps.get_db),
    ctx: ApiContext = Depends(deps.get_context),
) -> dict:
    """Enable a feature flag for an organization (admin only).

    Args:
        organization_id: The organization ID
        flag: The feature flag name to enable
        db: Database session
        ctx: API context

    Returns:
        Success message with flag details

    Raises:
        HTTPException: If user is not an admin, organization doesn't exist, or invalid flag
    """
    _require_admin(ctx)

    # Verify organization exists
    org = await crud.organization.get(db, organization_id, ctx, skip_access_validation=True)
    if not org:
        raise NotFoundException(f"Organization {organization_id} not found")

    # Validate flag exists
    try:
        feature_flag = FeatureFlagEnum(flag)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid feature flag: {flag}")

    # Enable the feature
    await crud.organization.enable_feature(db, organization_id, feature_flag)

    # Invalidate organization cache so next request sees updated feature flags
    await context_cache.invalidate_organization(organization_id)

    ctx.logger.info(f"Admin enabled feature flag {flag} for org {organization_id}")

    return {"message": f"Feature flag '{flag}' enabled", "organization_id": str(organization_id)}


@router.post("/organizations/{organization_id}/feature-flags/{flag}/disable")
async def disable_feature_flag(
    organization_id: UUID,
    flag: str,
    db: AsyncSession = Depends(deps.get_db),
    ctx: ApiContext = Depends(deps.get_context),
) -> dict:
    """Disable a feature flag for an organization (admin only).

    Args:
        organization_id: The organization ID
        flag: The feature flag name to disable
        db: Database session
        ctx: API context

    Returns:
        Success message with flag details

    Raises:
        HTTPException: If user is not an admin, organization doesn't exist, or invalid flag
    """
    _require_admin(ctx)

    # Verify organization exists
    org = await crud.organization.get(db, organization_id, ctx, skip_access_validation=True)
    if not org:
        raise NotFoundException(f"Organization {organization_id} not found")

    # Validate flag exists
    try:
        feature_flag = FeatureFlagEnum(flag)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid feature flag: {flag}")

    # Disable the feature
    await crud.organization.disable_feature(db, organization_id, feature_flag)

    # Invalidate organization cache so next request sees updated feature flags
    await context_cache.invalidate_organization(organization_id)

    ctx.logger.info(f"Admin disabled feature flag {flag} for org {organization_id}")

    return {"message": f"Feature flag '{flag}' disabled", "organization_id": str(organization_id)}


@router.post("/resync/{sync_id}", response_model=schemas.SyncJob)
async def resync_with_execution_config(
    *,
    db: AsyncSession = Depends(deps.get_db),
    sync_id: UUID,
    ctx: ApiContext = Depends(deps.get_context),
    execution_config: Optional[SyncConfig] = Body(
        None,
        description="Optional nested SyncConfig for sync behavior",
        examples=[
            {
                "summary": "ARF Capture Only",
                "value": {
                    "handlers": {
                        "enable_vector_handlers": False,
                        "enable_postgres_handler": False,
                        "enable_raw_data_handler": True,
                    },
                    "cursor": {"skip_load": True, "skip_updates": True},
                    "behavior": {"skip_hash_comparison": True},
                },
            },
            {
                "summary": "ARF Replay to Vector DBs",
                "value": {
                    "handlers": {
                        "enable_vector_handlers": True,
                        "enable_postgres_handler": False,
                        "enable_raw_data_handler": False,
                    },
                    "cursor": {"skip_load": True, "skip_updates": True},
                    "behavior": {"skip_hash_comparison": True, "replay_from_arf": True},
                },
            },
            {
                "summary": "Skip Vespa",
                "value": {"destinations": {"skip_vespa": True}},
            },
        ],
    ),
    tags: Optional[List[str]] = Body(
        None,
        description="Optional tags for filtering and organizing sync jobs",
        examples=[
            ["vespa-backfill-01-22-2026", "manual"],
            ["production"],
        ],
    ),
) -> schemas.SyncJob:
    """Admin-only: Trigger a sync with custom execution config and optional tags via Temporal.

    This endpoint allows admins to trigger syncs with custom execution configurations
    for advanced use cases like ARF-only capture, destination-specific replays, or dry runs.

    The sync is dispatched to Temporal and runs asynchronously in workers, not in the backend pod.

    **API Key Access**: Organizations with the `api_key_admin_sync` feature flag enabled
    can use API keys to access this endpoint programmatically.

    **Config Structure**: Nested config with 4 sub-objects:
        - destinations: skip_vespa, target_destinations, exclude_destinations
        - handlers: enable_vector_handlers, enable_raw_data_handler, enable_postgres_handler
        - cursor: skip_load, skip_updates
        - behavior: skip_hash_comparison, replay_from_arf

    **Tags**: Optional list of strings for filtering/organizing jobs:
        - Example: ["vespa-backfill-01-22-2026", "manual"]
        - Stored in sync_metadata.tags for filtering in admin dashboard

    Args:
        db: Database session
        sync_id: ID of the sync to trigger
        ctx: API context
        execution_config: Optional nested SyncConfig
        tags: Optional list of tags for filtering

    Returns:
        The created sync job

    Raises:
        HTTPException: If user is not admin or sync not found

    **Preset Examples** (use SyncConfig factory methods):
        - Normal sync: SyncConfig.default()
        - ARF capture only: SyncConfig.arf_capture_only()
        - ARF replay to vector DBs: SyncConfig.replay_from_arf_to_vector_dbs()
        - Vespa only: SyncConfig.vespa_only()
    """
    _require_admin_permission(ctx, FeatureFlagEnum.API_KEY_ADMIN_SYNC)

    ctx.logger.info(
        f"Admin triggering resync for sync {sync_id} with execution config: {execution_config}"
    )

    # Bypass organization filtering for all queries (admin access)
    from sqlalchemy import select as sa_select

    from airweave.core.shared_models import IntegrationType, SyncJobStatus
    from airweave.db.unit_of_work import UnitOfWork
    from airweave.models.collection import Collection
    from airweave.models.connection import Connection
    from airweave.models.source_connection import SourceConnection
    from airweave.models.sync import Sync
    from airweave.models.sync_connection import SyncConnection
    from airweave.models.sync_job import SyncJob

    # Get the sync without organization filtering
    result = await db.execute(sa_select(Sync).where(Sync.id == sync_id))
    sync_obj = result.scalar_one_or_none()
    if not sync_obj:
        raise NotFoundException(f"Sync {sync_id} not found")

    # Capture organization_id immediately before other async operations expire the model
    sync_organization_id = sync_obj.organization_id

    # Get connection IDs from SyncConnection table (bypass org filtering)
    sync_connections_result = await db.execute(
        sa_select(SyncConnection, Connection)
        .join(Connection, SyncConnection.connection_id == Connection.id)
        .where(SyncConnection.sync_id == sync_id)
    )
    sync_connections = sync_connections_result.all()

    source_connection_id = None
    destination_connection_ids = []
    for _sync_conn, conn in sync_connections:
        if conn.integration_type == IntegrationType.SOURCE:
            source_connection_id = conn.id
        else:
            destination_connection_ids.append(conn.id)

    if not source_connection_id:
        raise NotFoundException(f"Source connection not found for sync {sync_id}")

    # Check for existing active jobs (bypass org filtering)
    active_jobs_result = await db.execute(
        sa_select(SyncJob).where(
            SyncJob.sync_id == sync_id,
            SyncJob.status.in_(
                [
                    SyncJobStatus.PENDING,
                    SyncJobStatus.RUNNING,
                    SyncJobStatus.CANCELLING,
                ]
            ),
        )
    )
    active_jobs = list(active_jobs_result.scalars().all())
    if active_jobs:
        status = active_jobs[0].status
        job_status = (status.value if hasattr(status, "value") else status).lower()
        raise HTTPException(
            status_code=400, detail=f"Cannot start new sync: a sync job is already {job_status}"
        )

    # Enrich sync dict with connection IDs for schema validation
    sync_dict = {
        "id": sync_obj.id,
        "organization_id": sync_obj.organization_id,
        "name": sync_obj.name,
        "description": sync_obj.description,
        "status": sync_obj.status,
        "cron_schedule": sync_obj.cron_schedule,
        "next_scheduled_run": sync_obj.next_scheduled_run,
        "temporal_schedule_id": sync_obj.temporal_schedule_id,
        "sync_type": sync_obj.sync_type,
        "sync_metadata": sync_obj.sync_metadata,
        "created_at": sync_obj.created_at,
        "modified_at": sync_obj.modified_at,
        "created_by_email": sync_obj.created_by_email,
        "modified_by_email": sync_obj.modified_by_email,
        "source_connection_id": source_connection_id,
        "destination_connection_ids": destination_connection_ids,
    }
    sync_schema = schemas.Sync.model_validate(sync_dict)

    # Build sync_metadata with tags if provided
    sync_metadata = None
    if tags:
        sync_metadata = {"tags": tags}
        ctx.logger.info(f"Admin resync job will be tagged with: {tags}")

    async with UnitOfWork(db) as uow:
        sync_job_obj = SyncJob(
            sync_id=sync_id,
            organization_id=sync_obj.organization_id,
            status=SyncJobStatus.PENDING,
            sync_config=execution_config.model_dump() if execution_config else None,
            sync_metadata=sync_metadata,
        )
        uow.session.add(sync_job_obj)
        await uow.commit()
        await uow.session.refresh(sync_job_obj)

    sync_job_schema = schemas.SyncJob.model_validate(sync_job_obj, from_attributes=True)

    # Get source connection (bypass org filtering)
    source_conn_result = await db.execute(
        sa_select(SourceConnection).where(SourceConnection.sync_id == sync_id)
    )
    source_conn = source_conn_result.scalar_one_or_none()
    if not source_conn:
        raise NotFoundException(f"Source connection not found for sync {sync_id}")

    # Get collection (bypass org filtering)
    collection_result = await db.execute(
        sa_select(Collection).where(Collection.readable_id == source_conn.readable_collection_id)
    )
    collection = collection_result.scalar_one_or_none()
    if not collection:
        raise NotFoundException(f"Collection {source_conn.readable_collection_id} not found")

    collection_schema = schemas.Collection.model_validate(collection, from_attributes=True)

    # Get the Connection object (bypass org filtering)
    connection_result = await db.execute(
        sa_select(Connection).where(Connection.id == source_conn.connection_id)
    )
    connection = connection_result.scalar_one_or_none()
    if not connection:
        raise NotFoundException("Connection not found for source connection")
    connection_schema = schemas.Connection.model_validate(connection, from_attributes=True)

    # Build context for the sync's organization (not the admin's API key org)
    # This ensures Temporal workers can access resources in the correct org context
    sync_org_ctx = await _build_org_context(db, sync_organization_id, ctx)

    # Dispatch to Temporal with the sync's organization context
    ctx.logger.info(
        f"Dispatching sync job {sync_job_schema.id} to Temporal "
        f"(sync org: {sync_organization_id}, admin org: {ctx.organization.id})"
    )
    await temporal_service.run_source_connection_workflow(
        sync=sync_schema,
        sync_job=sync_job_schema,
        collection=collection_schema,
        connection=connection_schema,
        ctx=sync_org_ctx,  # Use sync's org context, not admin's
        force_full_sync=False,
    )

    ctx.logger.info(f"✅ Admin resync job {sync_job_schema.id} dispatched to Temporal")

    return sync_job_schema


# =============================================================================
# Admin Sync Endpoints for API Key Access
# =============================================================================


class AdminSyncInfo(schemas.Sync):
    """Extended sync info for admin listing with entity counts and status."""

    model_config = ConfigDict(from_attributes=True)

    total_entity_count: int = 0
    total_arf_entity_count: Optional[int] = None
    total_qdrant_entity_count: Optional[int] = None
    total_vespa_entity_count: Optional[int] = None

    last_job_status: Optional[str] = None
    last_job_at: Optional[datetime] = None
    last_job_error: Optional[str] = None
    all_tags: Optional[List[str]] = None
    source_short_name: Optional[str] = None
    source_is_authenticated: Optional[bool] = None
    readable_collection_id: Optional[str] = None


class AdminSearchDestination(str, Enum):
    """Destination options for admin search."""

    QDRANT = "qdrant"
    VESPA = "vespa"


@router.post("/collections/{readable_id}/search", response_model=schemas.SearchResponse)
async def admin_search_collection(
    readable_id: str,
    search_request: schemas.SearchRequest,
    db: AsyncSession = Depends(deps.get_db),
    ctx: ApiContext = Depends(deps.get_context),
    destination: AdminSearchDestination = Query(
        AdminSearchDestination.QDRANT,
        description="Search destination: 'qdrant' (default) or 'vespa'",
    ),
) -> schemas.SearchResponse:
    """Admin-only: Search any collection regardless of organization.

    This endpoint allows admins or API keys with `api_key_admin_sync` permission
    to search collections across organizations for migration and support purposes.

    Supports selecting the search destination (Qdrant or Vespa) for migration testing.

    Args:
        readable_id: The readable ID of the collection to search
        search_request: The search request parameters
        db: Database session
        ctx: API context
        destination: Search destination ('qdrant' or 'vespa')

    Returns:
        SearchResponse with results

    Raises:
        HTTPException: If not admin or collection not found
    """
    from airweave.search.service import service

    _require_admin_permission(ctx, FeatureFlagEnum.API_KEY_ADMIN_SYNC)

    return await service.search_admin(
        request_id=ctx.request_id,
        readable_collection_id=readable_id,
        search_request=search_request,
        db=db,
        ctx=ctx,
        destination=destination.value,
    )


@router.post("/collections/{readable_id}/search/as-user", response_model=schemas.SearchResponse)
async def admin_search_collection_as_user(
    readable_id: str,
    search_request: schemas.SearchRequest,
    user_principal: str = Query(
        ...,
        description="User principal (username) to search as. "
        "This user's access permissions will be applied to filter results.",
    ),
    db: AsyncSession = Depends(deps.get_db),
    ctx: ApiContext = Depends(deps.get_context),
    destination: AdminSearchDestination = Query(
        AdminSearchDestination.VESPA,
        description="Search destination: 'qdrant' or 'vespa' (default)",
    ),
) -> schemas.SearchResponse:
    """Admin-only: Search collection with access control for a specific user.

    Resolves the user's group memberships from the access_control_membership
    table and filters results accordingly.

    Args:
        readable_id: The readable ID of the collection to search
        search_request: The search request parameters
        user_principal: Username to search as
        db: Database session
        ctx: API context
        destination: Search destination ('qdrant' or 'vespa')

    Returns:
        SearchResponse with results filtered by user's access permissions.

    Raises:
        HTTPException: If not admin or collection not found.
    """
    from airweave.search.service import service

    _require_admin_permission(ctx, FeatureFlagEnum.API_KEY_ADMIN_SYNC)

    return await service.search_as_user(
        request_id=ctx.request_id,
        readable_collection_id=readable_id,
        search_request=search_request,
        db=db,
        ctx=ctx,
        user_principal=user_principal,
        destination=destination.value,
    )


@router.get("/source-connections/{source_connection_id}/cursor")
async def admin_get_cursor(
    source_connection_id: str,
    db: AsyncSession = Depends(deps.get_db),
    ctx: ApiContext = Depends(deps.get_context),
) -> dict:
    """Admin-only: Get cursor data for a source connection.

    Returns the sync cursor (change tokens, DirSync cookies, timestamps)
    for the sync associated with this source connection. Used for debugging
    and verifying continuous sync state.

    Args:
        source_connection_id: UUID of the source connection
        db: Database session
        ctx: API context

    Returns:
        Cursor data dict, or 404 if no cursor exists
    """
    from airweave.core.sync_cursor_service import sync_cursor_service

    _require_admin_permission(ctx, FeatureFlagEnum.API_KEY_ADMIN_SYNC)

    # Find the source connection and its sync_id
    source_connections = await crud.source_connection.get_multi(db, ctx=ctx)
    target_sc = None
    for sc in source_connections:
        if str(sc.id) == source_connection_id:
            target_sc = sc
            break

    if not target_sc:
        raise HTTPException(status_code=404, detail="Source connection not found")

    # source_connection has a sync_id field linking to the sync
    sync_id = getattr(target_sc, "sync_id", None)
    if not sync_id:
        raise HTTPException(status_code=404, detail="No sync found for this source connection")

    # Get cursor data
    cursor_data = await sync_cursor_service.get_cursor_data(db=db, sync_id=sync_id, ctx=ctx)

    if not cursor_data:
        raise HTTPException(status_code=404, detail="No cursor found for this sync")

    return {
        "sync_id": str(sync_id),
        "source_connection_id": source_connection_id,
        "cursor_data": cursor_data,
    }


@router.delete("/source-connections/{source_connection_id}/cursor")
async def admin_delete_cursor(
    source_connection_id: str,
    db: AsyncSession = Depends(deps.get_db),
    ctx: ApiContext = Depends(deps.get_context),
) -> dict:
    """Admin-only: Delete cursor for a source connection to force full sync.

    Removes the sync cursor, which forces the next sync to do a full crawl
    instead of incremental. Useful for debugging or resetting sync state.
    """
    from airweave.core.sync_cursor_service import sync_cursor_service

    _require_admin_permission(ctx, FeatureFlagEnum.API_KEY_ADMIN_SYNC)

    # Find source connection and its sync_id
    source_connections = await crud.source_connection.get_multi(db, ctx=ctx)
    target_sc = None
    for sc in source_connections:
        if str(sc.id) == source_connection_id:
            target_sc = sc
            break

    if not target_sc:
        raise HTTPException(status_code=404, detail="Source connection not found")

    sync_id = getattr(target_sc, "sync_id", None)
    if not sync_id:
        raise HTTPException(status_code=404, detail="No sync found for this source connection")

    # Delete cursor
    deleted = await sync_cursor_service.delete_cursor(db=db, sync_id=sync_id, ctx=ctx)

    return {
        "sync_id": str(sync_id),
        "deleted": deleted,
        "message": "Cursor deleted. Next sync will be a full sync.",
    }


async def _build_admin_search_context(
    db: AsyncSession,
    collection,
    readable_id: str,
    search_request: schemas.SearchRequest,
    destination,
    ctx: ApiContext,
):
    """Build search context with custom destination for admin search.

    This mirrors the factory.build() but allows overriding the destination.
    """
    from airweave.search.factory import (
        SearchContext,
        factory,
    )

    # Apply defaults and validate
    params = factory._apply_defaults_and_validate(search_request)

    # Get collection sources
    federated_sources = await factory.get_federated_sources(db, collection, ctx)
    has_federated_sources = bool(federated_sources)
    has_vector_sources = await factory._has_vector_sources(db, collection, ctx)

    # Determine destination capabilities
    requires_embedding = getattr(destination, "requires_client_embedding", True)
    supports_temporal = getattr(destination, "supports_temporal_relevance", True)

    ctx.logger.info(
        f"[AdminSearch] Destination: {destination.__class__.__name__}, "
        f"requires_client_embedding: {requires_embedding}, "
        f"supports_temporal_relevance: {supports_temporal}"
    )

    if not has_federated_sources and not has_vector_sources:
        raise ValueError("Collection has no sources")

    vector_size = collection.vector_size
    if vector_size is None:
        raise ValueError(f"Collection {collection.readable_id} has no vector_size set.")

    # Select providers for operations
    api_keys = factory._get_available_api_keys()
    providers = factory._create_provider_for_each_operation(
        api_keys,
        params,
        has_federated_sources,
        has_vector_sources,
        ctx,
        vector_size,
        requires_client_embedding=requires_embedding,
    )

    # Create event emitter
    from airweave.search.emitter import EventEmitter

    emitter = EventEmitter(request_id=ctx.request_id, stream=False)

    # Get temporal supporting sources if needed
    temporal_supporting_sources = None
    if params["temporal_weight"] > 0 and has_vector_sources and supports_temporal:
        try:
            temporal_supporting_sources = await factory._get_temporal_supporting_sources(
                db, collection, ctx, emitter
            )
        except Exception as e:
            raise ValueError(f"Failed to check temporal relevance support: {e}") from e
    elif params["temporal_weight"] > 0 and not supports_temporal:
        ctx.logger.info(
            "[AdminSearch] Skipping temporal relevance: destination does not support it"
        )
        temporal_supporting_sources = []

    # Build operations with custom destination
    operations = factory._build_operations(
        params,
        providers,
        federated_sources,
        has_vector_sources,
        search_request,
        temporal_supporting_sources,
        vector_size,
        destination=destination,
        requires_client_embedding=requires_embedding,
        db=db,
        ctx=ctx,
    )

    return SearchContext(
        request_id=ctx.request_id,
        collection_id=collection.id,
        readable_collection_id=readable_id,
        stream=False,
        vector_size=vector_size,
        offset=params["offset"],
        limit=params["limit"],
        emitter=emitter,
        query=search_request.query,
        **operations,
    )


@router.get("/syncs", response_model=List[AdminSyncInfo])
async def admin_list_all_syncs(
    db: AsyncSession = Depends(deps.get_db),
    ctx: ApiContext = Depends(deps.get_context),
    skip: int = Query(0, description="Number of syncs to skip"),
    limit: int = Query(100, le=1000, description="Maximum number of syncs to return"),
    sync_ids: Optional[str] = Query(
        None, description="Comma-separated list of sync IDs to filter by"
    ),
    organization_id: Optional[UUID] = Query(None, description="Filter by organization ID"),
    collection_id: Optional[str] = Query(
        None, description="Filter by collection readable ID (exact match)"
    ),
    source_type: Optional[str] = Query(None, description="Filter by source short name"),
    has_source_connection: bool = Query(
        True,
        description="Include only syncs with source connections",
    ),
    is_authenticated: Optional[bool] = Query(
        None,
        description="Filter by source connection auth status",
    ),
    status: Optional[str] = Query(
        None, description="Filter by sync status (active, inactive, error)"
    ),
    last_job_status: Optional[str] = Query(
        None,
        description="Filter by last job status (completed, failed, running, pending, cancelled)",
    ),
    ghost_syncs_last_n: Optional[int] = Query(
        None,
        ge=1,
        le=10,
        description="Filter to ghost syncs where the last N jobs all failed",
    ),
    include_destination_counts: bool = Query(
        False,
        description="Include Qdrant and Vespa document counts (slower, queries destinations)",
    ),
    include_arf_counts: bool = Query(
        False,
        description="Include ARF entity counts (slower, queries ARF storage for each sync)",
    ),
    tags: Optional[str] = Query(
        None,
        description="Comma-separated list of tags to filter by (matches jobs with ANY of the tags)",
    ),
    exclude_tags: Optional[str] = Query(
        None,
        description="Comma-separated tags to exclude from results",
    ),
) -> List[AdminSyncInfo]:
    """Admin-only: List all syncs across organizations with entity counts.

    Supports extensive filtering for migration and monitoring purposes.

    **Note**: Orphaned syncs (deleted source connections) are excluded by default.
    Set `has_source_connection=false` to see only orphaned syncs.

    **Entity Counts**:
        - total_entity_count: Count from Postgres (EntityCount table) - always included
        - total_arf_entity_count: Count from ARF storage (None unless include_arf_counts=true)
        - total_qdrant_entity_count: Count from Qdrant (None unless include_destination_counts=true)
        - total_vespa_entity_count: Count from Vespa (None unless include_destination_counts=true)

    **Performance Note**: Setting `include_destination_counts=true` or `include_arf_counts=true`
    queries external storage for each sync. Optimized with connection pooling but still slower.
    Uses approximate counts for better performance. Recommended for result sets <50 syncs.

    Args:
        db: Database session
        ctx: API context
        skip: Number of syncs to skip for pagination
        limit: Maximum number of syncs to return
        sync_ids: Optional comma-separated list of sync IDs
        organization_id: Optional filter by organization ID
        collection_id: Optional filter by collection readable ID
        source_type: Optional filter by source short name
        has_source_connection: Include syncs with source connections (default true)
        is_authenticated: Optional filter by authentication status
        status: Optional filter by sync status
        last_job_status: Optional filter by last job status
        ghost_syncs_last_n: Optional filter to syncs with N consecutive failures
        tags: Optional comma-separated list of tags to filter by
        exclude_tags: Optional comma-separated list of tags to exclude
        include_destination_counts: Whether to fetch Qdrant/Vespa counts (slower)
        include_arf_counts: Whether to fetch ARF entity counts (slower)

    Returns:
        List of syncs with extended information including entity counts

    Raises:
        HTTPException: If not admin or invalid parameters
    """
    from airweave.core.admin_sync_service import admin_sync_service

    _require_admin_permission(ctx, FeatureFlagEnum.API_KEY_ADMIN_SYNC)

    # Parse sync_ids if provided
    parsed_sync_ids: Optional[List[UUID]] = None
    if sync_ids:
        try:
            parsed_sync_ids = [UUID(sid.strip()) for sid in sync_ids.split(",") if sid.strip()]
        except ValueError as e:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid sync_ids format. Must be comma-separated UUIDs: {e}",
            )

    # Delegate to service layer
    sync_data_list, timings = await admin_sync_service.list_syncs_with_metadata(
        db=db,
        ctx=ctx,
        skip=skip,
        limit=limit,
        sync_ids=parsed_sync_ids,
        organization_id=organization_id,
        collection_id=collection_id,
        source_type=source_type,
        has_source_connection=has_source_connection,
        is_authenticated=is_authenticated,
        status=status,
        last_job_status=last_job_status,
        ghost_syncs_last_n=ghost_syncs_last_n,
        tags=tags,
        exclude_tags=exclude_tags,
        include_destination_counts=include_destination_counts,
        include_arf_counts=include_arf_counts,
    )

    if not sync_data_list:
        ctx.logger.info("Admin syncs query returned 0 results")
        return []

    # Convert to Pydantic models
    admin_syncs = [AdminSyncInfo.model_validate(sync_dict) for sync_dict in sync_data_list]

    # Log performance metrics
    ctx.logger.info(
        f"Admin listed {len(admin_syncs)} syncs in {timings['total']:.1f}ms | "
        f"Breakdown: query={timings.get('main_query', 0):.1f}ms, "
        f"entity_counts={timings.get('entity_counts', 0):.1f}ms, "
        f"arf_counts={timings.get('arf_counts', 0):.1f}ms, "
        f"last_job={timings.get('last_job_info', 0):.1f}ms, "
        f"source_conn={timings.get('source_connections', 0):.1f}ms, "
        f"dest_qdrant={timings.get('destination_counts_qdrant', 0):.1f}ms, "
        f"dest_vespa={timings.get('destination_counts_vespa', 0):.1f}ms, "
        f"sync_conn={timings.get('sync_connections', 0):.1f}ms, "
        f"build={timings.get('build_response', 0):.1f}ms | "
        f"Filters: sync_ids={len(parsed_sync_ids) if parsed_sync_ids else 0}, "
        f"org={organization_id}, collection={collection_id}, source={source_type}, "
        f"status={status}, last_job_status={last_job_status}, "
        f"has_source={has_source_connection}, is_authenticated={is_authenticated}, "
        f"tags={tags}, exclude_tags={exclude_tags}, ghost_syncs_n={ghost_syncs_last_n}, "
        f"include_arf={include_arf_counts}, include_dest={include_destination_counts}"
    )

    return admin_syncs


@router.post("/sync-jobs/{job_id}/cancel", response_model=schemas.SyncJob)
async def admin_cancel_sync_job(
    job_id: UUID,
    db: AsyncSession = Depends(deps.get_db),
    ctx: ApiContext = Depends(deps.get_context),
) -> schemas.SyncJob:
    """Admin-only: Cancel any sync job regardless of organization.

    This endpoint allows admins or API keys with `api_key_admin_sync` permission
    to cancel sync jobs across organizations for migration and support purposes.

    Args:
        job_id: The ID of the sync job to cancel
        db: Database session
        ctx: API context

    Returns:
        The updated sync job

    Raises:
        HTTPException: If not admin, job not found, or job not cancellable
    """
    from sqlalchemy import select as sa_select

    from airweave.core.datetime_utils import utc_now_naive
    from airweave.core.shared_models import SyncJobStatus
    from airweave.core.sync_job_service import sync_job_service
    from airweave.core.temporal_service import temporal_service
    from airweave.models.sync_job import SyncJob

    _require_admin_permission(ctx, FeatureFlagEnum.API_KEY_ADMIN_SYNC)

    # Get the sync job without organization filtering
    result = await db.execute(sa_select(SyncJob).where(SyncJob.id == job_id))
    sync_job = result.scalar_one_or_none()

    if not sync_job:
        raise NotFoundException(f"Sync job {job_id} not found")

    ctx.logger.info(
        f"Admin cancelling sync job {job_id} (org: {sync_job.organization_id}, "
        f"status: {sync_job.status})"
    )

    # Check if job is in a cancellable state (handle status as string or enum)
    job_status_str = sync_job.status.value if hasattr(sync_job.status, "value") else sync_job.status
    if job_status_str not in [SyncJobStatus.PENDING.value, SyncJobStatus.RUNNING.value]:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot cancel job in {job_status_str} state",
        )

    # Set transitional status to CANCELLING immediately
    await sync_job_service.update_status(
        sync_job_id=job_id,
        status=SyncJobStatus.CANCELLING,
        ctx=ctx,
    )

    # Fire-and-forget cancellation request to Temporal
    cancel_result = await temporal_service.cancel_sync_job_workflow(str(job_id), ctx)

    if not cancel_result["success"]:
        # Actual Temporal connectivity/availability error - revert status
        fallback_status = (
            SyncJobStatus.RUNNING
            if sync_job.status == SyncJobStatus.RUNNING
            else SyncJobStatus.PENDING
        )
        await sync_job_service.update_status(
            sync_job_id=job_id,
            status=fallback_status,
            ctx=ctx,
        )
        raise HTTPException(status_code=502, detail="Failed to request cancellation from Temporal")

    # If workflow wasn't found, mark job as CANCELLED directly
    if not cancel_result["workflow_found"]:
        ctx.logger.info(f"Workflow not found for job {job_id} - marking as CANCELLED directly")
        await sync_job_service.update_status(
            sync_job_id=job_id,
            status=SyncJobStatus.CANCELLED,
            ctx=ctx,
            completed_at=utc_now_naive(),
            error="Workflow not found in Temporal - may have already completed",
        )

    # Fetch the updated job from database
    await db.refresh(sync_job)

    ctx.logger.info(f"✅ Admin cancelled sync job {job_id}, new status: {sync_job.status}")

    return schemas.SyncJob.model_validate(sync_job, from_attributes=True)


@router.post("/syncs/{sync_id}/cancel")
async def admin_cancel_sync_by_id(
    sync_id: UUID,
    db: AsyncSession = Depends(deps.get_db),
    ctx: ApiContext = Depends(deps.get_context),
) -> dict:
    """Admin-only: Cancel all pending/running jobs for a sync.

    Args:
        sync_id: The sync ID whose jobs should be cancelled
        db: Database session
        ctx: API context

    Returns:
        Dict with cancelled job IDs and results

    Raises:
        HTTPException: If not admin or sync not found
    """
    from sqlalchemy import select as sa_select

    from airweave.core.datetime_utils import utc_now_naive
    from airweave.core.shared_models import SyncJobStatus
    from airweave.core.sync_job_service import sync_job_service
    from airweave.core.temporal_service import temporal_service
    from airweave.models.sync import Sync
    from airweave.models.sync_job import SyncJob

    _require_admin_permission(ctx, FeatureFlagEnum.API_KEY_ADMIN_SYNC)

    # Verify sync exists
    result = await db.execute(sa_select(Sync).where(Sync.id == sync_id))
    sync_obj = result.scalar_one_or_none()
    if not sync_obj:
        raise NotFoundException(f"Sync {sync_id} not found")

    # Find all pending/running jobs
    jobs_result = await db.execute(
        sa_select(SyncJob).where(
            SyncJob.sync_id == sync_id,
            SyncJob.status.in_([SyncJobStatus.PENDING, SyncJobStatus.RUNNING]),
        )
    )
    jobs = list(jobs_result.scalars().all())

    if not jobs:
        return {
            "sync_id": str(sync_id),
            "message": "No active jobs to cancel",
            "cancelled_jobs": [],
        }

    ctx.logger.info(f"Admin cancelling {len(jobs)} active job(s) for sync {sync_id}")

    cancelled_jobs = []
    failed_jobs = []

    for job in jobs:
        job_id = job.id
        job_status_str = job.status.value if hasattr(job.status, "value") else job.status

        try:
            # Set to CANCELLING
            await sync_job_service.update_status(
                sync_job_id=job_id,
                status=SyncJobStatus.CANCELLING,
                ctx=ctx,
            )

            # Request cancellation from Temporal
            cancel_result = await temporal_service.cancel_sync_job_workflow(str(job_id), ctx)

            if not cancel_result["success"]:
                # Temporal error - revert status
                fallback_status = (
                    SyncJobStatus.RUNNING
                    if job.status == SyncJobStatus.RUNNING
                    else SyncJobStatus.PENDING
                )
                await sync_job_service.update_status(
                    sync_job_id=job_id,
                    status=fallback_status,
                    ctx=ctx,
                )
                failed_jobs.append(
                    {
                        "job_id": str(job_id),
                        "error": "Failed to request cancellation from Temporal",
                    }
                )
                continue

            # If workflow not found, mark as CANCELLED directly
            if not cancel_result["workflow_found"]:
                ctx.logger.info(f"Workflow not found for job {job_id} - marking as CANCELLED")
                await sync_job_service.update_status(
                    sync_job_id=job_id,
                    status=SyncJobStatus.CANCELLED,
                    ctx=ctx,
                    completed_at=utc_now_naive(),
                    error="Workflow not found in Temporal - may have already completed",
                )

            cancelled_jobs.append(
                {
                    "job_id": str(job_id),
                    "previous_status": job_status_str,
                    "workflow_found": cancel_result["workflow_found"],
                }
            )

        except Exception as e:
            ctx.logger.error(f"Failed to cancel job {job_id}: {e}")
            failed_jobs.append({"job_id": str(job_id), "error": str(e)})

    ctx.logger.info(
        f"✅ Admin cancelled {len(cancelled_jobs)}/{len(jobs)} job(s) for sync {sync_id}"
    )

    return {
        "sync_id": str(sync_id),
        "total_jobs": len(jobs),
        "cancelled": len(cancelled_jobs),
        "failed": len(failed_jobs),
        "cancelled_jobs": cancelled_jobs,
        "failed_jobs": failed_jobs,
    }


@router.delete("/syncs/{sync_id}")
async def admin_delete_sync(
    sync_id: UUID,
    db: AsyncSession = Depends(deps.get_db),
    ctx: ApiContext = Depends(deps.get_context),
) -> dict:
    """Admin-only: Delete a sync and all related data.

    This endpoint reuses the existing source connection deletion logic which handles:
    - Cancelling active jobs
    - Cleaning up Temporal schedules
    - Removing data from Qdrant
    - Removing data from Vespa
    - Removing ARF storage
    - Cascading deletes in Postgres (sync, connection, source_connection)

    Args:
        sync_id: The sync ID to delete
        db: Database session
        ctx: API context

    Returns:
        Success message with deleted sync ID

    Raises:
        HTTPException: If not admin, sync not found, or deletion fails
    """
    from sqlalchemy import select as sa_select

    from airweave.core.container import container
    from airweave.models.source_connection import SourceConnection
    from airweave.models.sync import Sync

    _require_admin_permission(ctx, FeatureFlagEnum.API_KEY_ADMIN_SYNC)

    # Verify sync exists
    result = await db.execute(sa_select(Sync).where(Sync.id == sync_id))
    sync_obj = result.scalar_one_or_none()
    if not sync_obj:
        raise NotFoundException(f"Sync {sync_id} not found")

    # Find the source connection for this sync
    source_conn_result = await db.execute(
        sa_select(SourceConnection).where(SourceConnection.sync_id == sync_id)
    )
    source_conn = source_conn_result.scalar_one_or_none()

    if not source_conn:
        raise NotFoundException(f"Source connection not found for sync {sync_id}")

    ctx.logger.info(
        f"Admin deleting sync {sync_id} (org: {sync_obj.organization_id}) "
        f"via source connection {source_conn.id}"
    )

    # Build context for the sync's organization
    sync_org_ctx = await _build_org_context(db, sync_obj.organization_id, ctx)

    # Use the existing source connection delete logic which handles all cleanup
    try:
        await container.source_connection_service.delete(
            db,
            id=source_conn.id,
            ctx=sync_org_ctx,
        )

        ctx.logger.info(f"✅ Admin successfully deleted sync {sync_id}")

        return {
            "sync_id": str(sync_id),
            "message": "Sync deleted successfully",
            "deleted_source_connection_id": str(source_conn.id),
        }
    except Exception as e:
        ctx.logger.error(f"Failed to delete sync {sync_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete sync: {str(e)}")
