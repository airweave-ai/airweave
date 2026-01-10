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
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from airweave import crud, schemas
from airweave.api import deps
from airweave.api.context import ApiContext
from airweave.api.router import TrailingSlashRouter
from airweave.billing.service import billing_service
from airweave.core.context_cache_service import context_cache
from airweave.core.exceptions import InvalidStateError, NotFoundException
from airweave.core.organization_service import organization_service
from airweave.core.shared_models import FeatureFlag as FeatureFlagEnum
from airweave.core.temporal_service import temporal_service
from airweave.crud.crud_organization_billing import organization_billing
from airweave.db.unit_of_work import UnitOfWork
from airweave.integrations.auth0_management import auth0_management_client
from airweave.integrations.stripe_client import stripe_client
from airweave.models.organization import Organization
from airweave.models.organization_billing import OrganizationBilling
from airweave.models.user_organization import UserOrganization
from airweave.platform.sync.config import SyncExecutionConfig
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
        user=admin_ctx.user,  # Preserve user if any (for audit trail)
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

    # Build the base query with billing join
    query = select(Organization).outerjoin(
        OrganizationBilling, Organization.id == OrganizationBilling.organization_id
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
        internal_ctx = billing_service._create_system_context(org_schema, "admin_upgrade")

        # Create Stripe customer
        if not stripe_client:
            raise InvalidStateError("Stripe is not enabled")

        customer = await stripe_client.create_customer(
            email=owner_email,
            name=org.name,
            metadata={
                "organization_id": str(organization_id),
                "plan": "enterprise",
            },
        )

        # Use billing service to create record (handles $0 subscription)
        async with UnitOfWork(db) as uow:
            await billing_service.create_billing_record(
                db=db,
                organization=org,
                stripe_customer_id=customer.id,
                billing_email=owner_email,
                ctx=internal_ctx,
                uow=uow,
                contextual_logger=ctx.logger,
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
                await stripe_client.cancel_subscription(
                    billing.stripe_subscription_id, at_period_end=False
                )
                ctx.logger.info(f"Cancelled subscription {billing.stripe_subscription_id}")
            except Exception as e:
                ctx.logger.warning(f"Failed to cancel subscription: {e}")

        # Create new $0 enterprise subscription
        # Webhook will update billing record with subscription_id, plan, periods, etc.
        if stripe_client:
            price_id = stripe_client.get_price_for_plan(BillingPlan.ENTERPRISE)
            if price_id:
                sub = await stripe_client.create_subscription(
                    customer_id=billing.stripe_customer_id,
                    price_id=price_id,
                    metadata={
                        "organization_id": str(organization_id),
                        "plan": "enterprise",
                    },
                )
                ctx.logger.info(
                    f"Created $0 enterprise subscription {sub.id}, "
                    f"webhook will update billing record"
                )
            else:
                raise InvalidStateError("Enterprise price ID not configured")
        else:
            raise InvalidStateError("Stripe is not enabled")

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
) -> schemas.Organization:
    """Create a new enterprise organization (admin only).

    This creates an organization directly on the enterprise plan.

    Args:
        organization_data: The organization data
        owner_email: Email of the user who will own this organization
        db: Database session
        ctx: API context

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
            customer = await stripe_client.create_customer(
                email=owner_email,
                name=org.name,
                metadata={"organization_id": str(org.id), "plan": "enterprise"},
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
    execution_config: Optional[SyncExecutionConfig] = Body(
        None,
        description="Optional execution config for sync behavior (handler toggles, etc.)",
        examples=[
            {
                "enable_vector_handlers": False,
                "enable_postgres_handler": False,
                "skip_cursor_load": True,
                "skip_cursor_updates": True,
            }
        ],
    ),
) -> schemas.SyncJob:
    """Admin-only: Trigger a sync with custom execution config via Temporal.

    This endpoint allows admins to trigger syncs with custom execution configurations
    for advanced use cases like ARF-only capture, destination-specific replays, or dry runs.

    The sync is dispatched to Temporal and runs asynchronously in workers, not in the backend pod.

    **API Key Access**: Organizations with the `api_key_admin_sync` feature flag enabled
    can use API keys to access this endpoint programmatically.

    Args:
        db: Database session
        sync_id: ID of the sync to trigger
        ctx: API context
        execution_config: Optional dict with execution config parameters

    Returns:
        The created sync job

    Raises:
        HTTPException: If user is not admin or sync not found

    Example execution configs:
        - ARF capture only: {"enable_vector_handlers": false, "enable_postgres_handler": false}
        - Dry run: {"enable_vector_handlers": false, "enable_raw_data_handler": false,
          "enable_postgres_handler": false}
        - Target specific destination: {"target_destinations": ["<uuid>"]}
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
    async with UnitOfWork(db) as uow:
        sync_job_obj = SyncJob(
            sync_id=sync_id,
            organization_id=sync_obj.organization_id,
            status=SyncJobStatus.PENDING,
            execution_config_json=execution_config.model_dump() if execution_config else None,
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

    total_entity_count: int = 0
    last_job_status: Optional[str] = None
    last_job_at: Optional[datetime] = None
    source_short_name: Optional[str] = None
    readable_collection_id: Optional[str] = None

    # Last job that wrote to Vespa (skip_vespa != true)
    last_vespa_job_id: Optional[UUID] = None
    last_vespa_job_status: Optional[str] = None
    last_vespa_job_at: Optional[datetime] = None

    class Config:
        """Pydantic config."""

        from_attributes = True


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

    This endpoint allows testing access control filtering by searching as a
    specific user. It resolves the user's group memberships from the
    access_control_membership table and filters results accordingly.

    Use this for:
    - Testing ACL sync correctness
    - Verifying user permissions
    - Debugging access control issues

    Args:
        readable_id: The readable ID of the collection to search
        search_request: The search request parameters
        user_principal: Username to search as (e.g., "john" or "john@example.com")
        db: Database session
        ctx: API context
        destination: Search destination ('qdrant' or 'vespa')

    Returns:
        SearchResponse with results filtered by user's access permissions

    Raises:
        HTTPException: If not admin or collection not found
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


@router.get("/syncs", response_model=List[AdminSyncInfo])
async def admin_list_all_syncs(
    db: AsyncSession = Depends(deps.get_db),
    ctx: ApiContext = Depends(deps.get_context),
    skip: int = Query(0, description="Number of syncs to skip"),
    limit: int = Query(100, le=1000, description="Maximum number of syncs to return"),
    organization_id: Optional[UUID] = Query(None, description="Filter by organization ID"),
) -> List[AdminSyncInfo]:
    """Admin-only: List all syncs across organizations with entity counts.

    This endpoint returns syncs with entity counts, last job status, and source
    connection information for migration and monitoring purposes.

    Args:
        db: Database session
        ctx: API context
        skip: Number of syncs to skip for pagination
        limit: Maximum number of syncs to return
        organization_id: Optional filter by organization ID

    Returns:
        List of syncs with extended information

    Raises:
        HTTPException: If not admin
    """
    from sqlalchemy import func
    from sqlalchemy import select as sa_select

    from airweave.models.connection import Connection
    from airweave.models.entity_count import EntityCount
    from airweave.models.source_connection import SourceConnection
    from airweave.models.sync import Sync
    from airweave.models.sync_connection import SyncConnection
    from airweave.models.sync_job import SyncJob

    _require_admin_permission(ctx, FeatureFlagEnum.API_KEY_ADMIN_SYNC)

    # Build base query for syncs
    query = sa_select(Sync).order_by(Sync.created_at.desc())

    if organization_id:
        query = query.where(Sync.organization_id == organization_id)

    query = query.offset(skip).limit(limit)

    result = await db.execute(query)
    syncs = list(result.scalars().all())

    if not syncs:
        return []

    sync_ids = [s.id for s in syncs]

    # Fetch entity counts in bulk
    entity_count_query = (
        sa_select(EntityCount.sync_id, func.sum(EntityCount.count).label("total_count"))
        .where(EntityCount.sync_id.in_(sync_ids))
        .group_by(EntityCount.sync_id)
    )
    entity_count_result = await db.execute(entity_count_query)
    entity_count_map = {row.sync_id: row.total_count or 0 for row in entity_count_result}

    # Fetch last job info in bulk
    last_job_subq = (
        sa_select(
            SyncJob.sync_id,
            SyncJob.status,
            SyncJob.completed_at,
            func.row_number()
            .over(partition_by=SyncJob.sync_id, order_by=SyncJob.created_at.desc())
            .label("rn"),
        )
        .where(SyncJob.sync_id.in_(sync_ids))
        .subquery()
    )
    last_job_query = sa_select(last_job_subq).where(last_job_subq.c.rn == 1)
    last_job_result = await db.execute(last_job_query)
    last_job_map = {
        row.sync_id: {"status": row.status, "completed_at": row.completed_at}
        for row in last_job_result
    }

    # Fetch source connections info in bulk
    source_conn_query = sa_select(
        SourceConnection.sync_id,
        SourceConnection.short_name,
        SourceConnection.readable_collection_id,
    ).where(SourceConnection.sync_id.in_(sync_ids))
    source_conn_result = await db.execute(source_conn_query)
    source_conn_map = {
        row.sync_id: {
            "short_name": row.short_name,
            "readable_collection_id": row.readable_collection_id,
        }
        for row in source_conn_result
    }

    # Fetch sync connections to enrich with connection IDs
    sync_conn_query = (
        sa_select(SyncConnection, Connection)
        .join(Connection, SyncConnection.connection_id == Connection.id)
        .where(SyncConnection.sync_id.in_(sync_ids))
    )
    sync_conn_result = await db.execute(sync_conn_query)
    sync_connections = {}
    for sync_conn, connection in sync_conn_result:
        sync_id = sync_conn.sync_id
        if sync_id not in sync_connections:
            sync_connections[sync_id] = {"source": None, "destinations": []}
        if connection.integration_type.value == "source":
            sync_connections[sync_id]["source"] = connection.id
        elif connection.integration_type.value == "destination":
            sync_connections[sync_id]["destinations"].append(connection.id)

    # Fetch last ARF -> Vespa replay job info in bulk
    # An ARF -> Vespa replay job has:
    #   - replay_from_arf=true (read from ARF storage)
    #   - skip_vespa is NOT true (writes to Vespa)
    from sqlalchemy import or_

    arf_to_vespa_job_query = (
        sa_select(
            SyncJob.id,
            SyncJob.sync_id,
            SyncJob.status,
            SyncJob.completed_at,
            SyncJob.execution_config_json,
        )
        .where(
            SyncJob.sync_id.in_(sync_ids),
            SyncJob.execution_config_json.isnot(None),
            # Must be replay from ARF
            SyncJob.execution_config_json["replay_from_arf"].astext == "true",
            # Must NOT skip Vespa (skip_vespa is absent or false)
            or_(
                SyncJob.execution_config_json["skip_vespa"].astext != "true",
                SyncJob.execution_config_json["skip_vespa"].is_(None),
            ),
        )
        .order_by(SyncJob.sync_id, SyncJob.created_at.desc())
    )
    vespa_job_result = await db.execute(arf_to_vespa_job_query)
    vespa_job_rows = list(vespa_job_result)

    # Build map of sync_id -> most recent Vespa job (first per sync_id due to ordering)
    vespa_job_map = {}
    for row in vespa_job_rows:
        if row.sync_id not in vespa_job_map:
            vespa_job_map[row.sync_id] = {
                "id": row.id,
                "status": row.status,
                "completed_at": row.completed_at,
                "config": row.execution_config_json,
            }

    # Build response using helper function
    admin_syncs = _build_admin_sync_info_list(
        syncs=syncs,
        sync_connections=sync_connections,
        source_conn_map=source_conn_map,
        last_job_map=last_job_map,
        vespa_job_map=vespa_job_map,
        entity_count_map=entity_count_map,
    )

    ctx.logger.info(
        f"Admin listed {len(admin_syncs)} syncs "
        f"(org_filter={organization_id}, skip={skip}, limit={limit})"
    )

    return admin_syncs


def _build_admin_sync_info_list(
    syncs: list,
    sync_connections: dict,
    source_conn_map: dict,
    last_job_map: dict,
    vespa_job_map: dict,
    entity_count_map: dict,
) -> List[AdminSyncInfo]:
    """Build list of AdminSyncInfo from query results."""
    admin_syncs = []
    for sync in syncs:
        conn_info = sync_connections.get(sync.id, {"source": None, "destinations": []})
        source_info = source_conn_map.get(sync.id, {})
        last_job = last_job_map.get(sync.id, {})
        vespa_job = vespa_job_map.get(sync.id, {})

        sync_dict = {**sync.__dict__}
        if "_sa_instance_state" in sync_dict:
            sync_dict.pop("_sa_instance_state")

        sync_dict["source_connection_id"] = conn_info["source"]
        sync_dict["destination_connection_ids"] = conn_info["destinations"]
        sync_dict["total_entity_count"] = entity_count_map.get(sync.id, 0)
        # Handle status - may be enum or string depending on query
        last_status = last_job.get("status")
        sync_dict["last_job_status"] = (
            (last_status.value if hasattr(last_status, "value") else last_status)
            if last_status
            else None
        )
        sync_dict["last_job_at"] = last_job.get("completed_at")
        sync_dict["source_short_name"] = source_info.get("short_name")
        sync_dict["readable_collection_id"] = source_info.get("readable_collection_id")

        # Vespa migration tracking
        sync_dict["last_vespa_job_id"] = vespa_job.get("id")
        vespa_status = vespa_job.get("status")
        sync_dict["last_vespa_job_status"] = (
            (vespa_status.value if hasattr(vespa_status, "value") else vespa_status)
            if vespa_status
            else None
        )
        sync_dict["last_vespa_job_at"] = vespa_job.get("completed_at")
        sync_dict["last_vespa_job_config"] = vespa_job.get("config")

        admin_syncs.append(AdminSyncInfo.model_validate(sync_dict))

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
