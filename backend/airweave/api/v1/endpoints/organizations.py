"""API endpoints for organizations."""

from typing import List
from uuid import UUID

from fastapi import Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from airweave import crud, schemas
from airweave.analytics import business_events
from airweave.api import deps
from airweave.api.context import ApiContext
from airweave.api.deps import Inject
from airweave.api.router import TrailingSlashRouter
from airweave.core.datetime_utils import utc_now_naive
from airweave.core.logging import logger
from airweave.core.organization_service import organization_service
from airweave.domains.usage.protocols import UsageLimitCheckerProtocol
from airweave.domains.usage.types import ActionType
from airweave.models.user import User

router = TrailingSlashRouter()


@router.post("/", response_model=schemas.Organization)
async def create_organization(
    organization_data: schemas.OrganizationCreate,
    db: AsyncSession = Depends(deps.get_db),
    user: User = Depends(deps.get_user),
) -> schemas.Organization:
    """Create a new organization with current user as owner.

    Integrates with Auth0 Organizations API when available for enhanced multi-org support.

    This endpoint uses get_user instead of get_context because users creating their
    first organization don't have an organization context yet.

    Args:
        organization_data: The organization data to create
        db: Database session
        user: The authenticated user who will own the organization

    Returns:
        The created organization with user's role

    Raises:
        HTTPException: If organization name already exists or creation fails
    """
    # Create the organization with Auth0 integration
    try:
        organization = await organization_service.create_organization_with_integrations(
            db=db, org_data=organization_data, owner_user=user
        )

        # Set organization group properties for PostHog analytics
        business_events.set_organization_properties(
            organization_id=organization.id,
            properties={
                "organization_name": organization.name,
                "organization_plan": "trial",  # Default plan for new organizations
                "organization_created_at": (
                    organization.created_at.isoformat() if organization.created_at else None
                ),
                "organization_source": "signup",
            },
        )

        # Track event directly with analytics service (no ctx available during org creation)
        from airweave.analytics.service import analytics

        analytics.track_event(
            event_name="organization_created",
            distinct_id=user.email,
            properties={
                "organization_id": str(organization.id),
                "plan": "trial",  # Default plan for new organizations
                "source": "signup",
                "organization_name": organization.name,
            },
            groups={"organization": str(organization.id)},
        )

        # Notify Donke about new sign-up
        await _notify_donke_signup(organization, user, db)

        return organization
    except Exception as e:
        from airweave.core.logging import logger

        logger.exception(f"Failed to create organization: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to create organization: {str(e)}"
        ) from e


@router.get("/", response_model=List[schemas.OrganizationWithRole])
async def list_user_organizations(
    db: AsyncSession = Depends(deps.get_db),
    user: User = Depends(deps.get_user),
) -> List[schemas.OrganizationWithRole]:
    """Get all organizations the current user belongs to.

    Args:
        db: Database session
        user: The current authenticated user

    Returns:
        List of organizations with user's role in each
    """
    organizations = await crud.organization.get_user_organizations_with_roles(
        db=db, user_id=user.id
    )

    return [
        schemas.OrganizationWithRole(
            id=org.id,
            name=org.name,
            description=org.description or "",
            created_at=org.created_at,
            modified_at=org.modified_at,
            role=org.role,
            is_primary=org.is_primary,
            enabled_features=org.enabled_features or [],
        )
        for org in organizations
    ]


