"""API endpoints for organizations."""

from typing import List
from uuid import UUID

from fastapi import Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from airweave import crud, schemas
from airweave.api import deps
from airweave.api.context import ApiContext
from airweave.api.deps import Inject
from airweave.api.router import TrailingSlashRouter
from airweave.core.datetime_utils import utc_now_naive
from airweave.core.logging import logger
from airweave.core.protocols.identity import (
    IdentityProviderConflictError,
    IdentityProviderError,
    IdentityProviderRateLimitError,
    IdentityProviderUnavailableError,
)
from airweave.core.protocols.payment import (
    PaymentProviderError,
    PaymentProviderRateLimitError,
    PaymentProviderUnavailableError,
)
from airweave.domains.organizations import logic
from airweave.domains.organizations.protocols import OrganizationServiceProtocol
from airweave.domains.usage.protocols import UsageLimitCheckerProtocol
from airweave.domains.usage.types import ActionType
from airweave.models.user import User

router = TrailingSlashRouter()


@router.post("/", response_model=schemas.Organization)
async def create_organization(
    organization_data: schemas.OrganizationCreate,
    db: AsyncSession = Depends(deps.get_db),
    user: User = Depends(deps.get_user),
    org_service: OrganizationServiceProtocol = Inject(OrganizationServiceProtocol),
) -> schemas.Organization:
    """Create a new organization with current user as owner.

    This endpoint uses get_user instead of get_context because users creating their
    first organization don't have an organization context yet.
    """
    try:
        return await org_service.create_organization(
            db=db, org_data=organization_data, owner_user=user
        )
    except (IdentityProviderRateLimitError, PaymentProviderRateLimitError) as e:
        logger.warning(f"Rate-limited during org creation: {e}")
        raise HTTPException(
            status_code=429,
            detail="External provider is rate-limiting requests. Please retry shortly.",
            headers={"Retry-After": "10"},
        ) from e
    except IdentityProviderConflictError as e:
        raise HTTPException(status_code=409, detail="Organization already exists") from e
    except (IdentityProviderUnavailableError, PaymentProviderUnavailableError) as e:
        logger.error(f"External provider unavailable during org creation: {e}")
        raise HTTPException(
            status_code=503,
            detail="External service temporarily unavailable. Please retry.",
            headers={"Retry-After": "30"},
        ) from e
    except (IdentityProviderError, PaymentProviderError) as e:
        logger.exception(f"External provider failed during org creation: {e}")
        raise HTTPException(
            status_code=502, detail="External service error during organization creation"
        ) from e
    except Exception as e:
        logger.exception(f"Unexpected failure creating organization: {e}")
        raise HTTPException(status_code=500, detail="Failed to create organization") from e


