"""Redis-based caching service for API context data.

Provides caching for frequently accessed data like organizations and users
to reduce database load on high-traffic endpoints.
"""

import json
from typing import Optional
from uuid import UUID

from airweave import schemas
from airweave.core.config import settings
from airweave.core.logging import ContextualLogger
from airweave.core.logging import logger as default_logger
from airweave.core.redis_client import redis_client


class ContextCacheService:
    """Redis-backed cache for API context data.

    Caches organization and user data to reduce database queries on every request.
    Implements cache-aside pattern with automatic TTL-based expiration.
    """

    # Cache key prefixes
    ORG_KEY_PREFIX = "context:org"
    USER_KEY_PREFIX = "context:user"

    # Cache TTLs (in seconds)
    ORG_TTL = 300  # 5 minutes - orgs change infrequently
    USER_TTL = 180  # 3 minutes - users change less frequently than sessions

    def __init__(self, logger: Optional[ContextualLogger] = None):
        """Initialize the context cache service.

        Args:
            logger: Optional contextual logger for structured logging
        """
        self.logger = logger or default_logger.with_context(component="context_cache")

    def _org_cache_key(self, org_id: UUID) -> str:
        """Get Redis cache key for organization.

        Args:
            org_id: Organization UUID

        Returns:
            Redis key string
        """
        return f"{self.ORG_KEY_PREFIX}:{org_id}"

    def _user_cache_key(self, user_email: str) -> str:
        """Get Redis cache key for user.

        Args:
            user_email: User email address (unique identifier)

        Returns:
            Redis key string
        """
        # Use email as key since that's how we look up users
        return f"{self.USER_KEY_PREFIX}:{user_email}"

    async def get_organization(self, org_id: UUID) -> Optional[schemas.Organization]:
        """Get organization from cache.

        Args:
            org_id: Organization UUID

        Returns:
            Organization schema if cached, None otherwise
        """
        # Skip cache in local development
        if settings.LOCAL_DEVELOPMENT:
            return None

        try:
            cache_key = self._org_cache_key(org_id)
            cached_data = await redis_client.client.get(cache_key)

            if cached_data:
                self.logger.debug(f"Cache HIT: Organization {org_id}")
                data = json.loads(cached_data)
                return schemas.Organization.model_validate(data)

            self.logger.debug(f"Cache MISS: Organization {org_id}")
            return None

        except Exception as e:
            # Log error but don't fail - just return None to fall back to DB
            self.logger.warning(f"Error reading organization from cache: {e}. Falling back to DB.")
            return None

    async def set_organization(self, organization: schemas.Organization) -> bool:
        """Store organization in cache.

        Args:
            organization: Organization schema to cache

        Returns:
            True if cached successfully, False otherwise
        """
        # Skip cache in local development
        if settings.LOCAL_DEVELOPMENT:
            return False

        try:
            cache_key = self._org_cache_key(organization.id)
            # Serialize to JSON
            data = organization.model_dump(mode="json")
            json_data = json.dumps(data)

            # Store with TTL
            await redis_client.client.setex(cache_key, self.ORG_TTL, json_data)

            self.logger.debug(f"Cached organization {organization.id} for {self.ORG_TTL}s")
            return True

        except Exception as e:
            # Log error but don't fail the request
            self.logger.warning(f"Error caching organization: {e}. Request will continue.")
            return False

    async def get_user(self, user_email: str) -> Optional[schemas.User]:
        """Get user from cache.

        Args:
            user_email: User email address

        Returns:
            User schema if cached, None otherwise
        """
        # Skip cache in local development
        if settings.LOCAL_DEVELOPMENT:
            return None

        try:
            cache_key = self._user_cache_key(user_email)
            cached_data = await redis_client.client.get(cache_key)

            if cached_data:
                self.logger.debug(f"Cache HIT: User {user_email}")
                data = json.loads(cached_data)
                return schemas.User.model_validate(data)

            self.logger.debug(f"Cache MISS: User {user_email}")
            return None

        except Exception as e:
            self.logger.warning(f"Error reading user from cache: {e}. Falling back to DB.")
            return None

    async def set_user(self, user: schemas.User) -> bool:
        """Store user in cache.

        Args:
            user: User schema to cache

        Returns:
            True if cached successfully, False otherwise
        """
        # Skip cache in local development
        if settings.LOCAL_DEVELOPMENT:
            return False

        try:
            cache_key = self._user_cache_key(user.email)
            # Serialize to JSON
            data = user.model_dump(mode="json")
            json_data = json.dumps(data)

            # Store with TTL
            await redis_client.client.setex(cache_key, self.USER_TTL, json_data)

            self.logger.debug(f"Cached user {user.email} for {self.USER_TTL}s")
            return True

        except Exception as e:
            self.logger.warning(f"Error caching user: {e}. Request will continue.")
            return False

    async def invalidate_organization(self, org_id: UUID) -> bool:
        """Invalidate (delete) organization from cache.

        Call this when organization data changes (e.g., after update).

        Args:
            org_id: Organization UUID

        Returns:
            True if invalidated successfully, False otherwise
        """
        try:
            cache_key = self._org_cache_key(org_id)
            await redis_client.client.delete(cache_key)
            self.logger.debug(f"Invalidated organization cache: {org_id}")
            return True

        except Exception as e:
            self.logger.warning(f"Error invalidating organization cache: {e}")
            return False

    async def invalidate_user(self, user_email: str) -> bool:
        """Invalidate (delete) user from cache.

        Call this when user data changes (e.g., after update).

        Args:
            user_email: User email address

        Returns:
            True if invalidated successfully, False otherwise
        """
        try:
            cache_key = self._user_cache_key(user_email)
            await redis_client.client.delete(cache_key)
            self.logger.debug(f"Invalidated user cache: {user_email}")
            return True

        except Exception as e:
            self.logger.warning(f"Error invalidating user cache: {e}")
            return False

    async def get_cache_stats(self) -> dict:
        """Get cache statistics for monitoring.

        Returns:
            Dict with cache statistics
        """
        try:
            # Count cached organizations
            org_keys = []
            async for key in redis_client.client.scan_iter(match=f"{self.ORG_KEY_PREFIX}:*"):
                org_keys.append(key)

            # Count cached users
            user_keys = []
            async for key in redis_client.client.scan_iter(match=f"{self.USER_KEY_PREFIX}:*"):
                user_keys.append(key)

            return {
                "organizations_cached": len(org_keys),
                "users_cached": len(user_keys),
                "org_ttl": self.ORG_TTL,
                "user_ttl": self.USER_TTL,
            }

        except Exception as e:
            self.logger.error(f"Error getting cache stats: {e}")
            return {
                "error": str(e),
                "organizations_cached": 0,
                "users_cached": 0,
            }


# Global instance for convenience
context_cache = ContextCacheService()
