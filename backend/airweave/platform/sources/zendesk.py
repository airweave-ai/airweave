"""Zendesk source implementation for syncing tickets, comments, users, orgs, and attachments."""

from datetime import datetime, timezone
from typing import Any, AsyncGenerator, Dict, Optional

import httpx
from tenacity import retry, stop_after_attempt

from airweave.core.exceptions import TokenRefreshError
from airweave.core.shared_models import RateLimitLevel
from airweave.platform.configs.config import ZendeskConfig
from airweave.platform.decorators import source
from airweave.platform.entities._base import BaseEntity, Breadcrumb
from airweave.platform.entities.zendesk import (
    ZendeskAttachmentEntity,
    ZendeskCommentEntity,
    ZendeskOrganizationEntity,
    ZendeskTicketEntity,
    ZendeskUserEntity,
)
from airweave.platform.sources._base import BaseSource
from airweave.platform.sources.retry_helpers import (
    retry_if_rate_limit_or_timeout,
    wait_rate_limit_with_backoff,
)
from airweave.platform.storage import FileSkippedException
from airweave.schemas.source_connection import AuthenticationMethod, OAuthType


@source(
    name="Zendesk",
    short_name="zendesk",
    auth_methods=[
        AuthenticationMethod.OAUTH_BROWSER,
        AuthenticationMethod.OAUTH_TOKEN,
        AuthenticationMethod.AUTH_PROVIDER,
    ],
    oauth_type=OAuthType.WITH_REFRESH,
    requires_byoc=True,
    auth_config_class=None,
    config_class=ZendeskConfig,
    labels=["Customer Support", "CRM"],
    rate_limit_level=RateLimitLevel.ORG,
)
class ZendeskSource(BaseSource):
    """Zendesk source connector integrates with the Zendesk API to extract and synchronize data.

    Connects to your Zendesk instance to sync tickets, comments, users, orgs, and attachments.
    """

    @classmethod
    async def create(
        cls, access_token: str, config: Optional[Dict[str, Any]] = None
    ) -> "ZendeskSource":
        """Create a new Zendesk source.

        Args:
            access_token: OAuth access token for Zendesk API
            config: Optional configuration parameters

        Returns:
            Configured ZendeskSource instance
        """
        instance = cls()

        if not access_token:
            raise ValueError("Access token is required")

        instance.access_token = access_token
        instance.auth_type = "oauth"

        # Store config values as instance attributes
        if config and config.get("subdomain"):
            instance.subdomain = config["subdomain"]
            instance.exclude_closed_tickets = config.get("exclude_closed_tickets", False)
        else:
            # For token validation, we can use a placeholder subdomain
            # The actual subdomain will be provided during connection creation
            instance.subdomain = "validation-placeholder"
            instance.exclude_closed_tickets = False
            instance._is_validation_mode = True  # Flag to indicate this is for validation only

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
        """Make authenticated GET request to Zendesk API.

        Uses OAuth2 authentication.

        Args:
            client: HTTP client to use for the request
            url: API endpoint URL
            params: Optional query parameters
        """
        headers = await self._get_auth_headers()

        try:
            response = await client.get(url, headers=headers, params=params)

            # Handle 401 Unauthorized - token might have expired
            if response.status_code == 401:
                self.logger.warning(f"Received 401 Unauthorized for {url}")

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
                    # No token manager available to refresh expired token
                    self.logger.error("No token manager available to refresh expired token")
                    response.raise_for_status()

            # Raise for other HTTP errors
            response.raise_for_status()
            return response.json()

        except httpx.HTTPStatusError as e:
            self.logger.error(f"HTTP error from Zendesk API: {e.response.status_code} for {url}")
            raise
        except Exception as e:
            self.logger.error(f"Unexpected error accessing Zendesk API: {url}, {str(e)}")
            raise

    async def _get_auth_headers(self) -> Dict[str, str]:
        """Get OAuth authentication headers."""
        # Use get_access_token method to avoid sending 'Bearer None'
        token = await self.get_access_token()
        if not token:
            raise ValueError("No access token available for authentication")
        return {"Authorization": f"Bearer {token}"}

    async def get_access_token(self) -> Optional[str]:
        """Get the current access token."""
        if self.token_manager:
            # Token manager handles token retrieval
            return getattr(self, "access_token", None)
        return getattr(self, "access_token", None)

    @staticmethod
    def _parse_datetime(value: Optional[str]) -> Optional[datetime]:
        """Parse Zendesk ISO8601 timestamps into timezone-aware datetimes."""
        if not value:
            return None
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None

    @staticmethod
    def _now() -> datetime:
        """Return current UTC time."""
        return datetime.now(timezone.utc)

    def _build_ticket_url(self, ticket_id: int) -> str:
        """Construct a browser URL for a ticket."""
        return f"https://{self.subdomain}.zendesk.com/agent/tickets/{ticket_id}"

    def _build_user_url(self, user_id: int) -> str:
        """Construct a browser URL for a user profile."""
        return f"https://{self.subdomain}.zendesk.com/agent/users/{user_id}"

    def _build_org_url(self, org_id: int) -> str:
        """Construct a browser URL for an organization."""
        return f"https://{self.subdomain}.zendesk.com/agent/organizations/{org_id}"

    async def _generate_organization_entities(
        self, client: httpx.AsyncClient
    ) -> AsyncGenerator[BaseEntity, None]:
        """Generate organization entities."""
        url = f"https://{self.subdomain}.zendesk.com/api/v2/organizations.json"

        # Handle pagination
        while url:
            response = await self._get_with_auth(client, url)

            for org in response.get("organizations", []):
                org_name = org.get("name", "Organization")
                created_time = self._parse_datetime(org.get("created_at")) or self._now()
                updated_time = self._parse_datetime(org.get("updated_at")) or created_time

                yield ZendeskOrganizationEntity(
                    # Base fields
                    entity_id=str(org["id"]),
                    breadcrumbs=[],
                    name=org_name,
                    created_at=created_time,
                    updated_at=updated_time,
                    # API fields
                    organization_id=org["id"],
                    organization_name=org_name,
                    created_time=created_time,
                    updated_time=updated_time,
                    web_url_value=self._build_org_url(org["id"]),
                    domain_names=org.get("domain_names", []),
                    details=org.get("details"),
                    notes=org.get("notes"),
                    tags=org.get("tags", []),
                    custom_fields=org.get("custom_fields", []),
                    organization_fields=org.get("organization_fields", {}),
                    api_url=org.get("url"),
                )

            # Check for next page
            url = response.get("next_page")

    async def _generate_user_entities(
        self, client: httpx.AsyncClient
    ) -> AsyncGenerator[BaseEntity, None]:
        """Generate user entities."""
        url = f"https://{self.subdomain}.zendesk.com/api/v2/users.json"

        # Handle pagination
        while url:
            response = await self._get_with_auth(client, url)

            for user in response.get("users", []):
                if not user.get("email"):
                    continue  # Skip users without email

                now = self._now()
                created_time = self._parse_datetime(user.get("created_at")) or now
                updated_time = self._parse_datetime(user.get("updated_at")) or created_time
                display_name = user.get("name") or user.get("email") or f"User {user['id']}"

                yield ZendeskUserEntity(
                    # Base fields
                    entity_id=str(user["id"]),
                    breadcrumbs=[],
                    name=display_name,
                    created_at=created_time,
                    updated_at=updated_time,
                    # API fields
                    user_id=user["id"],
                    display_name=display_name,
                    created_time=created_time,
                    updated_time=updated_time,
                    web_url_value=self._build_user_url(user["id"]),
                    email=user["email"],
                    role=user.get("role", "end-user"),
                    active=user.get("active", True),
                    last_login_at=user.get("last_login_at"),
                    organization_id=user.get("organization_id"),
                    organization_name=None,
                    phone=user.get("phone"),
                    time_zone=user.get("time_zone"),
                    locale=user.get("locale"),
                    custom_fields=user.get("custom_fields", []),
                    tags=user.get("tags", []),
                    user_fields=user.get("user_fields", {}),
                    profile_url=user.get("url"),
                )

            # Check for next page
            url = response.get("next_page")

    async def _generate_ticket_entities(
        self, client: httpx.AsyncClient
    ) -> AsyncGenerator[BaseEntity, None]:
        """Generate ticket entities."""
        url = f"https://{self.subdomain}.zendesk.com/api/v2/tickets.json"

        # Handle pagination
        while url:
            response = await self._get_with_auth(client, url)

            for ticket in response.get("tickets", []):
                # Skip closed tickets if configured to do so
                if self.exclude_closed_tickets and ticket.get("status") == "closed":
                    continue

                created_time = self._parse_datetime(ticket.get("created_at")) or self._now()
                updated_time = self._parse_datetime(ticket.get("updated_at")) or created_time
                ticket_subject = ticket.get("subject", f"Ticket {ticket['id']}")
                ticket_url = self._build_ticket_url(ticket["id"])

                yield ZendeskTicketEntity(
                    # Base fields
                    entity_id=str(ticket["id"]),
                    breadcrumbs=[],
                    name=ticket_subject,
                    created_at=created_time,
                    updated_at=updated_time,
                    # API fields
                    ticket_id=ticket["id"],
                    subject=ticket_subject,
                    created_time=created_time,
                    updated_time=updated_time,
                    web_url_value=ticket_url,
                    description=ticket.get("description"),
                    requester_id=ticket.get("requester_id"),
                    requester_name=None,  # Will be populated from user data if needed
                    requester_email=None,  # Will be populated from user data if needed
                    assignee_id=ticket.get("assignee_id"),
                    assignee_name=None,  # Will be populated from user data if needed
                    assignee_email=None,  # Will be populated from user data if needed
                    status=ticket.get("status", "new"),
                    priority=ticket.get("priority"),
                    tags=ticket.get("tags", []),
                    custom_fields=ticket.get("custom_fields", []),
                    organization_id=ticket.get("organization_id"),
                    organization_name=None,  # Will be populated from organization data if needed
                    group_id=ticket.get("group_id"),
                    group_name=None,  # Will be populated from group data if needed
                    ticket_type=ticket.get("type"),
                    url=ticket.get("url"),
                )

            # Check for next page
            url = response.get("next_page")

    async def _generate_comment_entities(
        self, client: httpx.AsyncClient, ticket: Dict
    ) -> AsyncGenerator[BaseEntity, None]:
        """Generate comment entities for a ticket."""
        ticket_id = ticket["id"]
        # Include users in the response to get author names
        url = f"https://{self.subdomain}.zendesk.com/api/v2/tickets/{ticket_id}/comments.json?include=users"

        try:
            response = await self._get_with_auth(client, url)

            # Build a lookup map for users from side-loaded data
            users_map = {}
            for user in response.get("users", []):
                users_map[user["id"]] = user

            ticket_url = ticket.get("web_url") or self._build_ticket_url(ticket_id)
            ticket_breadcrumb = Breadcrumb(
                entity_id=str(ticket_id),
                name=ticket.get("subject", f"Ticket {ticket_id}"),
                entity_type=ZendeskTicketEntity.__name__,
            )

            for comment in response.get("comments", []):
                # Extract author information from the comment
                author_id = comment.get("author_id")

                # Handle comments without author_id or add fallback
                if not author_id:
                    author_id = 0  # Use fallback ID for system comments
                    author_name = "System"
                    author_email = None
                else:
                    # Get author name from side-loaded user data or provide fallback
                    author_name = "Unknown User"
                    author_email = None

                    if author_id in users_map:
                        user = users_map[author_id]
                        author_name = user.get("name", f"User {author_id}")
                        author_email = user.get("email")

                # Create comment name from body preview
                body = comment.get("body", "")
                comment_name = body[:50] + "..." if len(body) > 50 else body
                if not comment_name:
                    comment_name = f"Comment {comment['id']}"

                created_time = self._parse_datetime(comment.get("created_at")) or self._now()

                yield ZendeskCommentEntity(
                    # Base fields
                    entity_id=f"{ticket_id}_{comment['id']}",
                    breadcrumbs=[ticket_breadcrumb],
                    name=comment_name,
                    created_at=created_time,
                    updated_at=created_time,
                    # API fields
                    comment_id=comment["id"],
                    ticket_id=ticket_id,
                    ticket_subject=ticket["subject"],
                    author_id=author_id,
                    author_name=author_name,
                    author_email=author_email,
                    body=body,
                    html_body=comment.get("html_body"),
                    public=comment.get("public", False),
                    attachments=comment.get("attachments", []),
                    created_time=created_time,
                    web_url_value=ticket_url,
                )
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                # Ticket might not have comments or might be deleted
                self.logger.warning(f"No comments found for ticket {ticket_id}")
            else:
                raise

    async def _generate_attachment_entities(  # noqa: C901
        self, client: httpx.AsyncClient, ticket: Dict
    ) -> AsyncGenerator[BaseEntity, None]:
        """Generate attachment entities for a ticket."""
        ticket_id = ticket["id"]

        # Get ticket comments to find attachments
        url = f"https://{self.subdomain}.zendesk.com/api/v2/tickets/{ticket_id}/comments.json"

        try:
            response = await self._get_with_auth(client, url)

            ticket_breadcrumb = Breadcrumb(
                entity_id=str(ticket_id),
                name=ticket.get("subject", f"Ticket {ticket_id}"),
                entity_type=ZendeskTicketEntity.__name__,
            )

            for comment in response.get("comments", []):
                comment_created_at = self._parse_datetime(comment.get("created_at"))
                comment_breadcrumb = Breadcrumb(
                    entity_id=str(comment["id"]),
                    name=f"Comment {comment['id']}",
                    entity_type=ZendeskCommentEntity.__name__,
                )

                for attachment in comment.get("attachments", []):
                    # Ensure required fields are present before creating entity
                    if not all(
                        attachment.get(field) for field in ["id", "file_name", "content_url"]
                    ):
                        continue  # Skip attachments with missing required fields

                    # Use attachment created_at if available, otherwise fall back to comment
                    # created_at, and finally to current time if both are None
                    attachment_created_at = (
                        self._parse_datetime(attachment.get("created_at"))
                        or comment_created_at
                        or self._now()
                    )

                    # Determine file type from mime_type
                    mime_type = attachment.get("content_type") or "application/octet-stream"
                    size = attachment.get("size", 0)
                    if mime_type and "/" in mime_type:
                        file_type = mime_type.split("/")[0]
                    else:
                        import os

                        file_name = attachment.get("file_name", "")
                        ext = os.path.splitext(file_name)[1].lower().lstrip(".")
                        file_type = ext if ext else "file"

                    attachment_entity = ZendeskAttachmentEntity(
                        # Base fields
                        entity_id=str(attachment["id"]),
                        breadcrumbs=[ticket_breadcrumb, comment_breadcrumb],
                        name=attachment.get("file_name", ""),
                        created_at=attachment_created_at,
                        updated_at=attachment_created_at,
                        # File fields
                        url=attachment.get("content_url"),
                        size=size,
                        file_type=file_type,
                        mime_type=mime_type,
                        local_path=None,  # Will be set after download
                        # API fields
                        attachment_id=attachment["id"],
                        created_time=attachment_created_at,
                        updated_time=attachment_created_at,
                        web_url_value=attachment.get("content_url"),
                        ticket_id=ticket_id,
                        comment_id=comment["id"],
                        ticket_subject=ticket["subject"],
                        content_type=attachment.get("content_type"),
                        file_name=attachment.get("file_name", ""),
                        thumbnails=attachment.get("thumbnails", []),
                    )

                    # Download the file using file downloader
                    try:
                        await self.file_downloader.download_from_url(
                            entity=attachment_entity,
                            http_client_factory=self.http_client,
                            access_token_provider=self.get_access_token,
                            logger=self.logger,
                        )

                        # Verify download succeeded
                        if not attachment_entity.local_path:
                            raise ValueError(
                                f"Download failed - no local path set for {attachment_entity.name}"
                            )

                        self.logger.debug(
                            f"Successfully downloaded attachment: {attachment_entity.name}"
                        )
                        yield attachment_entity

                    except FileSkippedException as e:
                        # Attachment intentionally skipped (unsupported type, too large, etc.)
                        self.logger.debug(
                            f"Skipping attachment {attachment_entity.name}: {e.reason}"
                        )
                        continue

                    except Exception as e:
                        self.logger.error(
                            f"Failed to download attachment {attachment_entity.name}: {e}"
                        )
                        # Continue with other attachments
                        continue

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                # Ticket might not have attachments or might be deleted
                self.logger.warning(f"No attachments found for ticket {ticket_id}")
            else:
                raise

    async def generate_entities(self) -> AsyncGenerator[BaseEntity, None]:
        """Generate all entities from Zendesk."""
        async with self.http_client() as client:
            # Generate organizations first
            async for org_entity in self._generate_organization_entities(client):
                yield org_entity

            # Generate users
            async for user_entity in self._generate_user_entities(client):
                yield user_entity

            # Generate tickets
            async for ticket_entity in self._generate_ticket_entities(client):
                yield ticket_entity

                # Generate comments for each ticket
                async for comment_entity in self._generate_comment_entities(
                    client,
                    {
                        "id": ticket_entity.ticket_id,
                        "subject": ticket_entity.subject,
                        "web_url": ticket_entity.web_url,
                    },
                ):
                    yield comment_entity

                # Generate attachments for each ticket
                async for attachment_entity in self._generate_attachment_entities(
                    client,
                    {
                        "id": ticket_entity.ticket_id,
                        "subject": ticket_entity.subject,
                        "web_url": ticket_entity.web_url,
                    },
                ):
                    yield attachment_entity

    async def validate(self) -> bool:
        """Verify OAuth2 token by pinging Zendesk's /users/me endpoint."""
        # If we're in validation mode without a real subdomain, skip the actual API call
        if getattr(self, "_is_validation_mode", False):
            # For validation mode, we can't make a real API call without the subdomain
            # Just validate that we have an access token
            return bool(getattr(self, "access_token", None))

        return await self._validate_oauth2(
            ping_url=f"https://{self.subdomain}.zendesk.com/api/v2/users/me.json",
            headers={"Accept": "application/json"},
            timeout=10.0,
        )
