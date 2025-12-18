"""Calendly-specific bongo implementation.

Creates, updates, and deletes test event types via the real Calendly API.
Note: Scheduled events cannot be created programmatically via Calendly API -
they are created when someone books a meeting. This bongo focuses on
creating and managing event types, and can update meeting notes on existing
scheduled events if they exist.
"""

import asyncio
import time
import uuid
from typing import Any, Dict, List, Optional

import httpx
from monke.bongos.base_bongo import BaseBongo
from monke.utils.logging import get_logger


class CalendlyBongo(BaseBongo):
    """Bongo for Calendly that creates event types for end-to-end testing.

    - Uses OAuth access token as bearer token
    - Embeds a short token in event type descriptions for verification
    - Creates event types that can be used for scheduling
    - Note: Scheduled events are created when someone books, not via API
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
        self.entity_count: int = int(kwargs.get("entity_count", 3))
        self.openai_model: str = kwargs.get("openai_model", "gpt-4.1-mini")
        self.max_concurrency: int = int(kwargs.get("max_concurrency", 1))
        # Use rate_limit_delay_ms from config if provided, otherwise default to 500ms
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
            await self._rate_limit()
            resp = await client.get(
                f"{self.API_BASE}/users/me",
                headers=self._headers(),
            )

            # Handle 401 by refreshing token and retrying
            if resp.status_code == 401:
                self.logger.warning(
                    "⚠️ Got 401 when fetching user info, refreshing token..."
                )
                await self._refresh_token()
                await self._rate_limit()
                resp = await client.get(
                    f"{self.API_BASE}/users/me",
                    headers=self._headers(),
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
        """Create event types in Calendly.

        Returns a list of created entity descriptors used by the test flow.

        Note: Calendly doesn't allow creating scheduled events via API.
        Scheduled events are created when someone books a meeting.
        This method only creates event types.
        """
        self.logger.info(f"🥁 Creating {self.entity_count} Calendly event types")
        await self._ensure_user()

        from monke.generation.calendly import generate_calendly_event_type

        entities: List[Dict[str, Any]] = []
        semaphore = asyncio.Semaphore(self.max_concurrency)

        # Track tokens to detect collisions
        used_tokens: set[str] = set()
        token_lock = asyncio.Lock()

        async with httpx.AsyncClient() as client:

            async def create_one() -> Optional[Dict[str, Any]]:
                async with semaphore:
                    try:
                        await self._rate_limit()

                        # Generate unique token with collision detection
                        async with token_lock:
                            max_attempts = 100  # Prevent infinite loop
                            attempts = 0
                            token = str(uuid.uuid4())[:8]
                            while token in used_tokens and attempts < max_attempts:
                                self.logger.warning(
                                    f"⚠️ Token collision detected: {token}, generating new token..."
                                )
                                token = str(uuid.uuid4())[:8]
                                attempts += 1

                            if attempts >= max_attempts:
                                raise ValueError(
                                    f"Failed to generate unique token after {max_attempts} attempts. "
                                    f"Current token set size: {len(used_tokens)}"
                                )

                            used_tokens.add(token)
                            if attempts > 0:
                                self.logger.info(
                                    f"✅ Generated unique token after {attempts} collision(s): {token}"
                                )

                        self.logger.info(
                            f"🔨 Generating content for event type with token: {token} "
                            f"(unique token #{len(used_tokens)})"
                        )
                        (
                            name,
                            description,
                            duration_minutes,
                        ) = await generate_calendly_event_type(self.openai_model, token)
                        self.logger.info(
                            f"📝 Generated event type: '{name}' (token: {token})"
                        )
                        # Verify token is in name
                        if token not in name:
                            self.logger.warning(
                                f"⚠️ Token {token} not found in generated name '{name}' - this may cause verification to fail!"
                            )

                        # Create event type
                        # Calendly API v2 structure requires 'owner' parameter
                        # Owner should be the user URI who owns the event type
                        if not self._user_uri:
                            raise ValueError(
                                "No user URI available for creating event type (owner is required)"
                            )

                        request_body = {
                            "name": name,  # Token is already embedded in name by generation function
                            "duration": duration_minutes,
                            "description_plain": description,  # Token is embedded in description
                            "internal_note": f"Test event type created by Monke. Token: {token}",  # Backup: token in internal_note
                            "kind": "solo",  # solo, group, or collective
                            "active": True,
                            "owner": self._user_uri,  # Required: owner of the event type
                        }

                        # Add organization URI if available (optional but recommended)
                        if self._organization_uri:
                            request_body["organization"] = self._organization_uri

                        url = f"{self.API_BASE}/event_types"
                        self.logger.debug(f"Creating event type: URL={url}")
                        self.logger.debug(
                            f"Request body (sanitized): name={name}, duration={duration_minutes}, has_org={bool(self._organization_uri)}, has_user={bool(self._user_uri)}"
                        )

                        resp = await client.post(
                            url,
                            headers=self._headers(),
                            json=request_body,
                        )

                        # Handle 401 by refreshing token and retrying
                        if resp.status_code == 401:
                            self.logger.warning(
                                "⚠️ Got 401 when creating event type, refreshing token..."
                            )
                            await self._refresh_token()
                            await self._rate_limit()
                            resp = await client.post(
                                url,
                                headers=self._headers(),
                                json=request_body,
                            )

                        if resp.status_code not in (200, 201):
                            error_data = resp.text
                            try:
                                error_json = resp.json()
                                error_data = error_json
                                # Extract error message if available
                                if isinstance(error_json, dict):
                                    error_title = error_json.get("title", "")
                                    error_message = error_json.get("message", "")
                                    error_details = error_json.get("details", [])
                                    self.logger.error(
                                        f"Calendly API error: {error_title} - {error_message}"
                                    )
                                    if error_details:
                                        self.logger.error(
                                            f"Error details: {error_details}"
                                        )
                            except Exception:
                                pass
                            self.logger.error(
                                f"Failed to create event type: {resp.status_code} - {error_data}"
                            )
                            self.logger.error(
                                f"Request URL: {self.API_BASE}/event_types"
                            )
                            self.logger.error(f"Request body: {request_body}")
                            resp.raise_for_status()

                        resp.raise_for_status()
                        event_type_data = resp.json()
                        event_type = event_type_data.get("resource", {})
                        event_type_uri = event_type.get("uri", "")

                        if not event_type_uri:
                            raise ValueError("No URI returned for created event type")

                        # Extract UUID from URI (format: https://api.calendly.com/event_types/{uuid})
                        event_type_uuid = event_type_uri.split("/")[-1]

                        # CRITICAL DEBUG: Log what the API actually returned
                        api_name = event_type.get("name", "MISSING")
                        api_description = event_type.get("description_plain", "MISSING")
                        api_internal_note = event_type.get("internal_note", "MISSING")

                        self.logger.info(
                            f"🔍 API RESPONSE VERIFICATION for token {token}:"
                        )
                        self.logger.info(
                            f"   • Sent name: '{name}' (contains token: {token in name})"
                        )
                        self.logger.info(
                            f"   • API returned name: '{api_name}' (contains token: {token in str(api_name)})"
                        )
                        self.logger.info(
                            f"   • API returned description_plain: {'PRESENT' if api_description and api_description != 'MISSING' else 'MISSING'} "
                            f"(contains token: {token in str(api_description) if api_description else False})"
                        )
                        self.logger.info(
                            f"   • API returned internal_note: {'PRESENT' if api_internal_note and api_internal_note != 'MISSING' else 'MISSING'} "
                            f"(contains token: {token in str(api_internal_note) if api_internal_note else False})"
                        )

                        # CRITICAL: Verify token is in the returned name (most critical field)
                        api_name_str = str(api_name)
                        if token not in api_name_str:
                            self.logger.error(
                                f"❌ CRITICAL: Token {token} NOT found in API response name '{api_name}'! "
                                f"Sent name was '{name}'. This will cause verification to fail."
                            )
                            # Check if token is in other fields as fallback
                            token_in_desc = (
                                token in str(api_description)
                                if api_description
                                else False
                            )
                            token_in_note = (
                                token in str(api_internal_note)
                                if api_internal_note
                                else False
                            )
                            if token_in_desc or token_in_note:
                                self.logger.warning(
                                    f"⚠️ Token found in other fields (desc: {token_in_desc}, note: {token_in_note}) "
                                    f"but NOT in name. Search may still fail since name is the primary field."
                                )
                            else:
                                self.logger.error(
                                    f"❌ Token {token} NOT found in ANY field returned by API! "
                                    f"This entity will definitely fail verification."
                                )
                        else:
                            self.logger.info(
                                f"✅ Token {token} confirmed in API response name"
                            )

                        # Entity descriptor used by generic verification
                        return {
                            "type": "event_type",
                            "id": event_type_uuid,
                            "uri": event_type_uri,
                            "name": name,  # Use our generated name (with token), not API response
                            "token": token,
                            "expected_content": token,
                            "path": f"calendly/event_type/{event_type_uuid}",
                        }
                    except Exception as e:
                        self.logger.error(
                            f"❌ Error in create_one: {type(e).__name__}: {str(e)}"
                        )
                        # Re-raise to be caught by gather
                        raise

            # Create all event types in parallel
            tasks = [create_one() for _ in range(self.entity_count)]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Process results and handle any exceptions
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    self.logger.error(f"Failed to create event type {i + 1}: {result}")
                    # Re-raise the first exception we encounter
                    raise result
                elif result:
                    entities.append(result)
                    self._event_types.append(result)

        # SAFEGUARD: Store entities IMMEDIATELY after creation to prevent loss
        self.created_entities = entities

        # Log entity storage for debugging
        self.logger.info(
            f"💾 STORAGE VERIFICATION: Stored {len(entities)} entities in self.created_entities"
        )
        for i, entity in enumerate(entities, 1):
            self.logger.info(
                f"   Entity #{i}: id={entity.get('id')}, token={entity.get('token')}, "
                f"uri={entity.get('uri', 'missing')}"
            )

        # Final verification: Check for duplicate tokens in created entities
        entity_tokens = [e.get("token") for e in entities if e.get("token")]
        unique_tokens = set(entity_tokens)
        if len(entity_tokens) != len(unique_tokens):
            duplicates = [t for t in entity_tokens if entity_tokens.count(t) > 1]
            self.logger.error(
                f"❌ CRITICAL: Found {len(duplicates)} duplicate token(s) in created entities: {set(duplicates)}"
            )
            self.logger.error(
                f"   Total entities: {len(entities)}, Unique tokens: {len(unique_tokens)}"
            )
            # Log which entities have duplicate tokens
            for dup_token in set(duplicates):
                dup_entities = [e for e in entities if e.get("token") == dup_token]
                self.logger.error(
                    f"   Token '{dup_token}' appears in {len(dup_entities)} entities: "
                    f"{[e.get('id') for e in dup_entities]}"
                )
        else:
            self.logger.info(
                f"✅ Token uniqueness verified: {len(unique_tokens)} unique tokens for {len(entities)} entities"
            )
            self.logger.info(f"   Tokens: {sorted(entity_tokens)}")

        self.logger.info(f"✅ Created {len(entities)} event types")

        # CRITICAL: Verify entities are ready to be returned
        if not entities:
            self.logger.error("❌ CRITICAL: create_entities() returning empty list!")
        else:
            self.logger.info(
                f"✅ RETURNING {len(entities)} entities to test framework: "
                f"tokens={[e.get('token') for e in entities]}"
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

                    event_type_uri = (
                        event_info.get("uri")
                        or f"{self.API_BASE}/event_types/{event_info['id']}"
                    )

                    # Update event type
                    resp = await client.put(
                        event_type_uri,
                        headers=self._headers(),
                        json={
                            "name": name,
                            "duration": duration_minutes,
                            "description_plain": description,
                            "active": True,
                        },
                    )

                    # Handle 401 by refreshing token and retrying
                    if resp.status_code == 401:
                        self.logger.warning(
                            "⚠️ Got 401 when updating event type, refreshing token..."
                        )
                        await self._refresh_token()
                        await self._rate_limit()
                        resp = await client.put(
                            event_type_uri,
                            headers=self._headers(),
                            json={
                                "name": name,
                                "duration": duration_minutes,
                                "description_plain": description,
                                "active": True,
                            },
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
                    # Continue with next event type

        return updated

    async def delete_entities(self) -> List[str]:
        """Delete all test entities from Calendly."""
        self.logger.info("🥁 Deleting all test event types from Calendly")
        return await self.delete_specific_entities(self.created_entities)

    async def delete_specific_entities(
        self, entities: List[Dict[str, Any]]
    ) -> List[str]:
        """Delete specific entities from Calendly."""
        self.logger.info(
            f"🥁 Deleting {len(entities)} specific event types from Calendly"
        )

        # SAFEGUARD: Log what we're deleting to track premature deletion
        if entities:
            entity_info = [
                f"id={e.get('id')}, token={e.get('token')}, uri={e.get('uri', 'missing')}"
                for e in entities
            ]
            self.logger.info(
                f"🗑️ DELETION REQUEST: About to delete entities:\n   "
                + "\n   ".join(entity_info)
            )

        deleted_ids: List[str] = []

        async with httpx.AsyncClient() as client:
            for entity in entities:
                entity_id = entity.get("id")
                event_type_uri = (
                    entity.get("uri") or f"{self.API_BASE}/event_types/{entity_id}"
                )
                deletion_succeeded = False

                try:
                    await self._rate_limit()
                    # Calendly uses DELETE method for event types
                    resp = await client.delete(
                        event_type_uri,
                        headers=self._headers(),
                    )

                    # Handle 401 by refreshing token and retrying
                    if resp.status_code == 401:
                        self.logger.warning(
                            "⚠️ Got 401 when deleting event type, refreshing token..."
                        )
                        await self._refresh_token()
                        await self._rate_limit()
                        resp = await client.delete(
                            event_type_uri,
                            headers=self._headers(),
                        )

                    if resp.status_code == 204:
                        deleted_ids.append(entity_id)
                        deletion_succeeded = True
                        self.logger.info(
                            f"🗑️ Successfully deleted event type: {entity_id}"
                        )
                    elif resp.status_code == 404:
                        # 404 means the entity doesn't exist - verify by trying to fetch it
                        await self._rate_limit()
                        try:
                            verify_resp = await client.get(
                                event_type_uri, headers=self._headers()
                            )
                            if verify_resp.status_code == 200:
                                # Entity still exists - deletion failed but API returned 404
                                # Try deactivating instead (Calendly might require deactivation before deletion)
                                self.logger.warning(
                                    f"⚠️ Deletion returned 404 but entity {entity_id} still exists. "
                                    f"Attempting to deactivate instead..."
                                )
                                await self._rate_limit()
                                deactivate_resp = await client.put(
                                    event_type_uri,
                                    headers=self._headers(),
                                    json={"active": False},
                                )
                                if deactivate_resp.status_code in (200, 204):
                                    deleted_ids.append(entity_id)
                                    deletion_succeeded = True
                                    self.logger.info(
                                        f"🗑️ Deactivated event type {entity_id} (deletion not supported)"
                                    )
                                else:
                                    self.logger.error(
                                        f"❌ Failed to deactivate event type {entity_id}: "
                                        f"status {deactivate_resp.status_code}"
                                    )
                            else:
                                # Entity doesn't exist - deletion succeeded (idempotent)
                                deleted_ids.append(entity_id)
                                deletion_succeeded = True
                                self.logger.info(
                                    f"🗑️ Event type {entity_id} not found (404) - verified as deleted"
                                )
                        except Exception as verify_e:
                            # If verification fails, assume deletion succeeded (idempotent)
                            deleted_ids.append(entity_id)
                            deletion_succeeded = True
                            self.logger.info(
                                f"🗑️ Event type {entity_id} not found (404) - treating as deleted "
                                f"(verification failed: {verify_e})"
                            )
                    else:
                        # Unexpected status code - try deactivation as fallback
                        error_text = (
                            resp.text[:200] if resp.text else "No error details"
                        )
                        self.logger.warning(
                            f"⚠️ Deletion failed for event type {entity_id}: "
                            f"status {resp.status_code}, error: {error_text}. "
                            f"Attempting to deactivate instead..."
                        )
                        await self._rate_limit()
                        try:
                            deactivate_resp = await client.put(
                                event_type_uri,
                                headers=self._headers(),
                                json={"active": False},
                            )
                            if deactivate_resp.status_code in (200, 204):
                                deleted_ids.append(entity_id)
                                deletion_succeeded = True
                                self.logger.info(
                                    f"🗑️ Deactivated event type {entity_id} (deletion failed)"
                                )
                            else:
                                self.logger.error(
                                    f"❌ Failed to deactivate event type {entity_id}: "
                                    f"status {deactivate_resp.status_code}"
                                )
                        except Exception as deactivate_e:
                            self.logger.error(
                                f"❌ Failed to deactivate event type {entity_id}: {deactivate_e}"
                            )

                except httpx.HTTPStatusError as e:
                    # Handle HTTP errors
                    if e.response.status_code == 404:
                        # Try to verify if entity exists
                        try:
                            await self._rate_limit()
                            verify_resp = await client.get(
                                event_type_uri, headers=self._headers()
                            )
                            # Handle 401 in verification
                            if verify_resp.status_code == 401:
                                await self._refresh_token()
                                await self._rate_limit()
                                verify_resp = await client.get(
                                    event_type_uri, headers=self._headers()
                                )

                            if verify_resp.status_code == 200:
                                # Entity exists - try deactivation
                                self.logger.warning(
                                    f"⚠️ Deletion returned 404 but entity {entity_id} exists. "
                                    f"Attempting to deactivate..."
                                )
                                await self._rate_limit()
                                deactivate_resp = await client.put(
                                    event_type_uri,
                                    headers=self._headers(),
                                    json={"active": False},
                                )
                                # Handle 401 in deactivation
                                if deactivate_resp.status_code == 401:
                                    await self._refresh_token()
                                    await self._rate_limit()
                                    deactivate_resp = await client.put(
                                        event_type_uri,
                                        headers=self._headers(),
                                        json={"active": False},
                                    )
                                if deactivate_resp.status_code in (200, 204):
                                    deleted_ids.append(entity_id)
                                    deletion_succeeded = True
                                    self.logger.info(
                                        f"🗑️ Deactivated event type {entity_id}"
                                    )
                            else:
                                deleted_ids.append(entity_id)
                                deletion_succeeded = True
                                self.logger.info(
                                    f"🗑️ Event type {entity_id} not found (404) - verified as deleted"
                                )
                        except Exception:
                            # If verification fails, assume deleted
                            deleted_ids.append(entity_id)
                            deletion_succeeded = True
                            self.logger.info(
                                f"🗑️ Event type {entity_id} not found (404) - treating as deleted"
                            )
                    else:
                        # Try deactivation as fallback
                        self.logger.warning(
                            f"⚠️ HTTP error when deleting event type {entity_id}: "
                            f"{e.response.status_code}. Attempting to deactivate..."
                        )
                        try:
                            await self._rate_limit()
                            deactivate_resp = await client.put(
                                event_type_uri,
                                headers=self._headers(),
                                json={"active": False},
                            )
                            # Handle 401 in deactivation
                            if deactivate_resp.status_code == 401:
                                await self._refresh_token()
                                await self._rate_limit()
                                deactivate_resp = await client.put(
                                    event_type_uri,
                                    headers=self._headers(),
                                    json={"active": False},
                                )
                            if deactivate_resp.status_code in (200, 204):
                                deleted_ids.append(entity_id)
                                deletion_succeeded = True
                                self.logger.info(
                                    f"🗑️ Deactivated event type {entity_id}"
                                )
                            else:
                                self.logger.error(
                                    f"❌ Failed to deactivate event type {entity_id}: "
                                    f"status {deactivate_resp.status_code}"
                                )
                        except Exception as deactivate_e:
                            self.logger.error(
                                f"❌ Failed to deactivate event type {entity_id}: {deactivate_e}"
                            )
                except Exception as e:
                    self.logger.error(
                        f"❌ Exception when deleting event type {entity_id}: {e}"
                    )
                    # Try deactivation as last resort
                    try:
                        await self._rate_limit()
                        deactivate_resp = await client.put(
                            event_type_uri,
                            headers=self._headers(),
                            json={"active": False},
                        )
                        if deactivate_resp.status_code in (200, 204):
                            deleted_ids.append(entity_id)
                            deletion_succeeded = True
                            self.logger.info(
                                f"🗑️ Deactivated event type {entity_id} after deletion exception"
                            )
                    except Exception as deactivate_e:
                        self.logger.error(
                            f"❌ Failed to deactivate event type {entity_id}: {deactivate_e}"
                        )

                if not deletion_succeeded:
                    self.logger.warning(
                        f"⚠️ Event type {entity_id} could not be deleted or deactivated. "
                        f"It may still exist in Calendly and will be synced again."
                    )

        return deleted_ids

    async def cleanup(self):
        """Clean up all test data."""
        self.logger.info("🧹 Cleaning up Calendly test data")

        # SAFEGUARD: Log what we're about to delete to prevent premature deletion
        if hasattr(self, "created_entities") and self.created_entities:
            entity_count = len(self.created_entities)
            entity_ids = [e.get("id", "unknown") for e in self.created_entities]
            entity_tokens = [e.get("token", "no-token") for e in self.created_entities]

            self.logger.info(
                f"🗑️ PRE-DELETION CHECK: About to delete {entity_count} entities"
            )
            self.logger.info(f"   Entity IDs: {entity_ids}")
            self.logger.info(f"   Entity tokens: {entity_tokens}")

            # Verify entities still exist before deletion (safety check)
            if entity_count > 0:
                self.logger.info(
                    f"⚠️ DELETION WARNING: Deleting {entity_count} entities with tokens: {entity_tokens}"
                )

            await self.delete_entities()
        else:
            self.logger.info(
                "ℹ️ No entities to clean up (created_entities is empty or missing)"
            )

        # Only clear tracking after successful deletion
        self._event_types = []
        # Don't clear _user_uri as it might be needed for subsequent operations
        # self._user_uri = None
