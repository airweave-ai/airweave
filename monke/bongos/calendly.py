"""Calendly-specific bongo implementation.

Creation and deletion phases are skipped. There is always exactly one active
event type, which is fetched in the fetch step (fetch_existing_entities).
No event types are created or deleted. The bongo can update the existing
event type (e.g. name/description) for verification.
"""

import asyncio
import time
import uuid
from typing import Any, Dict, List, Optional

import httpx
from monke.bongos.base_bongo import BaseBongo
from monke.utils.logging import get_logger


# Calendly API limit: event type name max 55 characters
CALENDLY_EVENT_TYPE_NAME_MAX_LENGTH = 55


class CalendlyBongo(BaseBongo):
    """Bongo for Calendly: one existing event type, no create/delete.

    - Creation is skipped (create_entities returns []). Use the fetch step.
    - fetch_existing_entities() fetches the single active event type from the API.
    - OAuth access token as bearer token.
    - Can update the existing event type for verification.
    - Deletion and cleanup are no-ops (pre-existing event type is left unchanged).
    """

    connector_type = "calendly"

    API_BASE = "https://api.calendly.com"

    def __init__(self, credentials: Dict[str, Any], **kwargs):
        """Initialize the Calendly bongo.

        Args:
            credentials: Dict with at least "access_token" (Calendly OAuth token)
            **kwargs: Configuration from config file
        """
        super().__init__(credentials)
        self._credentials = credentials  # Store for token refresh
        self.access_token: str = credentials["access_token"]
        self.entity_count: int = 1  # Always exactly one (existing) event type
        self.openai_model: str = kwargs.get("openai_model", "gpt-4.1-mini")
        self.max_concurrency: int = int(kwargs.get("max_concurrency", 1))
        rate_limit_ms = int(kwargs.get("rate_limit_delay_ms", 500))
        self.rate_limit_delay: float = rate_limit_ms / 1000.0

        # Store Composio config for token refresh if available
        self._composio_config = kwargs.get("composio_config")

        # Runtime state
        self._user_uri: Optional[str] = None
        self._organization_uri: Optional[str] = None
        self._event_types: List[Dict[str, Any]] = []
        self._token_refreshed = False  # Track if we've refreshed the token

        # Pacing
        self.last_request_time = 0.0

        self.logger = get_logger("calendly_bongo")

    def _headers(self) -> Dict[str, str]:
        """Get HTTP headers for Calendly API requests."""
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }

    async def _rate_limit(self):
        """Apply rate limiting between requests."""
        now = time.time()
        elapsed = now - self.last_request_time
        if elapsed < self.rate_limit_delay:
            await asyncio.sleep(self.rate_limit_delay - elapsed)
        self.last_request_time = time.time()

    async def _request_with_429_retry(
        self,
        client: httpx.AsyncClient,
        method: str,
        url: str,
        max_attempts: int = 5,
        **kwargs: Any,
    ) -> httpx.Response:
        """Perform HTTP request with retry on 429 (rate limit).

        Waits using Retry-After or X-RateLimit-Reset when present,
        otherwise exponential backoff. Returns the response after
        non-429 or after max_attempts (caller should raise_for_status as needed).
        """
        attempt = 0
        while True:
            attempt += 1
            await self._rate_limit()
            resp = await client.request(method.upper(), url, **kwargs)
            if resp.status_code != 429:
                return resp
            if attempt >= max_attempts:
                self.logger.warning(
                    f"Calendly API 429 after {max_attempts} attempts; returning last response"
                )
                return resp
            wait_s = 2.0 * (2 ** (attempt - 1))
            headers = resp.headers
            retry_after = headers.get("Retry-After")
            if retry_after is not None:
                try:
                    wait_s = max(1.0, min(120.0, float(retry_after)))
                except (ValueError, TypeError) as e:
                    self.logger.debug(
                        "Failed to parse Calendly Retry-After header %r; using default backoff",
                        retry_after,
                        exc_info=e,
                    )
            else:
                reset_header = headers.get("X-RateLimit-Reset") or headers.get(
                    "x-ratelimit-reset"
                )
                if reset_header is not None:
                    try:
                        reset_val = float(reset_header)
                        now = time.time()
                        if reset_val > now:
                            wait_s = min(300.0, reset_val - now)
                        else:
                            wait_s = min(300.0, reset_val)
                        wait_s = max(1.0, wait_s)
                    except (ValueError, TypeError) as e:
                        self.logger.debug(
                            "Failed to parse Calendly rate-limit reset header %r; using default backoff",
                            reset_header,
                            exc_info=e,
                        )
                else:
                    wait_s = min(30.0, wait_s)
            self.logger.warning(
                f"Calendly API rate limit (429); retrying in {wait_s:.1f}s (attempt {attempt}/{max_attempts})"
            )
            await asyncio.sleep(wait_s)

    async def _refresh_token(self):
        """Refresh the access token from Composio."""
        try:
            from monke.auth.broker import ComposioBroker

            self.logger.info("🔄 Refreshing Calendly access token...")

            if self._composio_config:
                # Use the specific Composio configuration for this connector
                broker = ComposioBroker(
                    account_id=self._composio_config["account_id"],
                    auth_config_id=self._composio_config["auth_config_id"],
                )
                fresh_creds = await broker.get_credentials("calendly")
            else:
                # Fallback to generic credentials resolver
                from monke.auth.credentials_resolver import resolve_credentials

                fresh_creds = await resolve_credentials("calendly", self._credentials)

            self.access_token = fresh_creds["access_token"]
            self._token_refreshed = True
            self.logger.info("✅ Calendly access token refreshed")
        except Exception as e:
            self.logger.error(f"❌ Failed to refresh Calendly token: {e}")
            raise

    async def _ensure_user(self):
        """Ensure we have the user URI and organization URI."""
        if self._user_uri and self._organization_uri:
            return

        async with httpx.AsyncClient() as client:
            resp = await self._request_with_429_retry(
                client, "get", f"{self.API_BASE}/users/me", headers=self._headers()
            )

            # Handle 401 by refreshing token and retrying
            if resp.status_code == 401:
                self.logger.warning(
                    "⚠️ Got 401 when fetching user info, refreshing token..."
                )
                await self._refresh_token()
                resp = await self._request_with_429_retry(
                    client, "get", f"{self.API_BASE}/users/me", headers=self._headers()
                )

            resp.raise_for_status()
            data = resp.json()
            resource = data.get("resource", {})
            self._user_uri = resource.get("uri")
            self._organization_uri = resource.get("current_organization")
            self.logger.info(f"✅ Got user URI: {self._user_uri}")
            if self._organization_uri:
                self.logger.info(f"✅ Got organization URI: {self._organization_uri}")
            else:
                self.logger.warning(
                    "⚠️ No organization URI found, will use user context"
                )

    async def create_entities(self) -> List[Dict[str, Any]]:
        """Creation is skipped for Calendly; use the fetch step instead."""
        self.logger.info(
            "🥁 Calendly: creation skipped (use fetch step to load the existing event type)"
        )
        return []

    async def fetch_existing_entities(self) -> List[Dict[str, Any]]:
        """Fetch the single existing active event type from Calendly.

        There is always exactly one active event type; it is fetched here and
        used for sync/verify/update. No event types are ever created or deleted.
        """
        self.logger.info("📥 Fetching the single existing Calendly event type")
        await self._ensure_user()

        entities: List[Dict[str, Any]] = []
        url = f"{self.API_BASE}/event_types"
        params: Dict[str, Any] = {"count": 10}
        if self._organization_uri:
            params["organization"] = self._organization_uri
        elif self._user_uri:
            params["user"] = self._user_uri

        async with httpx.AsyncClient() as client:
            await self._rate_limit()
            resp = await self._request_with_429_retry(
                client, "get", url, headers=self._headers(), params=params
            )
            if resp.status_code == 401:
                self.logger.warning(
                    "⚠️ Got 401 when listing event types, refreshing token..."
                )
                await self._refresh_token()
                resp = await self._request_with_429_retry(
                    client, "get", url, headers=self._headers(), params=params
                )
            resp.raise_for_status()
            data = resp.json()
            collection = data.get("collection", [])

        if not collection:
            raise ValueError(
                "No event types found in Calendly. Ensure exactly one active "
                "event type exists in your account before running the Monke test."
            )

        resource = collection[0]
        event_type_uri = resource.get("uri", "").strip()
        if not event_type_uri:
            raise ValueError("First event type from Calendly API has no URI.")
        event_type_uuid = event_type_uri.split("/")[-1]
        name = (resource.get("name") or "").strip() or "Unnamed Event Type"
        slug = (resource.get("slug") or "").strip()
        token = name if name != "Unnamed Event Type" else (slug or event_type_uuid)

        entity = {
            "type": "event_type",
            "id": event_type_uuid,
            "uri": event_type_uri,
            "name": name,
            "token": token,
            "expected_content": token,
            "path": f"calendly/event_type/{event_type_uuid}",
        }
        entities.append(entity)
        self._event_types.append(entity)
        self.created_entities = entities

        self.logger.info(
            f"✅ Fetched 1 existing event type: id={event_type_uuid}, name={name!r}, token={token!r}"
        )
        return entities

    async def update_entities(self) -> List[Dict[str, Any]]:
        """Update event types in Calendly."""
        self.logger.info("🥁 Updating Calendly event types")
        updated: List[Dict[str, Any]] = []

        if not self._event_types:
            return updated

        from monke.generation.calendly import generate_calendly_event_type

        async with httpx.AsyncClient() as client:
            # Update first few event types
            events_to_update = self._event_types[: min(3, len(self._event_types))]

            for event_info in events_to_update:
                try:
                    await self._rate_limit()
                    token = event_info.get("token") or str(uuid.uuid4())[:8]
                    self.logger.info(
                        f"🔨 Generating update content with token: {token}"
                    )
                    (
                        name,
                        description,
                        duration_minutes,
                    ) = await generate_calendly_event_type(
                        self.openai_model, token, is_update=True
                    )
                    if token not in name:
                        name = f"{name} [{token}]"
                    if not name.strip().endswith(f"[{token}]"):
                        name = f"{name.strip()} [{token}]"

                    # Calendly API: name cannot be greater than 55 characters
                    if len(name) > CALENDLY_EVENT_TYPE_NAME_MAX_LENGTH:
                        suffix = f" [{token}]"
                        max_prefix = CALENDLY_EVENT_TYPE_NAME_MAX_LENGTH - len(suffix)
                        name = (name[:max_prefix].rstrip() + suffix)[
                            :CALENDLY_EVENT_TYPE_NAME_MAX_LENGTH
                        ]

                    event_type_uri = (
                        event_info.get("uri")
                        or f"{self.API_BASE}/event_types/{event_info['id']}"
                    )

                    # Update event type
                    put_json = {
                        "name": name,
                        "duration": duration_minutes,
                        "description_plain": description,
                        "active": True,
                    }
                    resp = await self._request_with_429_retry(
                        client,
                        "put",
                        event_type_uri,
                        headers=self._headers(),
                        json=put_json,
                    )

                    # Handle 401 by refreshing token and retrying
                    if resp.status_code == 401:
                        self.logger.warning(
                            "⚠️ Got 401 when updating event type, refreshing token..."
                        )
                        await self._refresh_token()
                        resp = await self._request_with_429_retry(
                            client,
                            "put",
                            event_type_uri,
                            headers=self._headers(),
                            json=put_json,
                        )

                    resp.raise_for_status()

                    updated.append(
                        {
                            "type": "event_type",
                            "id": event_info["id"],
                            "uri": event_type_uri,
                            "name": name,
                            "token": token,
                            "expected_content": token,
                            "updated": True,
                            "path": event_info.get(
                                "path", f"calendly/event_type/{event_info['id']}"
                            ),
                        }
                    )
                    self.logger.info(f"📝 Updated event type: {event_info['id']}")

                except Exception as e:
                    self.logger.error(
                        f"Failed to update event type {event_info['id']}: {e}"
                    )
                    raise  # Halt on any error in Calendly monke

        return updated

    async def delete_entities(self) -> List[str]:
        """Do not delete event types; we use a pre-existing one and leave it as-is."""
        self.logger.info(
            "🥁 Skipping deletion (Calendly monke uses one existing event type, no delete)"
        )
        return []

    async def delete_specific_entities(
        self, entities: List[Dict[str, Any]]
    ) -> List[str]:
        """Do not delete event types; we use a pre-existing one and leave it as-is."""
        self.logger.info(
            f"🥁 Skipping deletion of {len(entities)} event type(s) (using existing event type only)"
        )
        return []

    async def cleanup(self):
        """Clear tracking state only; do not delete the pre-existing event type."""
        self.logger.info(
            "🧹 Calendly cleanup: clearing state (pre-existing event type is left unchanged)"
        )
        self._event_types = []
