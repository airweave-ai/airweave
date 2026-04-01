"""Auth0 event webhook endpoints.

Receives event notifications from Auth0 Actions (e.g. Post Change
Password) and triggers session/token revocation in the Airweave backend.
"""

import hmac
import time
from collections import deque
from typing import Annotated

from fastapi import Depends, Header, HTTPException
from pydantic import BaseModel, StringConstraints
from sqlalchemy.ext.asyncio import AsyncSession

from airweave import schemas
from airweave.adapters.identity.auth0 import auth0_management_client
from airweave.api.deps import Inject
from airweave.api.router import TrailingSlashRouter
from airweave.core.config import settings
from airweave.core.datetime_utils import utc_now_naive
from airweave.core.logging import logger
from airweave.core.protocols.cache import ContextCache
from airweave.db.session import get_db
from airweave.domains.sessions.repository import SessionRepository
from airweave.domains.users.repository import UserRepository

router = TrailingSlashRouter()

_user_repo = UserRepository()
_session_repo = SessionRepository()

_WEBHOOK_WINDOW = 60  # seconds
_WEBHOOK_MAX_REQUESTS = 30  # max calls per window
_webhook_timestamps: deque[float] = deque()


Auth0Id = Annotated[
    str,
    StringConstraints(min_length=1, max_length=128, pattern=r"^[a-zA-Z0-9|_.@+-]+$"),
]


class PasswordChangedPayload(BaseModel):
    """Request body sent by the Auth0 Post Change Password Action."""

    auth0_id: Auth0Id


@router.post("/password-changed")
async def handle_password_changed(
    payload: PasswordChangedPayload,
    x_auth0_webhook_secret: str = Header(..., alias="X-Auth0-Webhook-Secret"),
    db: AsyncSession = Depends(get_db),
    cache: ContextCache = Inject(ContextCache),
) -> dict:
    """Handle Auth0 Post Change Password webhook.

    Revokes all tokens and sessions for the user, and calls Auth0
    Management API to revoke grants (refresh tokens).
    """
    if not settings.AUTH0_WEBHOOK_SECRET:
        raise HTTPException(status_code=403, detail="Invalid webhook secret")

    if not hmac.compare_digest(x_auth0_webhook_secret, settings.AUTH0_WEBHOOK_SECRET):
        raise HTTPException(status_code=403, detail="Invalid webhook secret")

    now_ts = time.monotonic()
    while _webhook_timestamps and _webhook_timestamps[0] < now_ts - _WEBHOOK_WINDOW:
        _webhook_timestamps.popleft()
    if len(_webhook_timestamps) >= _WEBHOOK_MAX_REQUESTS:
        raise HTTPException(status_code=429, detail="Too many requests")
    _webhook_timestamps.append(now_ts)

    user = await _user_repo.get_by_auth0_id(db, auth0_id=payload.auth0_id)
    if not user:
        logger.info("Password change webhook for unknown auth0_id=%s", payload.auth0_id)
        return {"status": "ok"}

    user_schema = schemas.User.model_validate(user)

    now = utc_now_naive()
    user_update = schemas.UserUpdate(tokens_revoked_at=now)
    await _user_repo.update_user_no_auth(db, id=user_schema.id, obj_in=user_update)

    active_sessions = await _session_repo.get_active_by_user(db, user_schema.id)
    revoked_count = await _session_repo.revoke_all_for_user(db, user_schema.id)
    for s in active_sessions:
        await cache.invalidate_session(s.session_id)
    logger.info("Password change: revoked %d sessions for user=%s", revoked_count, user_schema.id)

    await cache.invalidate_user(user_schema.email)

    await db.commit()

    await revoke_auth0_grants(payload.auth0_id)

    return {"status": "ok"}


async def revoke_auth0_grants(auth0_id: str) -> None:
    """Revoke all Auth0 grants for a user (best-effort)."""
    if not auth0_management_client:
        return
    try:
        await auth0_management_client.revoke_user_grants(auth0_id)
    except Exception as e:
        logger.warning(
            "Failed to revoke Auth0 grants for %s: %s — grants may still be active",
            auth0_id,
            e,
        )
