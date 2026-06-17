"""API endpoints for users.

Thin HTTP layer — delegates business logic to ``UserServiceProtocol``.
"""

from typing import List, Optional
from uuid import UUID

from fastapi import Depends, HTTPException, Request
from fastapi_auth0 import Auth0User
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from airweave import schemas
from airweave.api import deps
from airweave.api.auth import auth0
from airweave.api.deps import Inject
from airweave.api.jwt_utils import extract_sid
from airweave.api.router import TrailingSlashRouter
from airweave.api.v1.endpoints.auth0_events import revoke_auth0_grants
from airweave.core.datetime_utils import utc_now_naive
from airweave.core.logging import logger
from airweave.core.protocols.cache import ContextCache
from airweave.db.session import get_db
from airweave.domains.sessions.repository import SessionRepository
from airweave.domains.users.protocols import UserServiceProtocol
from airweave.domains.users.repository import UserRepository
from airweave.domains.users.types import is_email_authorized
from airweave.models.user_session import UserSession as UserSessionModel
from airweave.schemas import OrganizationWithRole, User
from airweave.schemas.user_session import SessionTerminationResult, UserSessionRead

router = TrailingSlashRouter()

_session_repo = SessionRepository()
_user_repo = UserRepository()


@router.get("/", response_model=User)
async def read_user(
    *,
    current_user: schemas.User = Depends(deps.get_user),
) -> schemas.User:
    """Get current user with all organization relationships."""
    return current_user


@router.get("/me/organizations", response_model=List[OrganizationWithRole])
async def read_user_organizations(
    *,
    db: AsyncSession = Depends(deps.get_db),
    current_user: schemas.User = Depends(deps.get_user),
    user_service: UserServiceProtocol = Inject(UserServiceProtocol),
) -> List[OrganizationWithRole]:
    """Get all organizations that the current user is a member of."""
    return await user_service.get_user_organizations(db, user_id=current_user.id)


@router.post("/create_or_update", response_model=User)
async def create_or_update_user(
    user_data: schemas.UserCreate,
    db: AsyncSession = Depends(deps.get_db),
    auth0_user: Optional[Auth0User] = Depends(auth0.get_user),
    user_service: UserServiceProtocol = Inject(UserServiceProtocol),
) -> schemas.User:
    """Create new user or sync existing user's Auth0 organizations.

    Can only create user with the same email as the authenticated user.
    """
    auth0_email = auth0_user.email if auth0_user else None
    if not auth0_email or not is_email_authorized(user_data.email, auth0_email):
        logger.error(f"User {user_data.email} is not authorized to create user {auth0_email}")
        raise HTTPException(
            status_code=403,
            detail="You are not authorized to create this user.",
        )

    result = await user_service.create_or_update(db, user_data, auth0_user)
    return result.user


@router.get("/me/sessions", response_model=List[UserSessionRead])
async def list_sessions(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: schemas.User = Depends(deps.get_user),
) -> list[UserSessionRead]:
    """List active sessions for the current user."""
    current_sid = extract_sid(request)
    sessions = await _session_repo.get_active_by_user(db, current_user.id)
    result = []
    for s in sessions:
        read = UserSessionRead.model_validate(s)
        read.is_current = s.session_id == current_sid if current_sid else False
        result.append(read)
    return result


@router.delete("/me/sessions/{session_id}", response_model=SessionTerminationResult)
async def terminate_session(
    session_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: schemas.User = Depends(deps.get_user),
    cache: ContextCache = Inject(ContextCache),
) -> SessionTerminationResult:
    """Terminate a specific session by its DB id. Cannot terminate the current session."""
    stmt = select(UserSessionModel).where(
        UserSessionModel.id == session_id,
        UserSessionModel.user_id == current_user.id,
    )
    result = await db.execute(stmt)
    session = result.scalar_one_or_none()

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.is_revoked:
        raise HTTPException(status_code=400, detail="Session already revoked")

    current_sid = extract_sid(request)
    if current_sid and session.session_id == current_sid:
        raise HTTPException(status_code=400, detail="Cannot terminate current session")

    await _session_repo.revoke(db, session.session_id, user_id=current_user.id)
    await cache.invalidate_session(session.session_id)
    await db.commit()
    return SessionTerminationResult(terminated_count=1, terminated_at=utc_now_naive())


@router.delete("/me/sessions", response_model=SessionTerminationResult)
async def terminate_other_sessions(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: schemas.User = Depends(deps.get_user),
    cache: ContextCache = Inject(ContextCache),
) -> SessionTerminationResult:
    """Terminate all sessions except the current one."""
    current_sid = extract_sid(request)
    if current_sid is None:
        raise HTTPException(
            status_code=400,
            detail="Cannot determine current session; unable to exclude it from termination",
        )
    active_sessions = await _session_repo.get_active_by_user(db, current_user.id)
    count = await _session_repo.revoke_all_for_user(
        db, current_user.id, except_session_id=current_sid
    )
    for s in active_sessions:
        if s.session_id != current_sid:
            await cache.invalidate_session(s.session_id)
    await cache.invalidate_user(current_user.email)
    await db.commit()
    return SessionTerminationResult(terminated_count=count, terminated_at=utc_now_naive())


@router.post("/me/terminate-all-sessions", response_model=SessionTerminationResult)
async def terminate_all_sessions(
    db: AsyncSession = Depends(get_db),
    current_user: schemas.User = Depends(deps.get_user),
    cache: ContextCache = Inject(ContextCache),
) -> SessionTerminationResult:
    """Nuclear option: revoke ALL sessions and tokens including current."""
    now = utc_now_naive()
    user_update = schemas.UserUpdate(tokens_revoked_at=now)
    await _user_repo.update_user_no_auth(db, id=current_user.id, obj_in=user_update)

    active_sessions = await _session_repo.get_active_by_user(db, current_user.id)
    count = await _session_repo.revoke_all_for_user(db, current_user.id)
    for s in active_sessions:
        await cache.invalidate_session(s.session_id)
    await cache.invalidate_user(current_user.email)

    await db.commit()

    if current_user.auth0_id:
        await revoke_auth0_grants(current_user.auth0_id)

    return SessionTerminationResult(terminated_count=count, terminated_at=now)
