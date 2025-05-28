"""Outlook Calendar source implementation.

Comprehensive implementation that retrieves:
  - Calendars (GET /me/calendars)
  - Events (GET /me/calendars/{calendar_id}/events)
  - Event attachments (GET /me/events/{event_id}/attachments)

Follows the same structure as the Gmail and Outlook Mail implementations.
"""

import base64
from datetime import datetime
from typing import Any, AsyncGenerator, Dict, List, Optional

import httpx

from airweave.core.logging import logger
from airweave.platform.auth.schemas import AuthType
from airweave.platform.decorators import source
from airweave.platform.entities._base import Breadcrumb, ChunkEntity
from airweave.platform.entities.outlook_calendar import (
    OutlookCalendarAttachmentEntity,
    OutlookCalendarCalendarEntity,
    OutlookCalendarEventEntity,
)
from airweave.platform.sources._base import BaseSource


@source(
    name="Outlook Calendar",
    short_name="outlook_calendar",
    auth_type=AuthType.oauth2_with_refresh_rotating,
    auth_config_class="OutlookCalendarAuthConfig",
    config_class="OutlookCalendarConfig",
    labels=["Productivity", "Calendar"],
)
class OutlookCalendarSource(BaseSource):
    """Outlook Calendar source implementation (read-only)."""

    GRAPH_BASE_URL = "https://graph.microsoft.com/v1.0"

    @classmethod
    async def create(
        cls, access_token: str, config: Optional[Dict[str, Any]] = None
    ) -> "OutlookCalendarSource":
        """Create a new Outlook Calendar source instance."""
        logger.info("Creating new OutlookCalendarSource instance")
        instance = cls()
        instance.access_token = access_token
        logger.info(f"OutlookCalendarSource instance created with config: {config}")
        return instance

    async def _get_with_auth(
        self, client: httpx.AsyncClient, url: str, params: Optional[dict] = None
    ) -> dict:
        """Make an authenticated GET request to Microsoft Graph API."""
        logger.debug(f"Making authenticated GET request to: {url} with params: {params}")
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Accept": "application/json",
        }
        try:
            response = await client.get(url, headers=headers, params=params)
            response.raise_for_status()
            data = response.json()
            logger.debug(f"Received response from {url} - Status: {response.status_code}")
            return data
        except Exception as e:
            logger.error(f"Error in API request to {url}: {str(e)}")
            raise

    async def _generate_calendar_entities(
        self, client: httpx.AsyncClient
    ) -> AsyncGenerator[OutlookCalendarCalendarEntity, None]:
        """Generate OutlookCalendarCalendarEntity objects for each calendar.

        Endpoint: GET /me/calendars
        """
        logger.info("Starting calendar entity generation")
        url = f"{self.GRAPH_BASE_URL}/me/calendars"
        calendar_count = 0

        try:
            while url:
                logger.debug(f"Fetching calendars from: {url}")
                data = await self._get_with_auth(client, url)
                calendars = data.get("value", [])
                logger.info(f"Retrieved {len(calendars)} calendars")

                for calendar_data in calendars:
                    calendar_count += 1
                    calendar_id = calendar_data["id"]
                    calendar_name = calendar_data.get("name", "Unknown Calendar")

                    logger.debug(f"Processing calendar #{calendar_count}: {calendar_name}")

                    yield OutlookCalendarCalendarEntity(
                        entity_id=calendar_id,
                        breadcrumbs=[],
                        name=calendar_name,
                        color=calendar_data.get("color"),
                        hex_color=calendar_data.get("hexColor"),
                        change_key=calendar_data.get("changeKey"),
                        can_edit=calendar_data.get("canEdit", False),
                        can_share=calendar_data.get("canShare", False),
                        can_view_private_items=calendar_data.get("canViewPrivateItems", False),
                        is_default_calendar=calendar_data.get("isDefaultCalendar", False),
                        is_removable=calendar_data.get("isRemovable", True),
                        is_tallying_responses=calendar_data.get("isTallyingResponses", False),
                        owner=calendar_data.get("owner"),
                        allowed_online_meeting_providers=calendar_data.get(
                            "allowedOnlineMeetingProviders", []
                        ),
                        default_online_meeting_provider=calendar_data.get(
                            "defaultOnlineMeetingProvider"
                        ),
                    )

                # Handle pagination
                url = data.get("@odata.nextLink")
                if url:
                    logger.debug("Following pagination to next page")

            logger.info(f"Completed calendar generation. Total calendars: {calendar_count}")

        except Exception as e:
            logger.error(f"Error generating calendar entities: {str(e)}")
            raise

    async def _generate_event_entities(
        self,
        client: httpx.AsyncClient,
        calendar: OutlookCalendarCalendarEntity,
    ) -> AsyncGenerator[ChunkEntity, None]:
        """Generate OutlookCalendarEventEntity objects and their attachments.

        Endpoint: GET /me/calendars/{calendar_id}/events
        """
        calendar_id = calendar.entity_id
        calendar_name = calendar.name
        logger.info(f"Starting event generation for calendar: {calendar_name}")

        url = f"{self.GRAPH_BASE_URL}/me/calendars/{calendar_id}/events"
        params = {"$top": 50}
        event_count = 0

        # Create breadcrumb for this calendar
        cal_breadcrumb = Breadcrumb(
            entity_id=calendar_id,
            name=calendar_name[:50] if calendar_name else "Unknown Calendar",
            type="calendar",
        )

        try:
            while url:
                logger.debug(f"Fetching events from: {url}")
                data = await self._get_with_auth(client, url, params=params)
                events = data.get("value", [])
                logger.info(f"Retrieved {len(events)} events from calendar {calendar_name}")

                for event_data in events:
                    event_count += 1
                    event_id = event_data.get("id", "unknown")
                    event_subject = event_data.get("subject", f"Event {event_count}")

                    logger.debug(f"Processing event #{event_count}: {event_subject}")

                    try:
                        # Process the event
                        async for entity in self._process_event(client, event_data, cal_breadcrumb):
                            yield entity
                    except Exception as e:
                        logger.error(f"Error processing event {event_id}: {str(e)}")
                        # Continue with other events

                # Handle pagination
                url = data.get("@odata.nextLink")
                if url:
                    logger.debug("Following pagination to next page")
                    params = None  # params are included in the nextLink

            logger.info(
                f"Completed event generation for calendar {calendar_name}. "
                f"Total events: {event_count}"
            )

        except Exception as e:
            logger.error(f"Error generating events for calendar {calendar_name}: {str(e)}")
            raise

    def _parse_datetime_field(self, dt_obj: Optional[Dict]) -> Optional[datetime]:
        """Parse datetime from Microsoft Graph API format."""
        if not dt_obj or not dt_obj.get("dateTime"):
            return None
        try:
            dt_str = dt_obj["dateTime"]
            if "T" in dt_str:
                # Handle timezone info
                if dt_str.endswith("Z"):
                    dt_str = dt_str.replace("Z", "+00:00")
                elif "+" not in dt_str and "-" not in dt_str[-6:]:
                    # If no timezone info, assume UTC
                    dt_str += "+00:00"
                return datetime.fromisoformat(dt_str)
        except (ValueError, TypeError) as e:
            logger.warning(f"Error parsing datetime: {str(e)}")
        return None

    def _parse_simple_datetime(self, dt_str: Optional[str]) -> Optional[datetime]:
        """Parse simple datetime string."""
        if not dt_str:
            return None
        try:
            if "T" in dt_str:
                if dt_str.endswith("Z"):
                    dt_str = dt_str.replace("Z", "+00:00")
                return datetime.fromisoformat(dt_str)
        except (ValueError, TypeError) as e:
            logger.warning(f"Error parsing simple datetime: {str(e)}")
        return None

    def _create_event_entity(
        self, event_data: Dict, cal_breadcrumb: Breadcrumb
    ) -> OutlookCalendarEventEntity:
        """Create an OutlookCalendarEventEntity from event data."""
        event_id = event_data["id"]
        event_subject = event_data.get("subject", "No Subject")

        # Extract event fields
        start_info = event_data.get("start", {})
        end_info = event_data.get("end", {})

        return OutlookCalendarEventEntity(
            entity_id=event_id,
            breadcrumbs=[cal_breadcrumb],
            subject=event_subject,
            body_preview=event_data.get("bodyPreview"),
            body_content=event_data.get("body", {}).get("content")
            if event_data.get("body")
            else None,
            body_content_type=event_data.get("body", {}).get("contentType"),
            start_datetime=self._parse_datetime_field(start_info),
            start_timezone=start_info.get("timeZone"),
            end_datetime=self._parse_datetime_field(end_info),
            end_timezone=end_info.get("timeZone"),
            is_all_day=event_data.get("isAllDay", False),
            is_cancelled=event_data.get("isCancelled", False),
            is_draft=event_data.get("isDraft", False),
            is_online_meeting=event_data.get("isOnlineMeeting", False),
            is_organizer=event_data.get("isOrganizer", False),
            is_reminder_on=event_data.get("isReminderOn", True),
            show_as=event_data.get("showAs"),
            importance=event_data.get("importance"),
            sensitivity=event_data.get("sensitivity"),
            response_status=event_data.get("responseStatus"),
            organizer=event_data.get("organizer"),
            attendees=event_data.get("attendees"),
            location=event_data.get("location"),
            locations=event_data.get("locations", []),
            categories=event_data.get("categories", []),
            created_at=self._parse_simple_datetime(event_data.get("createdDateTime")),
            updated_at=self._parse_simple_datetime(event_data.get("lastModifiedDateTime")),
            web_link=event_data.get("webLink"),
            online_meeting_url=event_data.get("onlineMeetingUrl"),
            online_meeting_provider=event_data.get("onlineMeetingProvider"),
            online_meeting=event_data.get("onlineMeeting"),
            series_master_id=event_data.get("seriesMasterId"),
            recurrence=event_data.get("recurrence"),
            reminder_minutes_before_start=event_data.get("reminderMinutesBeforeStart"),
            has_attachments=event_data.get("hasAttachments", False),
            ical_uid=event_data.get("iCalUId"),
            change_key=event_data.get("changeKey"),
            original_start_timezone=event_data.get("originalStartTimeZone"),
            original_end_timezone=event_data.get("originalEndTimeZone"),
            allow_new_time_proposals=event_data.get("allowNewTimeProposals", True),
            hide_attendees=event_data.get("hideAttendees", False),
        )

    async def _process_event(
        self,
        client: httpx.AsyncClient,
        event_data: Dict,
        cal_breadcrumb: Breadcrumb,
    ) -> AsyncGenerator[ChunkEntity, None]:
        """Process a single event and its attachments."""
        event_id = event_data["id"]
        event_subject = event_data.get("subject", "No Subject")

        logger.debug(f"Processing event: {event_subject} (ID: {event_id})")

        # Create event entity
        event_entity = self._create_event_entity(event_data, cal_breadcrumb)
        yield event_entity
        logger.debug(f"Event entity yielded for {event_subject}")

        # Create event breadcrumb for attachments
        event_breadcrumb = Breadcrumb(
            entity_id=event_id,
            name=event_subject[:50] if event_subject else f"Event {event_id[:8]}",
            type="event",
        )

        # Process attachments if the event has any
        if event_entity.has_attachments:
            logger.debug(f"Event {event_subject} has attachments, processing them")
            attachment_count = 0
            try:
                async for attachment_entity in self._process_event_attachments(
                    client, event_id, [cal_breadcrumb, event_breadcrumb]
                ):
                    attachment_count += 1
                    logger.debug(
                        f"Yielding attachment #{attachment_count} from event {event_subject}"
                    )
                    yield attachment_entity
                logger.debug(f"Processed {attachment_count} attachments for event {event_subject}")
            except Exception as e:
                logger.error(f"Error processing attachments for event {event_id}: {str(e)}")

    async def _create_content_stream(self, binary_data: bytes):
        """Create an async generator for binary content."""
        yield binary_data

    async def _process_event_attachments(
        self,
        client: httpx.AsyncClient,
        event_id: str,
        breadcrumbs: List[Breadcrumb],
    ) -> AsyncGenerator[OutlookCalendarAttachmentEntity, None]:
        """Process event attachments using the standard file processing pipeline."""
        logger.debug(f"Processing attachments for event {event_id}")

        url = f"{self.GRAPH_BASE_URL}/me/events/{event_id}/attachments"

        try:
            while url:
                logger.debug(f"Making request to: {url}")
                data = await self._get_with_auth(client, url)
                attachments = data.get("value", [])
                logger.debug(f"Retrieved {len(attachments)} attachments for event {event_id}")

                for att_idx, attachment in enumerate(attachments):
                    processed_entity = await self._process_single_attachment(
                        client, attachment, event_id, breadcrumbs, att_idx, len(attachments)
                    )
                    if processed_entity:
                        yield processed_entity

                # Handle pagination
                url = data.get("@odata.nextLink")
                if url:
                    logger.debug("Following pagination link")

        except Exception as e:
            logger.error(f"Error processing attachments for event {event_id}: {str(e)}")

    async def _process_single_attachment(
        self,
        client: httpx.AsyncClient,
        attachment: Dict,
        event_id: str,
        breadcrumbs: List[Breadcrumb],
        att_idx: int,
        total_attachments: int,
    ) -> Optional[OutlookCalendarAttachmentEntity]:
        """Process a single attachment and return the processed entity."""
        attachment_id = attachment["id"]
        attachment_type = attachment.get("@odata.type", "")
        attachment_name = attachment.get("name", "unknown")

        logger.debug(
            f"Processing attachment #{att_idx + 1}/{total_attachments} "
            f"(ID: {attachment_id}, Name: {attachment_name}, Type: {attachment_type})"
        )

        # Only process file attachments
        if "#microsoft.graph.fileAttachment" not in attachment_type:
            logger.debug(
                f"Skipping non-file attachment: {attachment_name} (type: {attachment_type})"
            )
            return None

        try:
            # Get attachment content if not already included
            content_bytes = attachment.get("contentBytes")
            if not content_bytes:
                logger.debug(f"Fetching content for attachment {attachment_id}")
                attachment_url = (
                    f"{self.GRAPH_BASE_URL}/me/events/{event_id}/attachments/{attachment_id}"
                )
                attachment_data = await self._get_with_auth(client, attachment_url)
                content_bytes = attachment_data.get("contentBytes")

                if not content_bytes:
                    logger.warning(f"No content found for attachment {attachment_name}")
                    return None

            # Create file entity
            file_entity = OutlookCalendarAttachmentEntity(
                entity_id=f"{event_id}_attachment_{attachment_id}",
                breadcrumbs=breadcrumbs,
                file_id=attachment_id,
                name=attachment_name,
                mime_type=attachment.get("contentType"),
                size=attachment.get("size", 0),
                download_url=f"outlook://calendar/attachment/{event_id}/{attachment_id}",
                event_id=event_id,
                attachment_id=attachment_id,
                content_type=attachment.get("contentType"),
                is_inline=attachment.get("isInline", False),
                content_id=attachment.get("contentId"),
                last_modified_at=attachment.get("lastModifiedDateTime"),
                metadata={
                    "source": "outlook_calendar",
                    "event_id": event_id,
                    "attachment_id": attachment_id,
                },
            )

            # Decode the base64 data
            try:
                binary_data = base64.b64decode(content_bytes)
            except Exception as e:
                logger.error(f"Error decoding attachment content: {str(e)}")
                return None

            # Process using the BaseSource method
            logger.debug(f"Processing file entity for {attachment_name} with direct content stream")
            processed_entity = await self.process_file_entity_with_content(
                file_entity=file_entity,
                content_stream=self._create_content_stream(binary_data),
                metadata={"source": "outlook_calendar", "event_id": event_id},
            )

            if processed_entity:
                logger.debug(f"Successfully processed attachment: {attachment_name}")
                return processed_entity
            else:
                logger.warning(f"Processing failed for attachment: {attachment_name}")
                return None

        except Exception as e:
            logger.error(f"Error processing attachment {attachment_id}: {str(e)}")
            return None

    async def generate_entities(self) -> AsyncGenerator[ChunkEntity, None]:
        """Generate all Outlook Calendar entities: Calendars, Events and Attachments."""
        logger.info("===== STARTING OUTLOOK CALENDAR ENTITY GENERATION =====")
        entity_count = 0

        try:
            async with httpx.AsyncClient() as client:
                logger.info("HTTP client created, starting entity generation")

                # Generate calendar entities and their events
                async for calendar_entity in self._generate_calendar_entities(client):
                    entity_count += 1
                    logger.info(
                        f"Yielding entity #{entity_count}: Calendar - {calendar_entity.name}"
                    )
                    yield calendar_entity

                    # Generate events for this calendar
                    async for event_entity in self._generate_event_entities(
                        client, calendar_entity
                    ):
                        entity_count += 1
                        entity_type = type(event_entity).__name__
                        entity_id = event_entity.entity_id
                        logger.info(
                            f"Yielding entity #{entity_count}: {entity_type} with ID {entity_id}"
                        )
                        yield event_entity

        except Exception as e:
            logger.error(f"Error in entity generation: {str(e)}", exc_info=True)
            raise
        finally:
            logger.info(
                f"===== OUTLOOK CALENDAR ENTITY GENERATION COMPLETE: {entity_count} entities ====="
            )