@router.get("/{organization_id}", response_model=schemas.OrganizationWithRole)
async def get_organization(
    organization_id: UUID,
    db: AsyncSession = Depends(deps.get_db),
    ctx: ApiContext = Depends(deps.get_context),
) -> schemas.OrganizationWithRole:
    """Get a specific organization by ID.

    Args:
        organization_id: The ID of the organization to get
        db: Database session
        ctx: The current authenticated user

    Returns:
        The organization with user's role

    Raises:
        HTTPException: If organization not found or user doesn't have access
    """
    # Validate access and get user's membership (this now has security built-in)
    user_org = await crud.organization.get_user_membership(
        db=db,
        organization_id=organization_id,
        user_id=ctx.user.id,
        ctx=ctx,
    )

    if not user_org:
        raise HTTPException(
            status_code=404, detail="Organization not found or you don't have access to it"
        )

    # Capture the role and is_primary values early to avoid greenlet exceptions later
    user_role = user_org.role
    user_is_primary = user_org.is_primary

    organization = await crud.organization.get(db=db, id=organization_id, ctx=ctx)

    return schemas.OrganizationWithRole(
        id=organization.id,
        name=organization.name,
        description=organization.description or "",
        created_at=organization.created_at,
        modified_at=organization.modified_at,
        role=user_role,
        is_primary=user_is_primary,
        enabled_features=organization.enabled_features or [],
    )


@router.put("/{organization_id}", response_model=schemas.OrganizationWithRole)
async def update_organization(
    organization_id: UUID,
    organization_data: schemas.OrganizationCreate,  # Reuse the same schema
    db: AsyncSession = Depends(deps.get_db),
    ctx: ApiContext = Depends(deps.get_context),
) -> schemas.OrganizationWithRole:
    """Update an organization.

    Only organization owners and admins can update organizations.

    Args:
        organization_id: The ID of the organization to update
        organization_data: The updated organization data
        db: Database session
        ctx: The current authenticated user

    Returns:
        The updated organization with user's role

    Raises:
        HTTPException: If organization not found, user doesn't have permission,
                      or organization name conflicts
    """
    # Get user's membership and validate admin access
    user_org = await crud.organization.get_user_membership(
        db=db,
        organization_id=organization_id,
        user_id=ctx.user.id,
        ctx=ctx,
    )

    if not user_org:
        raise HTTPException(
            status_code=404, detail="Organization not found or you don't have access to it"
        )

    # Capture the role and is_primary values early to avoid greenlet exceptions later
    user_role = user_org.role
    user_is_primary = user_org.is_primary

    if user_role not in ["owner", "admin"]:
        raise HTTPException(
            status_code=403, detail="Only organization owners and admins can update organizations"
        )

    # Check if the new name conflicts with existing organizations (if name is being changed)
    organization = await crud.organization.get(db=db, id=organization_id, ctx=ctx)

    update_data = schemas.OrganizationUpdate(
        name=organization_data.name, description=organization_data.description or ""
    )

    updated_organization = await crud.organization.update(
        db=db, db_obj=organization, obj_in=update_data, ctx=ctx
    )

    return schemas.OrganizationWithRole(
        id=updated_organization.id,
        name=updated_organization.name,
        description=updated_organization.description or "",
        created_at=updated_organization.created_at,
        modified_at=updated_organization.modified_at,
        role=user_role,
        is_primary=user_is_primary,
        enabled_features=updated_organization.enabled_features or [],
    )