@router.get("/", response_model=List[schemas.OrganizationWithRole])
async def list_user_organizations(
    db: AsyncSession = Depends(deps.get_db),
    user: User = Depends(deps.get_user),
) -> List[schemas.OrganizationWithRole]:
    """Get all organizations the current user belongs to."""
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
    """Get a specific organization by ID."""
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
    organization_data: schemas.OrganizationCreate,
    db: AsyncSession = Depends(deps.get_db),
    ctx: ApiContext = Depends(deps.get_context),
) -> schemas.OrganizationWithRole:
    """Update an organization. Only owners and admins can update."""
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

    user_role = user_org.role
    user_is_primary = user_org.is_primary

    if user_role not in ["owner", "admin"]:
        raise HTTPException(
            status_code=403, detail="Only organization owners and admins can update organizations"
        )

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
    org_service: OrganizationServiceProtocol = Inject(OrganizationServiceProtocol),
) -> schemas.OrganizationWithRole:
    """Delete an organization. Only owners can delete."""
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

    user_role = user_org.role
    user_is_primary = user_org.is_primary

    user_orgs = await crud.organization.get_user_organizations_with_roles(
        db=db, user_id=ctx.user.id
    )
    allowed, reason = logic.can_user_delete_org(user_role, len(user_orgs))
    if not allowed:
        raise HTTPException(
            status_code=400 if "only organization" in reason.lower() else 403, detail=reason
        )

    try:
        await org_service.delete_organization(
            db=db,
            organization_id=organization_id,
            deleting_user=ctx.user,
        )
        return schemas.OrganizationWithRole(
            id=organization_id,
            name="",
            description="",
            created_at=utc_now_naive(),
            modified_at=utc_now_naive(),
            role=user_role,
            is_primary=user_is_primary,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except Exception as e:
        logger.exception(f"Failed to delete organization {organization_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete organization") from e


@router.post("/{organization_id}/set-primary", response_model=schemas.OrganizationWithRole)
async def set_primary_organization(
    organization_id: UUID,
    db: AsyncSession = Depends(deps.get_db),
    ctx: ApiContext = Depends(deps.get_context),
) -> schemas.OrganizationWithRole:
    """Set an organization as the user's primary organization."""
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


# ---------------------------------------------------------------------------
# Member Management Endpoints
# ---------------------------------------------------------------------------


@router.post("/{organization_id}/invite", response_model=schemas.InvitationResponse)
async def invite_user_to_organization(
    organization_id: UUID,
    invitation_data: schemas.InvitationCreate,
    db: AsyncSession = Depends(deps.get_db),
    ctx: ApiContext = Depends(deps.get_context),
    org_service: OrganizationServiceProtocol = Inject(OrganizationServiceProtocol),
    usage_checker: UsageLimitCheckerProtocol = Inject(UsageLimitCheckerProtocol),
) -> schemas.InvitationResponse:
    """Send organization invitation via identity provider."""
    user_org = _find_user_org(ctx, organization_id)
    if not user_org or not logic.can_manage_members(user_org.role):
        raise HTTPException(
            status_code=403, detail="Only organization owners and admins can invite members"
        )

    try:
        await usage_checker.is_allowed(db, ctx.organization.id, ActionType.TEAM_MEMBERS, amount=1)
        invitation = await org_service.invite_user(
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
        msg = str(e)
        if "usage limit" in msg.lower() or "limit" in msg.lower():
            raise HTTPException(status_code=422, detail=msg) from e
        raise HTTPException(status_code=400, detail=msg) from e


@router.get("/{organization_id}/invitations", response_model=List[schemas.InvitationResponse])
async def get_pending_invitations(
    organization_id: UUID,
    db: AsyncSession = Depends(deps.get_db),
    ctx: ApiContext = Depends(deps.get_context),
    org_service: OrganizationServiceProtocol = Inject(OrganizationServiceProtocol),
) -> List[schemas.InvitationResponse]:
    """Get pending invitations for organization."""
    if not _find_user_org(ctx, organization_id):
        raise HTTPException(
            status_code=404, detail="Organization not found or you don't have access to it"
        )
    try:
        invitations = await org_service.get_pending_invitations(
            db=db,
            organization_id=organization_id,
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
    org_service: OrganizationServiceProtocol = Inject(OrganizationServiceProtocol),
) -> dict:
    """Remove a pending invitation."""
    user_org = _find_user_org(ctx, organization_id)
    if not user_org or not logic.can_manage_members(user_org.role):
        raise HTTPException(
            status_code=403, detail="Only organization owners and admins can remove invitations"
        )
    try:
        success = await org_service.remove_invitation(
            db=db,
            organization_id=organization_id,
            invitation_id=invitation_id,
        )
        if success:
            return {"message": "Invitation removed successfully"}
        raise HTTPException(status_code=404, detail="Invitation not found")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("/{organization_id}/members", response_model=List[schemas.MemberResponse])
async def get_organization_members(
    organization_id: UUID,
    db: AsyncSession = Depends(deps.get_db),
    ctx: ApiContext = Depends(deps.get_context),
    org_service: OrganizationServiceProtocol = Inject(OrganizationServiceProtocol),
) -> List[schemas.MemberResponse]:
    """Get all members of an organization."""
    if not _find_user_org(ctx, organization_id):
        raise HTTPException(
            status_code=404, detail="Organization not found or you don't have access to it"
        )
    try:
        members = await org_service.get_members(db=db, organization_id=organization_id)
        return [
            schemas.MemberResponse(
                id=m["id"],
                email=m["email"],
                name=m["name"],
                role=m["role"],
                status=m["status"],
                is_primary=m["is_primary"],
                auth0_id=m["auth0_id"],
            )
            for m in members
        ]
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.delete("/{organization_id}/members/{user_id}", response_model=dict)
async def remove_member_from_organization(
    organization_id: UUID,
    user_id: UUID,
    db: AsyncSession = Depends(deps.get_db),
    ctx: ApiContext = Depends(deps.get_context),
    org_service: OrganizationServiceProtocol = Inject(OrganizationServiceProtocol),
) -> dict:
    """Remove a member from organization."""
    user_org = _find_user_org(ctx, organization_id)
    if not user_org or not logic.can_manage_members(user_org.role):
        raise HTTPException(
            status_code=403, detail="Only organization owners and admins can remove members"
        )
    if user_id == ctx.user.id:
        raise HTTPException(
            status_code=400, detail="Use the leave organization endpoint to remove yourself"
        )
    try:
        success = await org_service.remove_member(
            db=db,
            organization_id=organization_id,
            user_id=user_id,
            remover_user=ctx.user,
        )
        if success:
            return {"message": "Member removed successfully"}
        raise HTTPException(status_code=404, detail="Member not found")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/{organization_id}/leave", response_model=dict)
async def leave_organization(
    organization_id: UUID,
    db: AsyncSession = Depends(deps.get_db),
    ctx: ApiContext = Depends(deps.get_context),
    org_service: OrganizationServiceProtocol = Inject(OrganizationServiceProtocol),
) -> dict:
    """Leave an organization."""
    user_org = _find_user_org(ctx, organization_id)
    if not user_org:
        raise HTTPException(status_code=404, detail="You are not a member of this organization")

    user_orgs = await crud.organization.get_user_organizations_with_roles(
        db=db, user_id=ctx.user.id
    )
    other_owners = await crud.organization.get_organization_owners(
        db=db,
        organization_id=organization_id,
        ctx=ctx,
        exclude_user_id=ctx.user.id,
    )

    allowed, reason = logic.can_user_leave_org(user_org.role, len(other_owners), len(user_orgs))
    if not allowed:
        raise HTTPException(status_code=400, detail=reason)

    try:
        success = await org_service.leave_organization(
            db=db,
            organization_id=organization_id,
            leaving_user=ctx.user,
        )
        if success:
            return {"message": "Successfully left the organization"}
        raise HTTPException(status_code=500, detail="Failed to leave organization")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _find_user_org(ctx: ApiContext, organization_id: UUID):
    """Find the user's membership in the given organization from the auth context."""
    for org in ctx.user.user_organizations:
        if org.organization.id == organization_id:
            return org
    return None
