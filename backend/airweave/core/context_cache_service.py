"""Redis-based caching service for API context data.

Provides caching for frequently accessed data like organizations and users
to reduce database load on high-traffic endpoints.
"""

import json
from typing import Optional
from uuid import UUID

from airweave import schemas
from airweave.core import credentials
from airweave.core.logging import ContextualLogger
from airweave.core.logging import logger as default_logger
from airweave.core.redis_client import redis_client


class ContextCacheService:
    """Redis-backed cache for API context data.

    Caches organization, user, and API key mapping data to reduce database queries
    on every request. Implements cache-aside pattern with automatic TTL-based expiration.
    """

    # Cache key prefixes
    ORG_KEY_PREFIX = "context:org"
    USER_KEY_PREFIX = "context:user"
    API_KEY_PREFIX = "context:apikey"
    JWT_BLACKLIST_PREFIX = "jwt:blacklist"
    JWT_USER_BLACKLIST_PREFIX = "jwt:user_blacklist"

    # Cache TTLs (in seconds)
    ORG_TTL = 300
    USER_TTL = 180
    API_KEY_TTL = 600
    # JWT blacklist TTL should match or exceed the maximum JWT expiration time
    # Auth0 default is 24 hours, we set to 48 hours to be safe
    JWT_BLACKLIST_TTL = 172800  # 48 hours

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

    def _api_key_cache_key(self, api_key_hash: str) -> str:
        """Get Redis cache key for API key mapping.

        Args:
            api_key_hash: Hash or partial hash of the API key (for security)

        Returns:
            Redis key string
        """
        return f"{self.API_KEY_PREFIX}:{api_key_hash}"

    async def get_organization(self, org_id: UUID) -> Optional[schemas.Organization]:
        """Get organization from cache.

        Args:
            org_id: Organization UUID

        Returns:
            Organization schema if cached, None otherwise
        """
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
            self.logger.error(f"Error reading organization from cache: {e}. Falling back to DB.")
            return None

    async def set_organization(self, organization: schemas.Organization) -> bool:
        """Store organization in cache.

        Args:
            organization: Organization schema to cache

        Returns:
            True if cached successfully, False otherwise
        """
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
            self.logger.error(f"Error reading user from cache: {e}. Falling back to DB.")
            return None

    async def set_user(self, user: schemas.User) -> bool:
        """Store user in cache.

        Args:
            user: User schema to cache

        Returns:
            True if cached successfully, False otherwise
        """
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

    async def get_api_key_org_id(self, api_key: str) -> Optional[UUID]:
        """Get organization ID for an API key from cache.

        The API key is encrypted before being used as a cache key for security,
        so the raw API key is never stored in Redis.

        Args:
            api_key: The API key string

        Returns:
            Organization UUID if cached, None otherwise
        """
        try:
            # Encrypt the API key for secure cache key
            encrypted_key = credentials.encrypt({"key": api_key})
            cache_key = self._api_key_cache_key(encrypted_key)
            cached_data = await redis_client.client.get(cache_key)

            if cached_data:
                self.logger.debug("Cache HIT: API key organization mapping")
                # Value is just the UUID string
                return UUID(cached_data.decode("utf-8"))

            self.logger.debug("Cache MISS: API key organization mapping")
            return None

        except Exception as e:
            self.logger.error(f"Error reading API key mapping from cache: {e}. Falling back to DB.")
            return None

    async def set_api_key_org_id(self, api_key: str, org_id: UUID) -> bool:
        """Store API key → organization ID mapping in cache.

        The API key is encrypted for the cache key (so raw key is never in Redis),
        but the org_id value is stored as plain text since it's not sensitive.

        Args:
            api_key: The API key string
            org_id: Organization UUID

        Returns:
            True if cached successfully, False otherwise
        """
        try:
            # Encrypt the API key for secure cache key
            encrypted_key = credentials.encrypt({"key": api_key})
            cache_key = self._api_key_cache_key(encrypted_key)

            # Store org_id as plain string
            org_id_str = str(org_id)

            # Store with TTL
            await redis_client.client.setex(cache_key, self.API_KEY_TTL, org_id_str)

            self.logger.debug(f"Cached API key mapping for {self.API_KEY_TTL}s")
            return True

        except Exception as e:
            self.logger.warning(f"Error caching API key mapping: {e}. Request will continue.")
            return False

    async def invalidate_api_key(self, api_key: str) -> bool:
        """Invalidate cached API key mapping.

        Call this when an API key is deleted or modified.

        Args:
            api_key: The API key string

        Returns:
            True if invalidated successfully, False otherwise
        """
        try:
            # Encrypt the API key to get the cache key
            encrypted_key = credentials.encrypt({"key": api_key})
            cache_key = self._api_key_cache_key(encrypted_key)
            await redis_client.client.delete(cache_key)
            self.logger.debug("Invalidated API key cache")
            return True

        except Exception as e:
            self.logger.warning(f"Error invalidating API key cache: {e}")
            return False

    async def invalidate_organization(self, org_id: UUID) -> bool:
        """Invalidate cached organization data.

        Call this when organization data changes (e.g., feature flags, billing).

        Args:
            org_id: Organization UUID

        Returns:
            True if invalidated successfully, False otherwise
        """
        try:
            cache_key = self._org_cache_key(org_id)
            await redis_client.client.delete(cache_key)
            self.logger.debug(f"Invalidated organization cache for {org_id}")
            return True

        except Exception as e:
            self.logger.warning(f"Error invalidating organization cache: {e}")
            return False

    async def invalidate_user(self, user_email: str) -> bool:
        """Invalidate cached user data.

        Call this when user attributes or organization memberships change so the
        next request reloads fresh data from the database.

        Args:
            user_email: User email address

        Returns:
            True if invalidated successfully, False otherwise
        """
        try:
            cache_key = self._user_cache_key(user_email)
            await redis_client.client.delete(cache_key)
            self.logger.debug(f"Invalidated user cache for {user_email}")
            return True

        except Exception as e:
            self.logger.warning(f"Error invalidating user cache: {e}")
            return False

    # JWT Blacklisting Methods

    def _jwt_blacklist_key(self, jti: str) -> str:
        """Get Redis cache key for blacklisted JWT token.

        Args:
            jti: JWT ID (jti claim from token)

        Returns:
            Redis key string
        """
        return f"{self.JWT_BLACKLIST_PREFIX}:{jti}"

    def _jwt_user_blacklist_key(self, user_email: str) -> str:
        """Get Redis cache key for user's JWT blacklist timestamp.

        Args:
            user_email: User email address

        Returns:
            Redis key string
        """
        return f"{self.JWT_USER_BLACKLIST_PREFIX}:{user_email}"

    async def blacklist_jwt(self, jti: str, ttl_seconds: Optional[int] = None) -> bool:
        """Blacklist a JWT token by its jti (JWT ID) claim.

        Once blacklisted, the token will be rejected even if it's otherwise valid.
        The blacklist entry expires after the specified TTL (defaults to JWT_BLACKLIST_TTL).

        Args:
            jti: JWT ID (jti claim) to blacklist
            ttl_seconds: Optional custom TTL in seconds (defaults to JWT_BLACKLIST_TTL)

        Returns:
            True if blacklisted successfully, False otherwise
        """
        try:
            cache_key = self._jwt_blacklist_key(jti)
            ttl = ttl_seconds or self.JWT_BLACKLIST_TTL
            await redis_client.client.setex(cache_key, ttl, "1")
            self.logger.info(f"Blacklisted JWT {jti} for {ttl}s")
            return True

        except Exception as e:
            self.logger.error(f"Error blacklisting JWT {jti}: {e}")
            return False

    async def is_jwt_blacklisted(self, jti: str) -> bool:
        """Check if a JWT token is blacklisted.

        Args:
            jti: JWT ID (jti claim) to check

        Returns:
            True if token is blacklisted, False otherwise
        """
        try:
            cache_key = self._jwt_blacklist_key(jti)
            exists = await redis_client.client.exists(cache_key)
            return bool(exists)

        except Exception as e:
            self.logger.error(f"Error checking JWT blacklist for {jti}: {e}")
            # Fail closed - if we can't check Redis, deny the token
            return True

    async def blacklist_user_tokens(self, user_email: str, ttl_seconds: Optional[int] = None) -> bool:
        """Blacklist all JWT tokens for a specific user.

        This creates a timestamp entry. Any JWT issued before this timestamp
        will be rejected. This is more efficient than blacklisting individual tokens.

        Args:
            user_email: User email to blacklist tokens for
            ttl_seconds: Optional custom TTL in seconds (defaults to JWT_BLACKLIST_TTL)

        Returns:
            True if blacklisted successfully, False otherwise
        """
        try:
            cache_key = self._jwt_user_blacklist_key(user_email)
            ttl = ttl_seconds or self.JWT_BLACKLIST_TTL

            # Store current timestamp - any JWT issued before this will be invalid
            import time

            timestamp = str(int(time.time()))
            await redis_client.client.setex(cache_key, ttl, timestamp)
            self.logger.info(f"Blacklisted all tokens for user {user_email} (issued before {timestamp})")
            return True

        except Exception as e:
            self.logger.error(f"Error blacklisting user tokens for {user_email}: {e}")
            return False

    async def is_user_token_blacklisted(self, user_email: str, token_issued_at: int) -> bool:
        """Check if a user's token is blacklisted based on issue timestamp.

        Args:
            user_email: User email from token
            token_issued_at: Token 'iat' (issued at) timestamp

        Returns:
            True if token was issued before blacklist timestamp, False otherwise
        """
        try:
            cache_key = self._jwt_user_blacklist_key(user_email)
            blacklist_timestamp = await redis_client.client.get(cache_key)

            if not blacklist_timestamp:
                return False

            # Token is blacklisted if it was issued before the blacklist timestamp
            blacklist_ts = int(blacklist_timestamp.decode("utf-8"))
            return token_issued_at < blacklist_ts

        except Exception as e:
            self.logger.error(f"Error checking user token blacklist for {user_email}: {e}")
            # Fail closed - if we can't check Redis, deny the token
            return True

    async def invalidate_user_with_tokens(self, user_email: str) -> bool:
        """Invalidate user cache AND blacklist all their JWT tokens.

        This is the recommended method to call when you need to immediately
        revoke access for a user (e.g., account suspension, security incident).

        Args:
            user_email: User email address

        Returns:
            True if both operations succeeded, False otherwise
        """
        cache_invalidated = await self.invalidate_user(user_email)
        tokens_blacklisted = await self.blacklist_user_tokens(user_email)

        if cache_invalidated and tokens_blacklisted:
            self.logger.info(f"Successfully invalidated user {user_email} and blacklisted all tokens")
            return True

        self.logger.warning(
            f"Partial invalidation for user {user_email}: "
            f"cache={cache_invalidated}, tokens={tokens_blacklisted}"
        )
        return False


context_cache = ContextCacheService()