@router.delete("/{organization_id}", response_model=schemas.OrganizationWithRole)
async def delete_organization(
    organization_id: UUID,
    db: AsyncSession = Depends(deps.get_db),
    ctx: ApiContext = Depends(deps.get_context),
) -> schemas.OrganizationWithRole:
    """Delete an organization.

    Only organization owners can delete organizations.

    Args:
        organization_id: The ID of the organization to delete
        db: Database session
        ctx: The current authenticated user

    Returns:
        The deleted organization

    Raises:
        HTTPException: If organization not found, user doesn't have permission,
                      or organization cannot be deleted
    """
    # Get user's membership (this now validates access automatically)
    user_org = await crud.organization.get_user_membership(
        db=db,
        organization_id=organization_id,
        user_id=ctx.user.id,
        ctx=ctx,
    )

    if not user_org:
        raise HTTPException(
            status_code=404, detail="Organization not found or you don't have access to it"
        )

    # Capture the role and is_primary values early to avoid greenlet exceptions later
    user_role = user_org.role
    user_is_primary = user_org.is_primary

    if user_role != "owner":
        raise HTTPException(
            status_code=403, detail="Only organization owners can delete organizations"
        )

    # Check if this is the user's only organization
    user_orgs = await crud.organization.get_user_organizations_with_roles(
        db=db, user_id=ctx.user.id
    )

    if len(user_orgs) <= 1:
        raise HTTPException(
            status_code=400,
            detail="Cannot delete your only organization. Contact support to delete your account.",
        )

    # Delete the organization using Auth0 service (handles both local and Auth0 deletion)
    try:
        success = await organization_service.delete_organization_with_integrations(
            db=db,
            organization_id=organization_id,
            deleting_user=ctx.user,
        )

        if not success:
            raise HTTPException(status_code=500, detail="Failed to delete organization")

        # Return the deleted organization info
        # Note: We use the captured values since the org is now deleted
        return schemas.OrganizationWithRole(
            id=organization_id,
            name="",  # Organization name is no longer available after deletion
            description="",
            created_at=utc_now_naive(),  # Placeholder values
            modified_at=utc_now_naive(),
            role=user_role,
            is_primary=user_is_primary,
        )

    except Exception as e:
        logger.error(f"Failed to delete organization {organization_id}: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to delete organization: {str(e)}"
        ) from e


@router.post("/{organization_id}/set-primary", response_model=schemas.OrganizationWithRole)
async def set_primary_organization(
    organization_id: UUID,
    db: AsyncSession = Depends(deps.get_db),
    ctx: ApiContext = Depends(deps.get_context),
) -> schemas.OrganizationWithRole:
    """Set an organization as the user's primary organization.

    Args:
        organization_id: The ID of the organization to set as primary
        db: Database session
        ctx: The current authenticated user

    Returns:
        The organization with updated primary status

    Raises:
        HTTPException: If organization not found or user doesn't have access
    """
    # Set as primary organization
    success = await crud.organization.set_primary_organization(
        db=db,
        user_id=ctx.user.id,
        organization_id=organization_id,
        ctx=ctx,
    )

    if not success:
        raise HTTPException(
            status_code=404, detail="Organization not found or you don't have access to it"
        )

    # Get the updated organization data
    user_org = await crud.organization.get_user_membership(
        db=db,
        organization_id=organization_id,
        user_id=ctx.user.id,
        ctx=ctx,
    )

    organization = await crud.organization.get(db=db, id=organization_id, ctx=ctx)

    if not organization or not user_org:
        raise HTTPException(status_code=404, detail="Organization not found")

    return schemas.OrganizationWithRole(
        id=organization.id,
        name=organization.name,
        description=organization.description or "",
        created_at=organization.created_at,
        modified_at=organization.modified_at,
        role=user_org.role,
        is_primary=user_org.is_primary,
    )


# Member Management Endpoints


@router.post("/{organization_id}/invite", response_model=schemas.InvitationResponse)
async def invite_user_to_organization(
    organization_id: UUID,
    invitation_data: schemas.InvitationCreate,
    db: AsyncSession = Depends(deps.get_db),
    ctx: ApiContext = Depends(deps.get_context),
    usage_checker: UsageLimitCheckerProtocol = Inject(UsageLimitCheckerProtocol),
) -> schemas.InvitationResponse:
    """Send organization invitation via Auth0."""
    # Validate user has admin access using auth context
    user_org = None
    for org in ctx.user.user_organizations:
        if org.organization.id == organization_id:
            user_org = org
            break

    if not user_org or user_org.role not in ["owner", "admin"]:
        raise HTTPException(
            status_code=403, detail="Only organization owners and admins can invite members"
        )

    try:
        # Enforce team member plan limits before sending invite
        await usage_checker.is_allowed(db, ctx.organization.id, ActionType.TEAM_MEMBERS, amount=1)
        invitation = await organization_service.invite_user_to_organization(
            db=db,
            organization_id=organization_id,
            email=invitation_data.email,
            role=invitation_data.role,
            inviter_user=ctx.user,
        )

        return schemas.InvitationResponse(
            id=invitation["id"],
            email=invitation_data.email,
            role=invitation_data.role,
            status="pending",
            invited_at=invitation.get("created_at"),
        )
    except Exception as e:
        # Convert limit errors to 422 for clearer UX
        msg = str(e)
        if "usage limit" in msg.lower() or "limit" in msg.lower():
            raise HTTPException(status_code=422, detail=msg) from e
        raise HTTPException(status_code=400, detail=msg) from e


