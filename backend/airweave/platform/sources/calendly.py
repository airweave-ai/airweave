"""Calendly source implementation for syncing event types, scheduled events, and invitees."""

from typing import Any, AsyncGenerator, Dict, List, Optional

import httpx
from tenacity import retry, stop_after_attempt

from airweave.core.exceptions import TokenRefreshError
from airweave.core.shared_models import RateLimitLevel
from airweave.platform.decorators import source
from airweave.platform.entities._base import BaseEntity, Breadcrumb
from airweave.platform.entities.calendly import (
    CalendlyEventInviteeEntity,
    CalendlyEventTypeEntity,
    CalendlyScheduledEventEntity,
    CalendlyUserEntity,
)
from airweave.platform.sources._base import BaseSource
from airweave.platform.sources.retry_helpers import (
    retry_if_rate_limit_or_timeout,
    wait_rate_limit_with_backoff,
)
from airweave.schemas.source_connection import AuthenticationMethod, OAuthType


@source(
    name="Calendly",
    short_name="calendly",
    auth_methods=[
        AuthenticationMethod.OAUTH_BROWSER,
        AuthenticationMethod.OAUTH_TOKEN,
        AuthenticationMethod.AUTH_PROVIDER,
    ],
    oauth_type=OAuthType.WITH_REFRESH,
    auth_config_class=None,
    config_class="CalendlyConfig",
    labels=["Productivity", "Calendar"],
    supports_continuous=False,
    rate_limit_level=RateLimitLevel.ORG,
)
class CalendlySource(BaseSource):
    """Calendly source connector integrates with the Calendly API to extract and synchronize data.

    Connects to your Calendly account.

    It supports syncing event types, scheduled events, and event invitees.
    """

    BASE_URL = "https://api.calendly.com"

    @classmethod
    async def create(
        cls, access_token: str, config: Optional[Dict[str, Any]] = None
    ) -> "CalendlySource":
        """Create a new Calendly source.

        Args:
            access_token: OAuth access token for Calendly API
            config: Optional configuration parameters

        Returns:
            Configured CalendlySource instance
        """
        instance = cls()
        instance.access_token = access_token

        # Store config values as instance attributes
        if config:
            # No specific config needed for now, but can be extended
            pass

        return instance

    @retry(
        stop=stop_after_attempt(5),
        retry=retry_if_rate_limit_or_timeout,
        wait=wait_rate_limit_with_backoff,
        reraise=True,
    )
    async def _get_with_auth(
        self, client: httpx.AsyncClient, url: str, params: Optional[Dict[str, Any]] = None
    ) -> Dict:
        """Make authenticated GET request to Calendly API with retry logic.

        Retries on:
        - 429 rate limits (respects Retry-After header)
        - Timeout errors (exponential backoff)

        Max 5 attempts with intelligent wait strategy.

        Args:
            client: HTTP client to use for the request
            url: API endpoint URL
            params: Optional query parameters
        """
        # Get a valid token (will refresh if needed)
        access_token = await self.get_access_token()
        if not access_token:
            raise ValueError("No access token available")

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }

        try:
            response = await client.get(url, headers=headers, params=params)

            # Handle 401 Unauthorized - token might have expired
            if response.status_code == 401:
                self.logger.warning(f"Received 401 Unauthorized for {url}, refreshing token...")

                # If we have a token manager, try to refresh
                if self.token_manager:
                    try:
                        # Force refresh the token
                        new_token = await self.token_manager.refresh_on_unauthorized()
                        headers = {"Authorization": f"Bearer {new_token}"}

                        # Retry the request with the new token
                        self.logger.debug(f"Retrying request with refreshed token: {url}")
                        response = await client.get(url, headers=headers, params=params)

                    except TokenRefreshError as e:
                        self.logger.error(f"Failed to refresh token: {str(e)}")
                        response.raise_for_status()
                else:
                    # No token manager, can't refresh
                    self.logger.error("No token manager available to refresh expired token")
                    response.raise_for_status()

            # Raise for other HTTP errors
            response.raise_for_status()
            return response.json()

        except httpx.HTTPStatusError as e:
            self.logger.error(f"HTTP error from Calendly API: {e.response.status_code} for {url}")
            raise
        except Exception as e:
            self.logger.error(f"Unexpected error accessing Calendly API: {url}, {str(e)}")
            raise

    async def _get_paginated(
        self,
        client: httpx.AsyncClient,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        collection_key: str = "collection",
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Get paginated results from Calendly API.

        Calendly uses cursor-based pagination with `count` and `page_token` parameters.

        Args:
            client: HTTP client
            url: API endpoint URL
            params: Optional query parameters
            collection_key: Key in response JSON that contains the collection array

        Yields:
            Individual items from paginated results
        """
        params = params or {}
        params.setdefault("count", 100)  # Max page size for Calendly

        page_token = None
        while True:
            if page_token:
                params["page_token"] = page_token
            else:
                # Remove page_token if it exists and we're starting fresh
                params.pop("page_token", None)

            response_data = await self._get_with_auth(client, url, params)

            # Extract collection from response
            collection = response_data.get(collection_key, [])
            for item in collection:
                yield item

            # Check for pagination
            pagination = response_data.get("pagination", {})
            next_page_token = pagination.get("next_page_token")

            if not next_page_token:
                break

            page_token = next_page_token

    async def _generate_event_type_entities(
        self, client: httpx.AsyncClient
    ) -> AsyncGenerator[CalendlyEventTypeEntity, None]:
        """Generate event type entities."""
        self.logger.error("_generate_event_type_entities() CALLED")
        self.logger.info("Starting event type entity generation from Calendly API")
        url = f"{self.BASE_URL}/event_types"

        # Get user info to use proper URI (Calendly API doesn't accept "me" as user parameter)
        try:
            user_response = await self._get_with_auth(client, f"{self.BASE_URL}/users/me")
            user_resource = user_response.get("resource", {})
            user_uri = user_resource.get("uri")
            organization_uri = user_resource.get("current_organization")

            # Calendly API accepts either user URI or organization URI (full URI, not just UUID)
            # Prefer organization if available, otherwise use user URI
            params = {}
            if organization_uri:
                # Use full organization URI (not just UUID)
                params["organization"] = organization_uri
            elif user_uri:
                # Use full user URI (not just UUID)
                params["user"] = user_uri
            # If neither available, don't filter (get all accessible event types)
        except Exception as e:
            self.logger.warning(f"Failed to get user info for event type filtering: {e}")
            # Continue without filter - will get all accessible event types
            params = {}

        entity_yield_count = 0
        entity_skip_count = 0

        async for event_type_data in self._get_paginated(client, url, params):
            # event_type_data IS the resource data (not wrapped in a "resource" key)
            # _get_paginated already extracts items from the "collection" array
            resource = event_type_data

            if not resource:
                entity_skip_count += 1
                self.logger.error(
                    f"SKIPPING event type: empty resource data. "
                    f"event_type_data: {str(event_type_data)[:200]}"
                )
                continue

            event_type_uri = resource.get("uri", "")
            if not event_type_uri:
                entity_skip_count += 1
                self.logger.error(
                    f"SKIPPING event type: no URI. "
                    f"resource keys: {list(resource.keys())}, "
                    f"resource: {str(resource)[:200]}"
                )
                continue

            # Always fetch full event type details to ensure we get description_plain
            # The list endpoint might not return all fields, especially description
            try:
                # Extract UUID from URI (format: https://api.calendly.com/event_types/{uuid})
                event_type_uuid = event_type_uri.split("/")[-1]
                detail_url = f"{self.BASE_URL}/event_types/{event_type_uuid}"
                detail_response = await self._get_with_auth(client, detail_url)
                detail_resource = detail_response.get("resource", {})
                # Use detail resource data (it has all fields including description_plain)
                if detail_resource:
                    resource = detail_resource
                    # Log if description is missing (for debugging)
                    if not resource.get("description_plain"):
                        self.logger.debug(
                            f"Event type {event_type_uuid} has no description_plain field"
                        )
                else:
                    self.logger.warning(
                        f"No resource data in detail response for event type {event_type_uri}"
                    )
            except Exception as e:
                self.logger.warning(
                    f"Failed to fetch full details for event type {event_type_uri}: {e}, using list data"
                )
                # Continue with partial data from list

            # Skip inactive event types (they were deactivated, not deleted)
            # Calendly doesn't support deletion, only deactivation
            # Deactivated event types should not be synced to Qdrant
            active = resource.get("active", True)
            if not active:
                entity_skip_count += 1
                self.logger.debug(f"Skipping inactive event type: {event_type_uri} (active=False)")
                continue

            # Extract fields - ensure name is never empty (required field)
            name = resource.get("name") or "Unnamed Event Type"
            description_plain = resource.get("description_plain")
            internal_note = resource.get("internal_note")

            # CRITICAL: Check for tokens in extracted data (for ALL entities, not just first few)
            import re

            event_type_uuid = event_type_uri.split("/")[-1]
            name_tokens = re.findall(r"\b[a-f0-9]{8}\b", name, re.IGNORECASE)
            desc_tokens = re.findall(r"\b[a-f0-9]{8}\b", description_plain or "", re.IGNORECASE)
            note_tokens = re.findall(r"\b[a-f0-9]{8}\b", internal_note or "", re.IGNORECASE)
            all_tokens = set(name_tokens + desc_tokens + note_tokens)

            # Log first few entities with full details
            if not hasattr(self, "_logged_entities"):
                self._logged_entities = 0

            if self._logged_entities < 5:
                self.logger.info(f"EXTRACTING event type {event_type_uuid}:")
                self.logger.info(
                    f"   • Name: '{name[:80]}...' "
                    f"(length: {len(name)}, tokens found: {name_tokens})"
                )
                self.logger.info(
                    f"   • Description: {'PRESENT' if description_plain else 'MISSING'} "
                    f"(length: {len(description_plain) if description_plain else 0}, tokens: {desc_tokens})"
                )
                self.logger.info(
                    f"   • Internal note: {'PRESENT' if internal_note else 'MISSING'} "
                    f"(length: {len(internal_note) if internal_note else 0}, tokens: {note_tokens})"
                )
                self.logger.info(
                    f"   • ALL TOKENS FOUND: {sorted(all_tokens) if all_tokens else 'NONE'}"
                )
                self._logged_entities += 1

            # CRITICAL WARNING: If no tokens found in any embeddable field, this entity won't be verifiable
            if not all_tokens:
                self.logger.error(
                    f"CRITICAL: Event type {event_type_uuid} has NO TOKENS in any embeddable field! "
                    f"This entity will NOT be searchable/verifiable. "
                    f"Name='{name[:50]}...', has_desc={bool(description_plain)}, has_note={bool(internal_note)}"
                )
            elif not name_tokens:
                # Token not in name (most critical field) - warn but continue
                self.logger.warning(
                    f"WARNING: Event type {event_type_uuid} has no token in NAME field "
                    f"(tokens found in other fields: {sorted(all_tokens)}). "
                    f"Name='{name[:50]}...'"
                )

            # CRITICAL: Before yielding, verify we have at least some embeddable content
            # If name is empty or default, and no description/note, entity won't be searchable
            has_embeddable_content = (
                (name and name != "Unnamed Event Type") or description_plain or internal_note
            )

            if not has_embeddable_content:
                self.logger.error(
                    f"CRITICAL: Event type {event_type_uuid} has NO embeddable content! "
                    f"Name='{name}', desc={bool(description_plain)}, note={bool(internal_note)}. "
                    f"This entity will NOT be searchable and will fail verification."
                )

            # Log entity being yielded for tracking
            entity_yield_count += 1
            self.logger.info(
                f"YIELDING entity #{entity_yield_count}: {event_type_uuid} "
                f"(name='{name[:40]}...', tokens_in_name={len(name_tokens)}, "
                f"all_tokens={sorted(all_tokens) if all_tokens else 'NONE'})"
            )

            yield CalendlyEventTypeEntity(
                uri=event_type_uri,
                name=name,  # This field is embeddable=True and is_name=True - tokens should be here
                active=resource.get("active", True),
                slug=resource.get("slug"),
                scheduling_url=resource.get("scheduling_url"),
                duration=resource.get("duration"),
                kind=resource.get("kind"),
                pooling_type=resource.get("pooling_type"),
                type=resource.get("type"),
                color=resource.get("color"),
                created_at=self._parse_datetime(resource.get("created_at")),
                updated_at=self._parse_datetime(resource.get("updated_at")),
                internal_note=internal_note,
                description_plain=description_plain,
                description_html=resource.get("description_html"),
                profile=resource.get("profile"),
                owner=resource.get("owner"),
                custom_questions=resource.get("custom_questions"),
                deleted_at=self._parse_datetime(resource.get("deleted_at")),
                breadcrumbs=[],  # Root entity
            )

        # Summary log after all entities processed
        self.logger.info(
            f"EVENT TYPE GENERATION SUMMARY: "
            f"yielded={entity_yield_count}, skipped={entity_skip_count}, "
            f"total_processed={entity_yield_count + entity_skip_count}"
        )

    async def _generate_scheduled_event_entities(
        self,
        client: httpx.AsyncClient,
        event_type_breadcrumb: Optional[Breadcrumb] = None,
    ) -> AsyncGenerator[CalendlyScheduledEventEntity, None]:
        """Generate scheduled event entities."""
        url = f"{self.BASE_URL}/scheduled_events"

        # Get user info to use proper URI (Calendly API doesn't accept "me" as user parameter)
        try:
            user_response = await self._get_with_auth(client, f"{self.BASE_URL}/users/me")
            user_resource = user_response.get("resource", {})
            user_uri = user_resource.get("uri")
            organization_uri = user_resource.get("current_organization")

            # Calendly API accepts either user URI or organization URI (full URI, not just UUID)
            # Prefer organization if available, otherwise use user URI
            params = {}
            if organization_uri:
                # Use full organization URI (not just UUID)
                params["organization"] = organization_uri
            elif user_uri:
                # Use full user URI (not just UUID)
                params["user"] = user_uri
            # If neither available, don't filter (get all accessible scheduled events)
        except Exception as e:
            self.logger.warning(f"Failed to get user info for scheduled event filtering: {e}")
            # Continue without filter - will get all accessible scheduled events
            params = {}

        async for event_data in self._get_paginated(client, url, params):
            # Extract nested resource data
            resource = event_data.get("resource", {})
            if not resource:
                continue

            # Get event type name if we have the URI
            event_type_uri = resource.get("event_type")
            event_type_name = None
            if event_type_uri:
                # Try to extract name from event type if available
                event_type_name = event_type_uri.split("/")[-1]

            breadcrumbs = []
            if event_type_breadcrumb:
                breadcrumbs = [event_type_breadcrumb]

            yield CalendlyScheduledEventEntity(
                uri=resource.get("uri", ""),
                name=resource.get("name", "Unnamed Event"),
                status=resource.get("status"),
                start_time=self._parse_datetime(resource.get("start_time")),
                end_time=self._parse_datetime(resource.get("end_time")),
                event_type=event_type_uri,
                event_type_name=event_type_name,
                location=resource.get("location"),
                invitees_counter=resource.get("invitees_counter"),
                created_at=self._parse_datetime(resource.get("created_at")),
                updated_at=self._parse_datetime(resource.get("updated_at")),
                canceled_at=self._parse_datetime(resource.get("canceled_at")),
                canceler_name=resource.get("canceler_name"),
                cancel_reason=resource.get("cancel_reason"),
                calendar_event=resource.get("calendar_event"),
                meeting_notes=resource.get("meeting_notes"),
                meeting_notes_plain=resource.get("meeting_notes_plain"),
                meeting_notes_html=resource.get("meeting_notes_html"),
                event_guests=resource.get("event_guests"),
                event_memberships=resource.get("event_memberships"),
                breadcrumbs=breadcrumbs,
            )

    async def _generate_event_invitee_entities(
        self,
        client: httpx.AsyncClient,
        scheduled_event: Dict[str, Any],
        event_breadcrumbs: List[Breadcrumb],
    ) -> AsyncGenerator[CalendlyEventInviteeEntity, None]:
        """Generate event invitee entities for a scheduled event."""
        event_uri = scheduled_event.get("uri", "")
        if not event_uri:
            return

        # Extract event UUID from URI (format: https://api.calendly.com/scheduled_events/{uuid})
        event_uuid = event_uri.split("/")[-1]
        if not event_uuid:
            return

        url = f"{self.BASE_URL}/scheduled_events/{event_uuid}/invitees"
        params = {}

        async for invitee_data in self._get_paginated(client, url, params):
            # Extract nested resource data
            resource = invitee_data.get("resource", {})
            if not resource:
                continue

            # Construct name from available fields
            name = (
                resource.get("name")
                or resource.get("name_field")
                or f"{resource.get('first_name', '')} {resource.get('last_name', '')}".strip()
                or resource.get("email", "Unknown Invitee")
            )

            yield CalendlyEventInviteeEntity(
                uri=resource.get("uri", ""),
                name=name,
                event=event_uri,
                event_name=scheduled_event.get("name"),
                email=resource.get("email"),
                first_name=resource.get("first_name"),
                last_name=resource.get("last_name"),
                name_field=resource.get("name"),
                status=resource.get("status"),
                text_reminder_number=resource.get("text_reminder_number"),
                timezone=resource.get("timezone"),
                created_at=self._parse_datetime(resource.get("created_at")),
                updated_at=self._parse_datetime(resource.get("updated_at")),
                canceled_at=self._parse_datetime(resource.get("canceled_at")),
                canceler_name=resource.get("canceler_name"),
                cancel_reason=resource.get("cancel_reason"),
                payment=resource.get("payment"),
                questions_and_answers=resource.get("questions_and_answers"),
                rescheduled=resource.get("rescheduled", False),
                old_invitee=resource.get("old_invitee"),
                new_invitee=resource.get("new_invitee"),
                tracking=resource.get("tracking"),
                breadcrumbs=event_breadcrumbs,
            )

    def _parse_datetime(self, value: Optional[str]) -> Optional[Any]:
        """Parse datetime string from Calendly API.

        Calendly uses ISO 8601 format with timezone.

        Args:
            value: Datetime string or None

        Returns:
            Parsed datetime or None
        """
        if not value:
            return None

        try:
            from datetime import datetime

            # Calendly uses ISO 8601 format: 2023-01-01T12:00:00.000000Z
            # Python's fromisoformat doesn't handle 'Z' directly, so replace it
            if value.endswith("Z"):
                value = value[:-1] + "+00:00"
            return datetime.fromisoformat(value)
        except (ValueError, AttributeError) as e:
            self.logger.warning(f"Failed to parse datetime '{value}': {e}")
            return None

    async def _generate_user_entity(
        self, client: httpx.AsyncClient
    ) -> Optional[CalendlyUserEntity]:
        """Generate user entity for the authenticated user."""
        try:
            response_data = await self._get_with_auth(client, f"{self.BASE_URL}/users/me")
            resource = response_data.get("resource", {})
            if not resource:
                return None

            return CalendlyUserEntity(
                uri=resource.get("uri", ""),
                name=resource.get("name", "Unknown User"),
                email=resource.get("email"),
                scheduling_url=resource.get("scheduling_url"),
                timezone=resource.get("timezone"),
                avatar_url=resource.get("avatar_url"),
                created_at=self._parse_datetime(resource.get("created_at")),
                updated_at=self._parse_datetime(resource.get("updated_at")),
                current_organization=resource.get("current_organization"),
                breadcrumbs=[],  # Root entity
            )
        except Exception as e:
            self.logger.warning(f"Failed to fetch user entity: {e}")
            return None

    async def generate_entities(self) -> AsyncGenerator[BaseEntity, None]:
        """Generate all entities from Calendly."""
        # CRITICAL: Log immediately, before any async operations
        self.logger.error("CALENDLY generate_entities() CALLED - THIS SHOULD APPEAR IN LOGS")
        self.logger.info("Starting Calendly entity generation pipeline")
        total_entities_yielded = 0

        try:
            self.logger.error("ABOUT TO CREATE HTTP CLIENT")
            async with self.http_client() as client:
                self.logger.error("HTTP CLIENT CREATED SUCCESSFULLY")
                # Generate user entity first
                try:
                    self.logger.error("ABOUT TO GENERATE USER ENTITY")
                    user_entity = await self._generate_user_entity(client)
                    if user_entity:
                        total_entities_yielded += 1
                        self.logger.info(f"YIELDED user entity: {user_entity.uri}")
                        yield user_entity
                    else:
                        self.logger.warning("No user entity generated")
                except Exception as e:
                    self.logger.error(f"Error generating user entity: {e}", exc_info=True)

                # Generate event types
                self.logger.error("ABOUT TO GENERATE EVENT TYPE ENTITIES")
                event_type_map = {}  # Map URI to name for breadcrumbs
                event_type_count = 0
                try:
                    async for event_type_entity in self._generate_event_type_entities(client):
                        event_type_count += 1
                        total_entities_yielded += 1
                        self.logger.info(
                            f"YIELDING event type #{event_type_count}: "
                            f"{event_type_entity.entity_id} (name: '{event_type_entity.name[:50]}...')"
                        )
                        yield event_type_entity
                        event_type_map[event_type_entity.uri] = event_type_entity.name

                    self.logger.info(
                        f"EVENT TYPES: {event_type_count} entities yielded from generate_entities()"
                    )
                except Exception as e:
                    self.logger.error(f"Error generating event type entities: {e}", exc_info=True)
                    # Continue to scheduled events even if event types fail

                # Generate scheduled events
                scheduled_event_count = 0
                try:
                    async for scheduled_event_entity in self._generate_scheduled_event_entities(
                        client
                    ):
                        scheduled_event_count += 1
                        total_entities_yielded += 1
                        yield scheduled_event_entity

                        # Create breadcrumb for the scheduled event
                        event_breadcrumb = Breadcrumb(
                            entity_id=scheduled_event_entity.uri,
                            name=scheduled_event_entity.name,
                            entity_type="CalendlyScheduledEventEntity",
                        )

                        # If we have event type info, add it to breadcrumbs
                        event_breadcrumbs = []
                        if scheduled_event_entity.event_type:
                            event_type_name = event_type_map.get(
                                scheduled_event_entity.event_type,
                                scheduled_event_entity.event_type_name or "Unknown Event Type",
                            )
                            event_type_breadcrumb = Breadcrumb(
                                entity_id=scheduled_event_entity.event_type,
                                name=event_type_name,
                                entity_type="CalendlyEventTypeEntity",
                            )
                            event_breadcrumbs = [event_type_breadcrumb, event_breadcrumb]
                        else:
                            event_breadcrumbs = [event_breadcrumb]

                        # Generate invitees for this scheduled event
                        scheduled_event_dict = {
                            "uri": scheduled_event_entity.uri,
                            "name": scheduled_event_entity.name,
                        }
                        async for invitee_entity in self._generate_event_invitee_entities(
                            client, scheduled_event_dict, event_breadcrumbs
                        ):
                            total_entities_yielded += 1
                            yield invitee_entity
                except Exception as e:
                    self.logger.error(f"Error generating scheduled events: {e}", exc_info=True)

                # Final summary of entity generation
                self.logger.info(
                    f"CALENDLY ENTITY GENERATION COMPLETE: "
                    f"total_yielded={total_entities_yielded} "
                    f"(user=1, event_types={event_type_count}, "
                    f"scheduled_events={scheduled_event_count}, invitees={total_entities_yielded - 1 - event_type_count - scheduled_event_count})"
                )

                # CRITICAL: Warn if no entities were yielded
                if total_entities_yielded == 0:
                    self.logger.error(
                        "CRITICAL: No entities were yielded from Calendly source connector! "
                        "This will result in an empty collection. Check API connectivity and authentication."
                    )
                elif total_entities_yielded < 3:
                    self.logger.warning(
                        f"WARNING: Only {total_entities_yielded} entity/entities yielded. "
                        f"Expected at least 3 event types for Monke tests."
                    )
        except Exception as e:
            self.logger.error(f"❌ CRITICAL ERROR in generate_entities(): {e}", exc_info=True)
            raise

            # CRITICAL: Warn if no entities were yielded
            if total_entities_yielded == 0:
                self.logger.error(
                    "❌ CRITICAL: No entities were yielded from Calendly source connector! "
                    "This will result in an empty collection. Check API connectivity and authentication."
                )
            elif total_entities_yielded < 3:
                self.logger.warning(
                    f"⚠️ WARNING: Only {total_entities_yielded} entity/entities yielded. "
                    f"Expected at least 3 event types for Monke tests."
                )
        except Exception as e:
            self.logger.error(f"❌ CRITICAL ERROR in generate_entities(): {e}", exc_info=True)
            raise

    async def validate(self) -> bool:
        """Verify OAuth2 token by pinging Calendly's /users/me endpoint."""
        return await self._validate_oauth2(
            ping_url=f"{self.BASE_URL}/users/me",
            headers={"Content-Type": "application/json"},
            timeout=10.0,
        )
