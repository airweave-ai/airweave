"""Cal.com-specific bongo implementation.

Creates, updates, and deletes test event types and bookings via the real Cal.com API.
"""

import asyncio
import re
import time
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import httpx
from monke.bongos.base_bongo import BaseBongo
from monke.utils.logging import get_logger


class CalComBongo(BaseBongo):
    """Bongo for Cal.com that creates event types and bookings for end-to-end testing.

    - Uses OAuth access token as bearer token
    - Embeds a short token in event type descriptions and booking notes for verification
    - Creates event types and then bookings for those event types
    """

    connector_type = "cal_com"

    API_BASE = "https://api.cal.com/v2"
    API_VERSION = "2024-06-14"

    def __init__(self, credentials: Dict[str, Any], **kwargs):
        """Initialize the Cal.com bongo.

        Args:
            credentials: Dict with at least "access_token" (Cal.com OAuth token)
            **kwargs: Configuration from config file
        """
        super().__init__(credentials)
        
        # Initialize logger FIRST before using it
        self.logger = get_logger("cal_com_bongo")
        
        # Debug: Log available credential fields
        self.logger.info(
            f"Received credentials with fields: {list(credentials.keys())}"
        )
        
        # Try to get access_token - support multiple possible field names from Composio
        self.access_token = (
            credentials.get("access_token")
            or credentials.get("token")
            or credentials.get("generic_api_key")
        )
        
        if not self.access_token:
            available_fields = list(credentials.keys())
            self.logger.error(
                f"No 'access_token' in credentials. Available: {available_fields}"
            )
            raise ValueError(
                f"Missing 'access_token' in credentials. "
                f"Expected one of: 'access_token', 'token', 'generic_api_key'. "
                f"Available fields: {available_fields}"
            )
        self.entity_count: int = int(kwargs.get("entity_count", 3))
        self.openai_model: str = kwargs.get("openai_model", "gpt-4.1-mini")
        self.max_concurrency: int = int(kwargs.get("max_concurrency", 1))
        # Use rate_limit_delay_ms from config if provided, otherwise default to 1000ms
        rate_limit_ms = int(kwargs.get("rate_limit_delay_ms", 1000))
        self.rate_limit_delay: float = rate_limit_ms / 1000.0

        # Runtime state
        self._schedules: List[Dict[str, Any]] = []
        self._event_types: List[Dict[str, Any]] = []
        self._bookings: List[Dict[str, Any]] = []
        self._default_schedule_id: Optional[int] = None

        # Pacing
        self.last_request_time = 0.0

    def _headers(self) -> Dict[str, str]:
        """Get headers for API requests."""
        return {
            "Authorization": f"Bearer {self.access_token}",
            "cal-api-version": self.API_VERSION,
            "Content-Type": "application/json",
        }

    async def _rate_limit(self):
        """Simple rate limiting to avoid hitting API limits."""
        now = time.time()
        elapsed = now - self.last_request_time
        if elapsed < self.rate_limit_delay:
            await asyncio.sleep(self.rate_limit_delay - elapsed)
        self.last_request_time = time.time()

    async def _ensure_default_schedule(self, client: httpx.AsyncClient) -> Optional[int]:
        """Get or use the default schedule for event types."""
        try:
            await self._rate_limit()
            resp = await client.get(
                f"{self.API_BASE}/schedules/default",
                headers=self._headers(),
            )
            if resp.status_code == 200:
                schedule_data = resp.json().get("data", {})
                if schedule_data:
                    schedule_id = schedule_data.get("id")
                    if schedule_id:
                        self.logger.info(f"Using default schedule: {schedule_id}")
                        return schedule_id
        except Exception as e:
            self.logger.warning(f"Could not get default schedule: {e}")

        # Try to get any schedule
        try:
            await self._rate_limit()
            resp = await client.get(
                f"{self.API_BASE}/schedules",
                headers=self._headers(),
            )
            if resp.status_code == 200:
                schedules = resp.json().get("data", [])
                if schedules:
                    schedule_id = schedules[0].get("id")
                    if schedule_id:
                        self.logger.info(f"Using first available schedule: {schedule_id}")
                        return schedule_id
        except Exception as e:
            self.logger.warning(f"Could not get schedules: {e}")

        return None

    async def create_entities(self) -> List[Dict[str, Any]]:
        """Create event types and bookings in Cal.com.

        Returns a list of created entity descriptors used by the test flow.
        """
        self.logger.info(f"🥁 Creating {self.entity_count} Cal.com event types with bookings")
        from monke.generation.cal_com import generate_cal_com_booking, generate_cal_com_event_type

        entities: List[Dict[str, Any]] = []
        semaphore = asyncio.Semaphore(self.max_concurrency)

        async with httpx.AsyncClient() as client:
            # Get default schedule for event types
            self._default_schedule_id = await self._ensure_default_schedule(client)

            async def create_event_type_and_booking() -> Optional[Dict[str, Any]]:
                async with semaphore:
                    try:
                        await self._rate_limit()
                        token = str(uuid.uuid4())[:8]
                        self.logger.info(f"🔨 Generating content for event type with token: {token}")

                        # Generate event type content
                        (
                            title,
                            description,
                            duration_minutes,
                            location_type,
                            location_details,
                        ) = await generate_cal_com_event_type(self.openai_model, token)
                        self.logger.info(f"📝 Generated event type: '{title[:50]}...'")

                        # Normalize location type to valid Cal.com values
                        valid_location_types = {"address", "link", "integration", "phone"}
                        if location_type not in valid_location_types:
                            location_lower = location_type.lower()
                            if "zoom" in location_lower or "video" in location_lower:
                                location_type = "integration"
                                location_details = "cal-video"
                            elif "phone" in location_lower or "call" in location_lower:
                                location_type = "phone"
                            elif "address" in location_lower or "in-person" in location_lower:
                                location_type = "address"
                            else:
                                location_type = "integration"
                                location_details = "cal-video"

                        # Build location object based on type
                        location_obj = {"type": location_type, "public": True}
                        
                        if location_type == "link":
                            url = (
                                location_details
                                if location_details and location_details.startswith(("http://", "https://"))
                                else "https://meet.google.com/abc-defg-hij"
                            )
                            location_obj["url"] = url
                        elif location_type == "address" and location_details:
                            location_obj["address"] = location_details
                        elif location_type == "phone" and location_details:
                            location_obj["phoneNumber"] = location_details
                        elif location_type == "integration":
                            location_obj["integration"] = "cal-video"
                        else:
                            # Fallback to integration type
                            location_obj = {"type": "integration", "integration": "cal-video", "public": True}
                        
                        # Generate slug from title (URL-friendly identifier)
                        slug = re.sub(r'[^a-z0-9]+', '-', title.lower()).strip('-')
                        if not slug:
                            slug = f"event-{token}"
                        else:
                            slug = f"{slug}-{token}"  # Add token to ensure uniqueness
                        
                        # Build event type data (title, slug, lengthInMinutes are required)
                        event_type_data = {
                            "title": title,
                            "slug": slug,
                            "lengthInMinutes": duration_minutes,
                            "description": description,
                            "locations": [location_obj],
                            "hidden": False,
                            "bookingRequiresAuthentication": False,
                        }

                        # Add schedule if available
                        if self._default_schedule_id:
                            event_type_data["scheduleId"] = self._default_schedule_id

                        resp = await client.post(
                            f"{self.API_BASE}/event-types",
                            headers=self._headers(),
                            json=event_type_data,
                        )

                        if resp.status_code not in (200, 201):
                            error_data = resp.text
                            try:
                                error_json = resp.json()
                                error_data = error_json
                            except Exception:
                                pass
                            self.logger.error(
                                f"Failed to create event type: {resp.status_code} - {error_data}"
                            )
                            resp.raise_for_status()

                        event_type = resp.json().get("data", {})
                        if not event_type:
                            # Some APIs return the data directly
                            event_type = resp.json()
                        event_type_id = event_type.get("id")
                        if not event_type_id:
                            raise ValueError(f"Event type creation response missing ID: {event_type}")

                        event_type_entity = {
                            "type": "event_type",
                            "id": event_type_id,
                            "name": title,
                            "token": token,
                            "expected_content": token,
                            "path": f"cal_com/event_type/{event_type_id}",
                        }
                        entities.append(event_type_entity)
                        self._event_types.append(event_type_entity)

                        # Create a booking for this event type
                        await self._rate_limit()
                        booking_token = str(uuid.uuid4())[:8]
                        self.logger.info(
                            f"🔨 Generating content for booking with token: {booking_token}"
                        )

                        # Generate booking content
                        attendee_name = f"Test Attendee {token[:4]}"
                        attendee_email = f"test-{token}@example.com"
                        notes, questions = await generate_cal_com_booking(
                            self.openai_model, booking_token, attendee_name, attendee_email
                        )

                        # Calculate start time (1 day from now, at 9 AM UTC)
                        start_time = datetime.utcnow() + timedelta(days=1)
                        start_time = start_time.replace(hour=9, minute=0, second=0, microsecond=0)
                        end_time = start_time + timedelta(minutes=duration_minutes)

                        booking_data = {
                            "start": start_time.isoformat() + "Z",
                            "eventTypeId": event_type_id,
                            "attendee": {
                                "name": attendee_name,
                                "email": attendee_email,
                                "timeZone": "UTC",
                            },
                            "metadata": {"notes": notes},
                        }

                        # Add location with proper structure
                        if location_type == "integrations:zoom" or location_type.startswith("integrations:"):
                            booking_data["location"] = {"type": location_type}
                        elif location_type == "address" and location_details:
                            booking_data["location"] = {
                                "type": "address",
                                "address": location_details,
                            }

                        # Add location if needed
                        if location_type == "address" and location_details:
                            booking_data["location"] = {
                                "type": "address",
                                "address": location_details,
                            }

                        resp = await client.post(
                            f"{self.API_BASE}/bookings",
                            headers=self._headers(),
                            json=booking_data,
                        )

                        if resp.status_code not in (200, 201):
                            error_data = resp.text
                            try:
                                error_json = resp.json()
                                error_data = error_json
                            except Exception:
                                pass
                            self.logger.warning(
                                f"Failed to create booking: {resp.status_code} - {error_data}"
                            )
                            # Don't fail the whole test if booking creation fails
                            # Just log and continue
                        else:
                            booking = resp.json().get("data", {})
                            if not booking:
                                booking = resp.json()
                            booking_id = booking.get("id")
                            if booking_id:
                                booking_entity = {
                                    "type": "booking",
                                    "id": booking_id,
                                    "name": f"Booking for {title}",
                                    "parent_id": event_type_id,
                                    "token": booking_token,
                                    "expected_content": booking_token,
                                    "path": f"cal_com/booking/{booking_id}",
                                }
                                entities.append(booking_entity)
                                self._bookings.append(booking_entity)
                                self.logger.info(
                                    f"✅ Created booking {booking_id} for event type {event_type_id}"
                                )

                        self.logger.info(
                            f"✅ Created event type {event_type_id}: {title[:50]}..."
                        )
                        return event_type_entity

                    except Exception as e:
                        self.logger.error(f"❌ Error in create_event_type_and_booking: {type(e).__name__}: {str(e)}")
                        raise

            # Create all event types (and their bookings) in parallel
            tasks = [create_event_type_and_booking() for _ in range(self.entity_count)]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Process results and handle any exceptions
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    self.logger.error(f"Failed to create event type {i + 1}: {result}")
                    raise result
                elif result:
                    self.logger.info(
                        f"✅ Created event type {i + 1}/{self.entity_count}: {result['name'][:50]}..."
                    )

        self.created_entities = entities
        return entities

    async def update_entities(self) -> List[Dict[str, Any]]:
        """Update a small subset of event types by regenerating title/description with same token."""
        self.logger.info("🥁 Updating some Cal.com event types")
        if not self._event_types:
            return []

        from monke.generation.cal_com import generate_cal_com_event_type

        updated_entities: List[Dict[str, Any]] = []
        count = min(2, len(self._event_types))

        async with httpx.AsyncClient() as client:
            for i in range(count):
                await self._rate_limit()
                et = self._event_types[i]
                (
                    title,
                    description,
                    duration_minutes,
                    location_type,
                    location_details,
                ) = await generate_cal_com_event_type(self.openai_model, et["token"])

                event_type_data = {
                    "title": title,
                    "description": description,
                    "lengthInMinutes": duration_minutes,
                }

                resp = await client.patch(
                    f"{self.API_BASE}/event-types/{et['id']}",
                    headers=self._headers(),
                    json=event_type_data,
                )
                resp.raise_for_status()
                updated_entities.append({**et, "name": title, "expected_content": et["token"]})

        return updated_entities

    async def delete_entities(self) -> List[str]:
        """Delete all created event types and bookings."""
        self.logger.info("🥁 Deleting all Cal.com test entities")
        deleted_ids = await self.delete_specific_entities(self.created_entities)
        return deleted_ids

    async def delete_specific_entities(self, entities: List[Dict[str, Any]]) -> List[str]:
        """Delete provided list of entities by id."""
        self.logger.info(f"🥁 Deleting {len(entities)} Cal.com entities")
        deleted: List[str] = []
        async with httpx.AsyncClient() as client:
            for e in entities:
                try:
                    await self._rate_limit()
                    entity_type = e.get("type", "")
                    entity_id = e.get("id")

                    if entity_type == "booking":
                        # Delete booking
                        r = await client.delete(
                            f"{self.API_BASE}/bookings/{entity_id}", headers=self._headers()
                        )
                    elif entity_type == "event_type":
                        # Delete event type
                        r = await client.delete(
                            f"{self.API_BASE}/event-types/{entity_id}", headers=self._headers()
                        )
                    else:
                        self.logger.warning(f"Unknown entity type: {entity_type}")
                        continue

                    if r.status_code in (200, 204):
                        deleted.append(str(entity_id))
                    else:
                        self.logger.warning(
                            f"Delete failed for {entity_type} {entity_id}: {r.status_code} - {r.text}"
                        )
                except Exception as ex:
                    self.logger.warning(f"Delete error for {e.get('id')}: {ex}")
        return deleted

    async def cleanup(self):
        """Comprehensive cleanup of all monke test data."""
        self.logger.info("🧹 Starting comprehensive Cal.com cleanup")

        cleanup_stats = {
            "schedules_deleted": 0,
            "event_types_deleted": 0,
            "bookings_deleted": 0,
            "errors": 0,
        }

        try:
            # Clean up current session data
            if self._event_types or self._bookings:
                self.logger.info(
                    f"🗑️ Cleaning up {len(self._event_types)} event types and {len(self._bookings)} bookings"
                )
                await self.delete_specific_entities(self._event_types + self._bookings)
                cleanup_stats["event_types_deleted"] += len(self._event_types)
                cleanup_stats["bookings_deleted"] += len(self._bookings)

            # Note: Schedules are typically not deleted as they're shared resources
            # We only clean up event types and bookings that we created

            self.logger.info(
                f"🧹 Cleanup completed: {cleanup_stats['event_types_deleted']} event types, "
                f"{cleanup_stats['bookings_deleted']} bookings deleted, {cleanup_stats['errors']} errors"
            )

        except Exception as e:
            self.logger.error(f"❌ Error during comprehensive cleanup: {e}")
            # Don't re-raise - cleanup should be best-effort