@router.get("/{organization_id}/invitations", response_model=List[schemas.InvitationResponse])
async def get_pending_invitations(
    organization_id: UUID,
    db: AsyncSession = Depends(deps.get_db),
    ctx: ApiContext = Depends(deps.get_context),
) -> List[schemas.InvitationResponse]:
    """Get pending invitations for organization."""
    # Validate user has access to organization using auth context
    user_org = None
    for org in ctx.user.user_organizations:
        if org.organization.id == organization_id:
            user_org = org
            break

    if not user_org:
        raise HTTPException(
            status_code=404, detail="Organization not found or you don't have access to it"
        )

    try:
        invitations = await organization_service.get_pending_invitations(
            db=db,
            organization_id=organization_id,
            requesting_user=ctx.user,
        )

        return [
            schemas.InvitationResponse(
                id=inv["id"],
                email=inv["email"],
                role=inv["role"],
                status=inv["status"],
                invited_at=inv["invited_at"],
            )
            for inv in invitations
        ]
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.delete("/{organization_id}/invitations/{invitation_id}", response_model=dict)
async def remove_pending_invitation(
    organization_id: UUID,
    invitation_id: str,
    db: AsyncSession = Depends(deps.get_db),
    ctx: ApiContext = Depends(deps.get_context),
) -> dict:
    """Remove a pending invitation."""
    # Validate user has admin access using auth context
    user_org = None
    for org in ctx.user.user_organizations:
        if org.organization.id == organization_id:
            user_org = org
            break

    if not user_org or user_org.role not in ["owner", "admin"]:
        raise HTTPException(
            status_code=403, detail="Only organization owners and admins can remove invitations"
        )

    try:
        success = await organization_service.remove_pending_invitation(
            db=db,
            organization_id=organization_id,
            invitation_id=invitation_id,
            remover_user=ctx.user,
        )

        if success:
            return {"message": "Invitation removed successfully"}
        else:
            raise HTTPException(status_code=404, detail="Invitation not found")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("/{organization_id}/members", response_model=List[schemas.MemberResponse])
async def get_organization_members(
    organization_id: UUID,
    db: AsyncSession = Depends(deps.get_db),
    ctx: ApiContext = Depends(deps.get_context),
) -> List[schemas.MemberResponse]:
    """Get all members of an organization."""
    # Validate user has access to organization using auth context
    user_org = None
    for org in ctx.user.user_organizations:
        if org.organization.id == organization_id:
            user_org = org
            break

    if not user_org:
        raise HTTPException(
            status_code=404, detail="Organization not found or you don't have access to it"
        )

    try:
        members = await organization_service.get_organization_members(
            db=db,
            organization_id=organization_id,
            requesting_user=ctx.user,
        )

        return [
            schemas.MemberResponse(
                id=member["id"],
                email=member["email"],
                name=member["name"],
                role=member["role"],
                status=member["status"],
                is_primary=member["is_primary"],
                auth0_id=member["auth0_id"],
            )
            for member in members
        ]
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.delete("/{organization_id}/members/{user_id}", response_model=dict)
async def remove_member_from_organization(
    organization_id: UUID,
    user_id: UUID,
    db: AsyncSession = Depends(deps.get_db),
    ctx: ApiContext = Depends(deps.get_context),
) -> dict:
    """Remove a member from organization."""
    # Validate user has admin access using auth context
    user_org = None
    for org in ctx.user.user_organizations:
        if org.organization.id == organization_id:
            user_org = org
            break

    if not user_org or user_org.role not in ["owner", "admin"]:
        raise HTTPException(
            status_code=403, detail="Only organization owners and admins can remove members"
        )

    # Don't allow removing yourself this way - use leave endpoint instead
    if user_id == ctx.user.id:
        raise HTTPException(
            status_code=400, detail="Use the leave organization endpoint to remove yourself"
        )

    try:
        success = await organization_service.remove_member_from_organization(
            db=db,
            organization_id=organization_id,
            user_id=user_id,
            remover_user=ctx.user,
        )

        if success:
            return {"message": "Member removed successfully"}
        else:
            raise HTTPException(status_code=404, detail="Member not found")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/{organization_id}/leave", response_model=dict)
