"""Zendesk source implementation for syncing tickets, comments, users, orgs, and attachments."""

from datetime import datetime, timezone
from typing import Any, AsyncGenerator, Dict, Optional

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from airweave.core.exceptions import TokenRefreshError
from airweave.platform.decorators import source
from airweave.platform.entities._base import ChunkEntity
from airweave.platform.entities.zendesk import (
    ZendeskAttachmentEntity,
    ZendeskCommentEntity,
    ZendeskOrganizationEntity,
    ZendeskTicketEntity,
    ZendeskUserEntity,
)
from airweave.platform.sources._base import BaseSource
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
    config_class="ZendeskConfig",
    labels=["Customer Support", "CRM"],
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
        stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10), reraise=True
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
                        self.logger.info(f"Retrying request with refreshed token: {url}")
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

    async def _generate_organization_entities(
        self, client: httpx.AsyncClient
    ) -> AsyncGenerator[ChunkEntity, None]:
        """Generate organization entities."""
        url = f"https://{self.subdomain}.zendesk.com/api/v2/organizations.json"

        # Handle pagination
        while url:
            response = await self._get_with_auth(client, url)

            for org in response.get("organizations", []):
                yield ZendeskOrganizationEntity(
                    entity_id=str(org["id"]),
                    breadcrumbs=[],
                    organization_id=org["id"],
                    name=org["name"],
                    created_at=org.get("created_at"),
                    updated_at=org.get("updated_at"),
                    domain_names=org.get("domain_names", []),
                    details=org.get("details"),
                    notes=org.get("notes"),
                    tags=org.get("tags", []),
                    custom_fields=org.get("custom_fields", []),
                    organization_fields=org.get("organization_fields", {}),
                )

            # Check for next page
            url = response.get("next_page")

    async def _generate_user_entities(
        self, client: httpx.AsyncClient
    ) -> AsyncGenerator[ChunkEntity, None]:
        """Generate user entities."""
        url = f"https://{self.subdomain}.zendesk.com/api/v2/users.json"

        # Handle pagination
        while url:
            response = await self._get_with_auth(client, url)

            for user in response.get("users", []):
                # Ensure email exists and handle required datetime fields properly
                if not user.get("email"):
                    continue  # Skip users without email

                # Parse datetime fields with fallbacks
                from datetime import datetime

                now = datetime.now()

                created_at = user.get("created_at")
                if isinstance(created_at, str):
                    from dateutil.parser import parse

                    created_at = parse(created_at)
                elif created_at is None:
                    created_at = now

                updated_at = user.get("updated_at")
                if isinstance(updated_at, str):
                    updated_at = parse(updated_at)
                elif updated_at is None:
                    updated_at = created_at

                yield ZendeskUserEntity(
                    entity_id=str(user["id"]),
                    breadcrumbs=[],
                    user_id=user["id"],
                    name=user["name"],
                    email=user["email"],
                    role=user.get("role", "end-user"),
                    active=user.get("active", True),
                    created_at=created_at,
                    updated_at=updated_at,
                    last_login_at=user.get("last_login_at"),
                    organization_id=user.get("organization_id"),
                    phone=user.get("phone"),
                    time_zone=user.get("time_zone"),
                    locale=user.get("locale"),
                    custom_fields=user.get("custom_fields", []),
                    tags=user.get("tags", []),
                    user_fields=user.get("user_fields", {}),
                )

            # Check for next page
            url = response.get("next_page")

    async def _generate_ticket_entities(
        self, client: httpx.AsyncClient
    ) -> AsyncGenerator[ChunkEntity, None]:
        """Generate ticket entities."""
        url = f"https://{self.subdomain}.zendesk.com/api/v2/tickets.json"

        # Handle pagination
        while url:
            response = await self._get_with_auth(client, url)

            for ticket in response.get("tickets", []):
                # Skip closed tickets if configured to do so
                if self.exclude_closed_tickets and ticket.get("status") == "closed":
                    continue

                yield ZendeskTicketEntity(
                    entity_id=str(ticket["id"]),
                    breadcrumbs=[],
                    ticket_id=ticket["id"],
                    subject=ticket["subject"],
                    description=ticket.get("description"),
                    requester_id=ticket.get("requester_id"),
                    requester_name=None,  # Will be populated from user data if needed
                    requester_email=None,  # Will be populated from user data if needed
                    assignee_id=ticket.get("assignee_id"),
                    assignee_name=None,  # Will be populated from user data if needed
                    assignee_email=None,  # Will be populated from user data if needed
                    status=ticket.get("status", "new"),
                    priority=ticket.get("priority"),
                    created_at=ticket.get("created_at"),
                    updated_at=ticket.get("updated_at"),
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
    ) -> AsyncGenerator[ChunkEntity, None]:
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

                yield ZendeskCommentEntity(
                    entity_id=f"{ticket_id}_{comment['id']}",
                    breadcrumbs=[],
                    comment_id=comment["id"],
                    ticket_id=ticket_id,
                    ticket_subject=ticket["subject"],
                    author_id=author_id,
                    author_name=author_name,
                    author_email=author_email,
                    body=comment.get("body", ""),
                    html_body=comment.get("html_body"),
                    public=comment.get("public", False),
                    created_at=comment.get("created_at"),
                    attachments=comment.get("attachments", []),
                )
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                # Ticket might not have comments or might be deleted
                self.logger.warning(f"No comments found for ticket {ticket_id}")
            else:
                raise

    async def _generate_attachment_entities(
        self, client: httpx.AsyncClient, ticket: Dict
    ) -> AsyncGenerator[ChunkEntity, None]:
        """Generate attachment entities for a ticket."""
        ticket_id = ticket["id"]

        # Get ticket comments to find attachments
        url = f"https://{self.subdomain}.zendesk.com/api/v2/tickets/{ticket_id}/comments.json"

        try:
            response = await self._get_with_auth(client, url)

            for comment in response.get("comments", []):
                comment_created_at = comment.get("created_at")

                for attachment in comment.get("attachments", []):
                    # Ensure required fields are present before creating entity
                    if not all(
                        attachment.get(field) for field in ["id", "file_name", "content_url"]
                    ):
                        continue  # Skip attachments with missing required fields

                    # Use attachment created_at if available, otherwise fall back to comment
                    # created_at, and finally to current time if both are None
                    attachment_created_at = attachment.get("created_at") or comment_created_at
                    if attachment_created_at is None:
                        attachment_created_at = datetime.now(timezone.utc)
                    elif isinstance(attachment_created_at, str):
                        from dateutil.parser import parse

                        attachment_created_at = parse(attachment_created_at)

                    attachment_entity = ZendeskAttachmentEntity(
                        entity_id=str(attachment["id"]),
                        breadcrumbs=[],
                        file_id=str(attachment["id"]),  # Convert to string for consistency
                        attachment_id=attachment["id"],
                        ticket_id=ticket_id,
                        comment_id=comment["id"],
                        ticket_subject=ticket["subject"],
                        name=attachment.get("file_name", ""),
                        file_name=attachment.get("file_name", ""),
                        mime_type=attachment.get("content_type"),
                        content_type=attachment.get("content_type"),
                        size=attachment.get("size", 0),
                        url=attachment.get("content_url"),
                        download_url=attachment.get("content_url"),
                        thumbnails=attachment.get("thumbnails", []),
                        created_at=attachment_created_at,
                    )

                    # Process the file entity
                    processed_entity = await self.process_file_entity(attachment_entity)
                    if processed_entity:
                        yield processed_entity

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                # Ticket might not have attachments or might be deleted
                self.logger.warning(f"No attachments found for ticket {ticket_id}")
            else:
                raise

    async def generate_entities(self) -> AsyncGenerator[ChunkEntity, None]:
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
                    client, {"id": ticket_entity.ticket_id, "subject": ticket_entity.subject}
                ):
                    yield comment_entity

                # Generate attachments for each ticket
                async for attachment_entity in self._generate_attachment_entities(
                    client, {"id": ticket_entity.ticket_id, "subject": ticket_entity.subject}
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
