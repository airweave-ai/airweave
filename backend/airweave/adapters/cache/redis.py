"""Redis-backed context cache implementing ContextCache protocol.

Uses SHA-256 for API key cache keys instead of Fernet encryption,
removing the dependency on the credentials module.
"""

import hashlib
import json
import logging
from typing import Optional
from uuid import UUID

from airweave import schemas
from airweave.core.protocols.cache import ContextCache

logger = logging.getLogger(__name__)

ORG_KEY_PREFIX = "context:org"
USER_KEY_PREFIX = "context:user"
API_KEY_PREFIX = "context:apikey"

ORG_TTL = 30
USER_TTL = 30
API_KEY_TTL = 600


class RedisContextCache(ContextCache):
    """Redis-backed context cache for the API hot path.

    Injected into deps.py via the container. All methods are fail-safe —
    errors are logged and swallowed so the request falls through to DB.
    """

    def __init__(self, redis_client) -> None:
        """Initialize RedisContextCache."""
        self._redis = redis_client

    @staticmethod
    def _hash_api_key(api_key: str) -> str:
        return hashlib.sha256(api_key.encode()).hexdigest()

    # --- Read ---

    async def get_organization(self, org_id: UUID) -> Optional[schemas.Organization]:
        """Return cached organization or None on miss."""
        try:
            data = await self._redis.get(f"{ORG_KEY_PREFIX}:{org_id}")
            if data:
                return schemas.Organization.model_validate(json.loads(data))
            return None
        except Exception as e:
            logger.debug("Cache read error (org %s): %s", org_id, e)
            return None

    async def get_user(self, user_email: str) -> Optional[schemas.User]:
        """Return cached user or None on miss."""
        try:
            data = await self._redis.get(f"{USER_KEY_PREFIX}:{user_email}")
            if data:
                return schemas.User.model_validate(json.loads(data))
            return None
        except Exception as e:
            logger.debug("Cache read error (user %s): %s", user_email, e)
            return None

    async def get_api_key_org_id(self, api_key: str) -> Optional[UUID]:
        """Return cached org ID for an API key or None on miss."""
        try:
            key_hash = self._hash_api_key(api_key)
            data = await self._redis.get(f"{API_KEY_PREFIX}:{key_hash}")
            if data:
                return UUID(data.decode("utf-8"))
            return None
        except Exception as e:
            logger.debug("Cache read error (api_key): %s", e)
            return None

    # --- Write ---

    async def set_organization(self, organization: schemas.Organization) -> None:
        """Cache an organization with TTL."""
        try:
            payload = json.dumps(organization.model_dump(mode="json"))
            await self._redis.setex(f"{ORG_KEY_PREFIX}:{organization.id}", ORG_TTL, payload)
        except Exception as e:
            logger.debug("Cache write error (org %s): %s", organization.id, e)

    async def set_user(self, user: schemas.User) -> None:
        """Cache a user with TTL."""
        try:
            payload = json.dumps(user.model_dump(mode="json"))
            await self._redis.setex(f"{USER_KEY_PREFIX}:{user.email}", USER_TTL, payload)
        except Exception as e:
            logger.debug("Cache write error (user %s): %s", user.email, e)

    async def set_api_key_org_id(self, api_key: str, org_id: UUID) -> None:
        """Cache an API key → org ID mapping with TTL."""
        try:
            key_hash = self._hash_api_key(api_key)
            await self._redis.setex(f"{API_KEY_PREFIX}:{key_hash}", API_KEY_TTL, str(org_id))
        except Exception as e:
            logger.debug("Cache write error (api_key): %s", e)

    # --- Invalidation ---

    async def invalidate_organization(self, org_id: UUID) -> None:
        """Remove cached organization entry."""
        try:
            await self._redis.delete(f"{ORG_KEY_PREFIX}:{org_id}")
        except Exception as e:
            logger.debug("Cache invalidation error (org %s): %s", org_id, e)

    async def invalidate_user(self, user_email: str) -> None:
        """Remove cached user entry."""
        try:
            await self._redis.delete(f"{USER_KEY_PREFIX}:{user_email}")
        except Exception as e:
            logger.debug("Cache invalidation error (user %s): %s", user_email, e)

    async def invalidate_api_key(self, api_key: str) -> None:
        """Remove cached API key entry."""
        try:
            key_hash = self._hash_api_key(api_key)
            await self._redis.delete(f"{API_KEY_PREFIX}:{key_hash}")
        except Exception as e:
            logger.debug("Cache invalidation error (api_key): %s", e)