async def leave_organization(
    organization_id: UUID,
    db: AsyncSession = Depends(deps.get_db),
    ctx: ApiContext = Depends(deps.get_context),
) -> dict:
    """Leave an organization."""
    # Validate user is a member using auth context
    user_org = None
    for org in ctx.user.user_organizations:
        if org.organization.id == organization_id:
            user_org = org
            break

    if not user_org:
        raise HTTPException(status_code=404, detail="You are not a member of this organization")

    # Check if this is the user's only organization
    user_orgs = await crud.organization.get_user_organizations_with_roles(
        db=db, user_id=ctx.user.id
    )

    if len(user_orgs) <= 1:
        raise HTTPException(
            status_code=400,
            detail="Cannot leave your only organization. "
            "Users must belong to at least one organization. Delete the organization instead.",
        )

    # If user is an owner, check if there are other owners
    user_role = user_org.role
    if user_role == "owner":
        other_owners = await crud.organization.get_organization_owners(
            db=db,
            organization_id=organization_id,
            ctx=ctx,
            exclude_user_id=ctx.user.id,
        )

        if not other_owners:
            raise HTTPException(
                status_code=400,
                detail="Cannot leave organization as the only owner. "
                "Transfer ownership to another member first.",
            )

    try:
        # Use the organization_service to handle leaving (which handles both local and Auth0)
        success = await organization_service.handle_user_leaving_organization(
            db=db,
            organization_id=organization_id,
            leaving_user=ctx.user,
        )

        if success:
            return {"message": "Successfully left the organization"}
        else:
            raise HTTPException(status_code=500, detail="Failed to leave organization")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


async def _notify_donke_signup(
    organization: schemas.Organization,
    user: User,
    db: AsyncSession,
) -> None:
    """Notify Donke about new sign-up (best-effort).

    Args:
        organization: The newly created organization
        user: The user who created the organization
        db: Database session
    """
    import httpx

    from airweave.core.config import settings

    if not settings.DONKE_URL or not settings.DONKE_API_KEY:
        return

    try:
        # Get plan from billing
        billing = await crud.organization_billing.get_by_organization(
            db, organization_id=organization.id
        )
        # Handle both enum and string cases for billing_plan
        if billing:
            plan = (
                billing.billing_plan.value
                if hasattr(billing.billing_plan, "value")
                else str(billing.billing_plan)
            )
        else:
            plan = "developer"

        # Simple HTTP call to Donke (uses Azure app key)
        async with httpx.AsyncClient() as client:
            await client.post(
                f"{settings.DONKE_URL}/api/notify-signup?code={settings.DONKE_API_KEY}",
                headers={
                    "Content-Type": "application/json",
                },
                json={
                    "organization_name": organization.name,
                    "user_email": user.email,
                    "user_name": user.full_name,
                    "plan": plan,
                    "organization_id": str(organization.id),
                },
                timeout=5.0,
            )
            logger.info(f"Notified Donke about signup for organization {organization.id}")
    except Exception as e:
        logger.warning(f"Failed to notify Donke about signup: {e}")
