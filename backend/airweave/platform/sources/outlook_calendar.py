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
from tenacity import retry, stop_after_attempt

from airweave.core.logging import logger
from airweave.core.shared_models import RateLimitLevel
from airweave.platform.configs.config import OutlookCalendarConfig
from airweave.platform.decorators import source
from airweave.platform.entities._base import BaseEntity, Breadcrumb
from airweave.platform.entities.outlook_calendar import (
    OutlookCalendarAttachmentEntity,
    OutlookCalendarCalendarEntity,
    OutlookCalendarEventEntity,
)
from airweave.platform.sources._base import BaseSource
from airweave.platform.sources.retry_helpers import (
    retry_if_rate_limit_or_timeout,
    wait_rate_limit_with_backoff,
)
from airweave.platform.storage import FileSkippedException
from airweave.schemas.source_connection import AuthenticationMethod, OAuthType


@source(
    name="Outlook Calendar",
    short_name="outlook_calendar",
    auth_methods=[
        AuthenticationMethod.OAUTH_BROWSER,
        AuthenticationMethod.OAUTH_TOKEN,
        AuthenticationMethod.AUTH_PROVIDER,
    ],
    oauth_type=OAuthType.WITH_REFRESH,
    auth_config_class=None,
    config_class=OutlookCalendarConfig,
    labels=["Productivity", "Calendar"],
    supports_continuous=False,
    rate_limit_level=RateLimitLevel.ORG,
)
class OutlookCalendarSource(BaseSource):
    """Outlook Calendar source connector integrates with the Microsoft Graph API to extract data.

    Synchronizes data from Outlook calendars.

    It provides comprehensive access to calendars, events, and attachments
    with proper timezone handling and meeting management features.
    """

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

    @retry(
        stop=stop_after_attempt(5),
        retry=retry_if_rate_limit_or_timeout,
        wait=wait_rate_limit_with_backoff,
        reraise=True,
    )
    async def _get_with_auth(
        self, client: httpx.AsyncClient, url: str, params: Optional[dict] = None
    ) -> dict:
        """Make an authenticated GET request to Microsoft Graph API."""
        self.logger.debug(f"Making authenticated GET request to: {url} with params: {params}")

        # Get fresh token (will refresh if needed)
        access_token = await self.get_access_token()
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
        }

        try:
            response = await client.get(url, headers=headers, params=params)

            # Handle 401 errors by refreshing token and retrying
            if response.status_code == 401:
                self.logger.warning(
                    f"Got 401 Unauthorized from Microsoft Graph API at {url}, refreshing token..."
                )
                await self.refresh_on_unauthorized()

                # Get new token and retry
                access_token = await self.get_access_token()
                headers = {
                    "Authorization": f"Bearer {access_token}",
                    "Accept": "application/json",
                }
                response = await client.get(url, headers=headers, params=params)

            response.raise_for_status()
            data = response.json()
            self.logger.debug(f"Received response from {url} - Status: {response.status_code}")
            return data
        except Exception as e:
            self.logger.error(f"Error in API request to {url}: {str(e)}")
            raise

    async def _generate_calendar_entities(
        self, client: httpx.AsyncClient
    ) -> AsyncGenerator[OutlookCalendarCalendarEntity, None]:
        """Generate OutlookCalendarCalendarEntity objects for each calendar.

        Endpoint: GET /me/calendars
        """
        self.logger.info("Starting calendar entity generation")
        url = f"{self.GRAPH_BASE_URL}/me/calendars"
        calendar_count = 0

        try:
            while url:
                self.logger.debug(f"Fetching calendars from: {url}")
                data = await self._get_with_auth(client, url)
                calendars = data.get("value", [])
                self.logger.info(f"Retrieved {len(calendars)} calendars")

                for calendar_data in calendars:
                    calendar_count += 1
                    calendar_id = calendar_data["id"]
                    calendar_name = calendar_data.get("name", "Unknown Calendar")

                    self.logger.debug(f"Processing calendar #{calendar_count}: {calendar_name}")

                    yield OutlookCalendarCalendarEntity(
                        breadcrumbs=[],
                        id=calendar_id,
                        name=calendar_name,
                        created_at=None,  # Calendars don't have creation timestamp
                        updated_at=None,  # Calendars don't have update timestamp
                        # API fields
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
                        web_url_override=calendar_data.get("webUrl"),
                    )

                # Handle pagination
                url = data.get("@odata.nextLink")
                if url:
                    self.logger.debug("Following pagination to next page")

            self.logger.info(f"Completed calendar generation. Total calendars: {calendar_count}")

        except Exception as e:
            self.logger.error(f"Error generating calendar entities: {str(e)}")
            raise

    async def _generate_event_entities(
        self,
        client: httpx.AsyncClient,
        calendar: OutlookCalendarCalendarEntity,
    ) -> AsyncGenerator[BaseEntity, None]:
        """Generate OutlookCalendarEventEntity objects and their attachments.

        Endpoint: GET /me/calendars/{calendar_id}/events
        """
        calendar_id = calendar.id
        calendar_name = calendar.name
        self.logger.info(f"Starting event generation for calendar: {calendar_name}")

        url = f"{self.GRAPH_BASE_URL}/me/calendars/{calendar_id}/events"
        params = {"$top": 50}
        event_count = 0

        # Create breadcrumb for this calendar
        cal_breadcrumb = Breadcrumb(
            entity_id=calendar_id,
            name=calendar_name,
            entity_type="OutlookCalendarCalendarEntity",
        )

        try:
            while url:
                self.logger.debug(f"Fetching events from: {url}")
                data = await self._get_with_auth(client, url, params=params)
                events = data.get("value", [])
                self.logger.info(f"Retrieved {len(events)} events from calendar {calendar_name}")

                for event_data in events:
                    event_count += 1
                    event_id = event_data.get("id", "unknown")
                    event_subject = event_data.get("subject", f"Event {event_count}")

                    # Skip cancelled events (deleted but still returned by API)
                    if event_data.get("isCancelled"):
                        self.logger.info(f"Skipping cancelled event: {event_subject}")
                        continue

                    self.logger.debug(f"Processing event #{event_count}: {event_subject}")

                    try:
                        # Process the event
                        async for entity in self._process_event(client, event_data, cal_breadcrumb):
                            yield entity
                    except Exception as e:
                        self.logger.error(f"Error processing event {event_id}: {str(e)}")
                        # Continue with other events

                # Handle pagination
                url = data.get("@odata.nextLink")
                if url:
                    self.logger.debug("Following pagination to next page")
                    params = None  # params are included in the nextLink

            self.logger.info(
                f"Completed event generation for calendar {calendar_name}. "
                f"Total events: {event_count}"
            )

        except Exception as e:
            self.logger.error(f"Error generating events for calendar {calendar_name}: {str(e)}")
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
            self.logger.warning(f"Error parsing datetime: {str(e)}")
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
            self.logger.warning(f"Error parsing simple datetime: {str(e)}")
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
        created_dt = self._parse_simple_datetime(event_data.get("createdDateTime"))
        updated_dt = self._parse_simple_datetime(event_data.get("lastModifiedDateTime"))
        web_link = event_data.get("webLink")

        return OutlookCalendarEventEntity(
            breadcrumbs=[cal_breadcrumb],
            name=event_subject,
            subject=event_subject,
            body_preview=event_data.get("bodyPreview"),
            body_content=(
                event_data.get("body", {}).get("content") if event_data.get("body") else None
            ),
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
            id=event_id,
            created_datetime=created_dt,
            last_modified_datetime=updated_dt,
            web_url_override=web_link,
        )

    async def _process_event(
        self,
        client: httpx.AsyncClient,
        event_data: Dict,
        cal_breadcrumb: Breadcrumb,
    ) -> AsyncGenerator[BaseEntity, None]:
        """Process a single event and its attachments."""
        event_id = event_data["id"]
        event_subject = event_data.get("subject", "No Subject")

        self.logger.debug(f"Processing event: {event_subject} (ID: {event_id})")

        # Create event entity
        event_entity = self._create_event_entity(event_data, cal_breadcrumb)
        yield event_entity
        self.logger.debug(f"Event entity yielded for {event_subject}")

        # Create event breadcrumb for attachments
        event_breadcrumb = Breadcrumb(
            entity_id=event_id,
            name=event_subject,
            entity_type="OutlookCalendarEventEntity",
        )

        # Process attachments if the event has any
        if event_entity.has_attachments:
            self.logger.debug(f"Event {event_subject} has attachments, processing them")
            attachment_count = 0
            try:
                async for attachment_entity in self._process_event_attachments(
                    client, event_id, [cal_breadcrumb, event_breadcrumb], event_entity.web_url
                ):
                    attachment_count += 1
                    self.logger.debug(
                        f"Yielding attachment #{attachment_count} from event {event_subject}"
                    )
                    yield attachment_entity
                self.logger.debug(
                    f"Processed {attachment_count} attachments for event {event_subject}"
                )
            except Exception as e:
                self.logger.error(f"Error processing attachments for event {event_id}: {str(e)}")

    async def _process_event_attachments(
        self,
        client: httpx.AsyncClient,
        event_id: str,
        breadcrumbs: List[Breadcrumb],
        event_web_url: Optional[str],
    ) -> AsyncGenerator[OutlookCalendarAttachmentEntity, None]:
        """Process event attachments using the standard file processing pipeline."""
        self.logger.debug(f"Processing attachments for event {event_id}")

        url = f"{self.GRAPH_BASE_URL}/me/events/{event_id}/attachments"

        try:
            while url:
                self.logger.debug(f"Making request to: {url}")
                data = await self._get_with_auth(client, url)
                attachments = data.get("value", [])
                self.logger.debug(f"Retrieved {len(attachments)} attachments for event {event_id}")

                for att_idx, attachment in enumerate(attachments):
                    processed_entity = await self._process_single_attachment(
                        client,
                        attachment,
                        event_id,
                        breadcrumbs,
                        att_idx,
                        len(attachments),
                        event_web_url,
                    )
                    if processed_entity:
                        yield processed_entity

                # Handle pagination
                url = data.get("@odata.nextLink")
                if url:
                    self.logger.debug("Following pagination link")

        except Exception as e:
            self.logger.error(f"Error processing attachments for event {event_id}: {str(e)}")

    async def _process_single_attachment(
        self,
        client: httpx.AsyncClient,
        attachment: Dict,
        event_id: str,
        breadcrumbs: List[Breadcrumb],
        att_idx: int,
        total_attachments: int,
        event_web_url: Optional[str],
    ) -> Optional[OutlookCalendarAttachmentEntity]:
        """Process a single attachment and return the processed entity."""
        attachment_id = attachment["id"]
        attachment_type = attachment.get("@odata.type", "")
        attachment_name = attachment.get("name", "unknown")

        self.logger.debug(
            f"Processing attachment #{att_idx + 1}/{total_attachments} "
            f"(ID: {attachment_id}, Name: {attachment_name}, Type: {attachment_type})"
        )

        # Only process file attachments
        if "#microsoft.graph.fileAttachment" not in attachment_type:
            self.logger.debug(
                f"Skipping non-file attachment: {attachment_name} (type: {attachment_type})"
            )
            return None

        try:
            # Get attachment content if not already included
            content_bytes = attachment.get("contentBytes")
            if not content_bytes:
                self.logger.debug(f"Fetching content for attachment {attachment_id}")
                attachment_url = (
                    f"{self.GRAPH_BASE_URL}/me/events/{event_id}/attachments/{attachment_id}"
                )
                attachment_data = await self._get_with_auth(client, attachment_url)
                content_bytes = attachment_data.get("contentBytes")

                if not content_bytes:
                    self.logger.warning(f"No content found for attachment {attachment_name}")
                    return None

            # Decode the base64 data
            try:
                binary_data = base64.b64decode(content_bytes)
            except Exception as e:
                self.logger.error(f"Error decoding attachment content: {str(e)}")
                return None

            # Determine file type from mime_type
            mime_type = attachment.get("contentType") or "application/octet-stream"
            size = attachment.get("size", 0)
            if mime_type and "/" in mime_type:
                file_type = mime_type.split("/")[0]
            else:
                import os

                ext = os.path.splitext(attachment_name)[1].lower().lstrip(".")
                file_type = ext if ext else "file"

            # Create file entity
            file_entity = OutlookCalendarAttachmentEntity(
                composite_id=f"{event_id}_attachment_{attachment_id}",
                breadcrumbs=breadcrumbs,
                name=attachment_name,
                url=f"outlook://calendar/attachment/{event_id}/{attachment_id}",
                size=size,
                file_type=file_type,
                mime_type=mime_type,
                local_path=None,  # Will be set after saving
                # API fields
                event_id=event_id,
                attachment_id=attachment_id,
                content_type=attachment.get("contentType"),
                is_inline=attachment.get("isInline", False),
                content_id=attachment.get("contentId"),
                last_modified_at=attachment.get("lastModifiedDateTime"),
                event_web_url=event_web_url,
            )

            # Save bytes using file downloader
            try:
                await self.file_downloader.save_bytes(
                    entity=file_entity,
                    content=binary_data,
                    filename_with_extension=attachment_name,  # Attachment name from API
                    logger=self.logger,
                )

                # Verify save succeeded
                if not file_entity.local_path:
                    raise ValueError(f"Save failed - no local path set for {file_entity.name}")

                self.logger.debug(f"Successfully processed attachment: {attachment_name}")
                return file_entity

            except FileSkippedException as e:
                # File intentionally skipped (unsupported type, too large, etc.) - not an error
                self.logger.debug(f"Skipping attachment {attachment_name}: {e.reason}")
                return None

            except Exception as e:
                self.logger.error(f"Failed to save attachment {attachment_name}: {e}")
                return None

        except Exception as e:
            self.logger.error(f"Error processing attachment {attachment_id}: {str(e)}")
            return None

    async def generate_entities(self) -> AsyncGenerator[BaseEntity, None]:
        """Generate all Outlook Calendar entities: Calendars, Events and Attachments."""
        self.logger.info("===== STARTING OUTLOOK CALENDAR ENTITY GENERATION =====")
        entity_count = 0

        try:
            async with self.http_client() as client:
                self.logger.info("HTTP client created, starting entity generation")

                # Generate calendar entities and their events
                async for calendar_entity in self._generate_calendar_entities(client):
                    entity_count += 1
                    self.logger.info(
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
                        self.logger.info(
                            f"Yielding entity #{entity_count}: {entity_type} with ID {entity_id}"
                        )
                        yield event_entity

        except Exception as e:
            self.logger.error(f"Error in entity generation: {str(e)}", exc_info=True)
            raise
        finally:
            self.logger.info(
                f"===== OUTLOOK CALENDAR ENTITY GENERATION COMPLETE: {entity_count} entities ====="
            )

    async def validate(self) -> bool:
        """Verify Outlook Calendar OAuth2 token by pinging the calendars endpoint."""
        return await self._validate_oauth2(
            ping_url=f"{self.GRAPH_BASE_URL}/me/calendars?$top=1",
            headers={"Accept": "application/json"},
            timeout=10.0,
        )
