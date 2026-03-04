"""Airtable source implementation for syncing bases, tables, records, and comments."""

from typing import Any, AsyncGenerator, Dict, List, Optional

import httpx
from tenacity import retry, stop_after_attempt

from airweave.core.exceptions import TokenRefreshError
from airweave.core.shared_models import RateLimitLevel
from airweave.platform.configs.auth import AirtableAuthConfig
from airweave.platform.configs.config import AirtableConfig
from airweave.platform.decorators import source
from airweave.platform.entities._base import BaseEntity, Breadcrumb
from airweave.platform.entities.airtable import (
    AirtableAttachmentEntity,
    AirtableBaseEntity,
    AirtableCommentEntity,
    AirtableRecordEntity,
    AirtableTableEntity,
    AirtableUserEntity,
)
from airweave.platform.sources._base import BaseSource
from airweave.platform.sources.retry_helpers import (
    retry_if_rate_limit_or_timeout,
    wait_rate_limit_with_backoff,
)
from airweave.platform.storage import FileSkippedException
from airweave.schemas.source_connection import AuthenticationMethod, OAuthType


@source(
    name="Airtable",
    short_name="airtable",
    auth_methods=[
        AuthenticationMethod.OAUTH_BROWSER,
        AuthenticationMethod.OAUTH_TOKEN,
        AuthenticationMethod.AUTH_PROVIDER,
    ],
    oauth_type=OAuthType.WITH_REFRESH,
    auth_config_class=AirtableAuthConfig,
    config_class=AirtableConfig,
    labels=["Database", "Spreadsheet"],
    supports_continuous=False,
    rate_limit_level=RateLimitLevel.ORG,
)
class AirtableSource(BaseSource):
    """Airtable source connector integrates with the Airtable API to extract and synchronize data.

    Connects to your Airtable bases and syncs everything by default:
    - User info (authenticated user)
    - All accessible bases
    - All tables in each base
    - All records in each table
    - All comments on each record
    - All attachments in each record

    No configuration needed - just connect and sync!
    """

    API_BASE = "https://api.airtable.com/v0"

    @classmethod
    async def create(
        cls, access_token: str, config: Optional[Dict[str, Any]] = None
    ) -> "AirtableSource":
        """Create a new Airtable source.

        Args:
            access_token: OAuth access token for Airtable API
            config: Optional configuration parameters (currently unused)

        Returns:
            Configured AirtableSource instance
        """
        instance = cls()
        instance.access_token = access_token
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
        """Make authenticated GET request to Airtable API with token manager support.

        This method uses the token manager for authentication and handles
        401 errors by refreshing the token and retrying. Also handles 429 rate limits.

        Rate limits:
        - 5 requests/second per base (enforced by Airtable)
        - 50 requests/second for all PAT traffic
        - 429 responses include Retry-After header (typically 30 seconds)

        Args:
            client: HTTP client to use for the request
            url: API endpoint URL
            params: Optional query parameters

        Returns:
            JSON response data

        Raises:
            httpx.HTTPStatusError: For 4xx/5xx responses after retries
            ValueError: If no access token is available
        """
        # Get a valid token (will refresh if needed)
        access_token = await self.get_access_token()
        if not access_token:
            raise ValueError("No access token available")

        headers = {"Authorization": f"Bearer {access_token}"}

        try:
            response = await client.get(url, headers=headers, params=params, timeout=30.0)

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
                        self.logger.info(f"Retrying request with refreshed token: {url}")
                        response = await client.get(
                            url, headers=headers, params=params, timeout=30.0
                        )

                    except TokenRefreshError as e:
                        self.logger.error(f"Failed to refresh token: {str(e)}")
                        response.raise_for_status()
                else:
                    # No token manager, can't refresh
                    self.logger.error("No token manager available to refresh expired token")
                    response.raise_for_status()

            # Handle 429 Rate Limit
            if response.status_code == 429:
                retry_after = response.headers.get("Retry-After", "30")
                self.logger.warning(
                    f"Rate limit hit for {url}, waiting {retry_after} seconds before retry"
                )
                import asyncio

                await asyncio.sleep(float(retry_after))
                # Retry after waiting
                response = await client.get(url, headers=headers, params=params, timeout=30.0)

            # Raise for other HTTP errors
            response.raise_for_status()
            return response.json()

        except httpx.HTTPStatusError as e:
            self._handle_http_error(e, url)
            raise
        except Exception as e:
            self.logger.error(f"Unexpected error accessing Airtable API: {url}, {str(e)}")
            raise

    def _handle_http_error(self, error: httpx.HTTPStatusError, url: str) -> None:
        """Handle HTTP errors with specific error messages.

        Critical errors (400, 401, 403, 500, 502) get detailed logging.
        """
        status = error.response.status_code
        error_messages = {
            400: "BAD_REQUEST - Invalid request format",
            401: "UNAUTHORIZED - Authentication failed",
            403: "FORBIDDEN - No permission for resource",
            500: "SERVER_ERROR - Airtable server issue",
            502: "SERVER_ERROR - Airtable server issue",
        }

        error_type = error_messages.get(status, f"HTTP_ERROR_{status}")
        self.logger.error(f"{error_type} ({status}) for {url}")

    async def _get_user_info(self, client: httpx.AsyncClient) -> Optional[Dict[str, Any]]:
        """Get authenticated user information from whoami endpoint."""
        url = f"{self.API_BASE}/meta/whoami"

        try:
            return await self._get_with_auth(client, url)
        except Exception as e:
            self.logger.warning(f"Failed to get user info: {e}")
            return None

    async def _list_bases(self, client: httpx.AsyncClient) -> AsyncGenerator[Dict[str, Any], None]:
        """List all accessible bases via Meta API with pagination."""
        url = f"{self.API_BASE}/meta/bases"
        params: Dict[str, Any] = {}

        while True:
            try:
                data = await self._get_with_auth(client, url, params=params)
                bases = data.get("bases", [])

                for base in bases:
                    yield base

                # Check for pagination
                offset = data.get("offset")
                if not offset:
                    break
                params["offset"] = offset

            except Exception as e:
                self.logger.error(f"Error listing bases: {e}")
                break

    async def _get_base_schema(self, client: httpx.AsyncClient, base_id: str) -> Dict[str, Any]:
        """Get the schema for a specific base including tables and fields."""
        url = f"{self.API_BASE}/meta/bases/{base_id}/tables"
        return await self._get_with_auth(client, url)

    async def _list_records(
        self,
        client: httpx.AsyncClient,
        base_id: str,
        table_id_or_name: str,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """List all records in a table with pagination."""
        url = f"{self.API_BASE}/{base_id}/{table_id_or_name}"
        params: Dict[str, Any] = {"pageSize": 100}

        while True:
            try:
                data = await self._get_with_auth(client, url, params=params)
                records = data.get("records", [])

                for record in records:
                    yield record

                # Check for pagination
                offset = data.get("offset")
                if not offset:
                    break
                params["offset"] = offset

            except Exception as e:
                self.logger.error(f"Error listing records for {base_id}/{table_id_or_name}: {e}")
                break

    async def _list_comments(
        self, client: httpx.AsyncClient, base_id: str, table_id: str, record_id: str
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """List all comments for a record with pagination."""
        url = f"{self.API_BASE}/{base_id}/{table_id}/{record_id}/comments"
        params: Dict[str, Any] = {"pageSize": 100}

        while True:
            try:
                data = await self._get_with_auth(client, url, params=params)
                comments = data.get("comments", [])

                for comment in comments:
                    yield comment

                # Check for pagination
                offset = data.get("offset")
                if not offset:
                    break
                params["offset"] = offset

            except Exception as e:
                self.logger.warning(f"Error listing comments for {record_id}: {e}")
                break

    async def _generate_base_entities(
        self, client: httpx.AsyncClient
    ) -> AsyncGenerator[BaseEntity, None]:
        """Generate base entities.

        Note: Bases must already exist in Airtable. The API does not provide
        endpoints to create bases programmatically (requires special permissions).
        We list all accessible bases via the Meta API.

        This is a fundamental Airtable API limitation - all connectors
        (tables, records) are created within existing bases.
        """
        # List all accessible bases
        async for base in self._list_bases(client):
            try:
                base_id = base.get("id")
                if not base_id:
                    continue

                yield AirtableBaseEntity(
                    base_id=base_id,
                    breadcrumbs=[],
                    name=base.get("name", base_id),
                    permission_level=base.get("permissionLevel"),
                    url=f"https://airtable.com/{base_id}",
                )
            except Exception as e:
                self.logger.error(f"Error creating base entity: {e}")

    async def _generate_table_entities(
        self, client: httpx.AsyncClient, base_id: str, base_name: str, base_breadcrumb: Breadcrumb
    ) -> AsyncGenerator[BaseEntity, None]:
        """Generate table entities for a base."""
        try:
            schema = await self._get_base_schema(client, base_id)
            tables = schema.get("tables", [])

            for table in tables:
                table_id = table.get("id")
                table_name = table.get("name")

                if not table_id:
                    continue

                # Get primary field name if available
                primary_field_name = None
                fields = table.get("fields", [])
                for field in fields:
                    if field.get("type") == "primaryField" or field.get("isPrimary"):
                        primary_field_name = field.get("name")
                        break
                if not primary_field_name and fields:
                    # First field is usually the primary
                    primary_field_name = fields[0].get("name")

                yield AirtableTableEntity(
                    table_id=table_id,
                    breadcrumbs=[base_breadcrumb],
                    name=table_name or table_id,
                    base_id=base_id,
                    description=table.get("description"),
                    fields_schema=fields,
                    primary_field_name=primary_field_name,
                    view_count=len(table.get("views", [])),
                )

        except Exception as e:
            self.logger.error(f"Error generating table entities for base {base_id}: {e}")

    async def _generate_comment_entities(
        self,
        client: httpx.AsyncClient,
        base_id: str,
        table_id: str,
        record: Dict[str, Any],
        record_breadcrumbs: List[Breadcrumb],
    ) -> AsyncGenerator[BaseEntity, None]:
        """Generate comment entities for a record."""
        record_id = record.get("id")
        if not record_id:
            return

        try:
            async for comment in self._list_comments(client, base_id, table_id, record_id):
                comment_id = comment.get("id")
                if not comment_id:
                    continue

                author = comment.get("author", {})
                comment_text = comment.get("text", "")

                # Create comment name from text preview
                comment_name = comment_text[:50] + "..." if len(comment_text) > 50 else comment_text
                if not comment_name:
                    comment_name = f"Comment {comment_id}"

                yield AirtableCommentEntity(
                    comment_id=comment_id,
                    breadcrumbs=record_breadcrumbs,
                    name=comment_name,
                    created_at=comment.get("createdTime"),
                    updated_at=comment.get("lastUpdatedTime"),
                    record_id=record_id,
                    base_id=base_id,
                    table_id=table_id,
                    text=comment_text,
                    author_id=author.get("id"),
                    author_email=author.get("email"),
                    author_name=author.get("name"),
                )

        except Exception as e:
            self.logger.warning(f"Error generating comment entities for record {record_id}: {e}")

    def _create_attachment_entity(
        self,
        attachment: Dict[str, Any],
        base_id: str,
        table_id: str,
        table_name: str,
        record_id: str,
        field_name: str,
        record_breadcrumbs: List[Breadcrumb],
    ) -> Optional[AirtableAttachmentEntity]:
        """Create an attachment entity from attachment data."""
        url = attachment.get("url")
        if not url:
            return None

        att_id = attachment.get("id", f"{record_id}:{field_name}")
        filename = attachment.get("filename") or attachment.get("name") or "attachment"
        mime_type = attachment.get("type") or "application/octet-stream"
        size = attachment.get("size", 0)

        # Determine file type from mime_type
        file_type = mime_type.split("/")[0] if "/" in mime_type else "file"

        return AirtableAttachmentEntity(
            attachment_id=att_id,
            breadcrumbs=record_breadcrumbs,
            name=filename,
            # File fields
            url=url,
            size=size,
            file_type=file_type,
            mime_type=mime_type,
            local_path=None,  # Will be set after download
            # API fields
            base_id=base_id,
            table_id=table_id,
            table_name=table_name,
            record_id=record_id,
            field_name=field_name,
        )

    async def _generate_attachment_entities(
        self,
        client: httpx.AsyncClient,
        base_id: str,
        table_id: str,
        table_name: str,
        record: Dict[str, Any],
        record_breadcrumbs: List[Breadcrumb],
    ) -> AsyncGenerator[BaseEntity, None]:
        """Generate attachment entities for a record."""
        record_id = record.get("id")
        if not record_id:
            return

        fields = record.get("fields", {})

        # Look for attachment fields
        for field_name, field_value in fields.items():
            if not isinstance(field_value, list):
                continue

            for attachment in field_value:
                if not isinstance(attachment, dict):
                    continue

                # Create attachment entity
                file_entity = self._create_attachment_entity(
                    attachment,
                    base_id,
                    table_id,
                    table_name,
                    record_id,
                    field_name,
                    record_breadcrumbs,
                )
                if not file_entity:
                    continue

                # Download the file using file downloader
                try:
                    # Airtable URLs expire after 2 hours, so download immediately
                    await self.file_downloader.download_from_url(
                        entity=file_entity,
                        http_client_factory=self.http_client,
                        access_token_provider=self.get_access_token,
                        logger=self.logger,
                    )

                    # Verify download succeeded
                    if not file_entity.local_path:
                        raise ValueError(
                            f"Download failed - no local path set for {file_entity.name}"
                        )

                    self.logger.debug(f"Successfully downloaded attachment: {file_entity.name}")
                    yield file_entity

                except FileSkippedException as e:
                    # File intentionally skipped (unsupported type, too large, etc.) - not an error
                    self.logger.debug(f"Skipping file: {e.reason}")
                    continue

                except Exception as e:
                    self.logger.error(f"Error downloading attachment {file_entity.name}: {e}")

    async def generate_entities(self) -> AsyncGenerator[BaseEntity, None]:  # noqa: C901
        """Generate all entities from Airtable."""
        async with self.http_client() as client:
            # First, yield the user entity
            user_info = await self._get_user_info(client)
            if user_info:
                try:
                    user_id = user_info.get("id", "unknown")
                    email = user_info.get("email")
                    user_name = email or user_id

                    yield AirtableUserEntity(
                        user_id=user_id,
                        display_name=user_name,
                        breadcrumbs=[],
                        email=email,
                        scopes=user_info.get("scopes"),
                    )
                except Exception as e:
                    self.logger.warning(f"Failed to create user entity: {e}")

            # Generate base entities
            async for base_entity in self._generate_base_entities(client):
                yield base_entity

                base_id = base_entity.base_id
                base_name = base_entity.name

                base_breadcrumb = Breadcrumb(
                    entity_id=base_id,
                    name=base_name,
                    entity_type="AirtableBaseEntity",
                )

                # Generate table entities for this base
                async for table_entity in self._generate_table_entities(
                    client, base_id, base_name, base_breadcrumb
                ):
                    yield table_entity

                    table_id = table_entity.table_id
                    table_name = table_entity.name

                    table_breadcrumb = Breadcrumb(
                        entity_id=table_id,
                        name=table_name,
                        entity_type="AirtableTableEntity",
                    )
                    table_breadcrumbs = [base_breadcrumb, table_breadcrumb]

                    # Generate record entities for this table
                    async for record in self._list_records(client, base_id, table_id):
                        record_id = record.get("id")
                        if not record_id:
                            continue

                        # Get record name from first non-empty field value or record ID
                        fields = record.get("fields", {})
                        record_name = record_id
                        if fields:
                            # Try to get first field value as name
                            for value in fields.values():
                                if isinstance(value, str) and value.strip():
                                    record_name = value.strip()[:100]  # Truncate to 100 chars
                                    break
                                elif value and not isinstance(value, (dict, list)):
                                    record_name = str(value)[:100]
                                    break

                        # Yield the record entity
                        record_entity = AirtableRecordEntity(
                            record_id=record_id,
                            breadcrumbs=table_breadcrumbs,
                            name=record_name,
                            created_at=record.get("createdTime"),
                            base_id=base_id,
                            table_id=table_id,
                            table_name=table_name,
                            fields=fields,
                        )
                        yield record_entity

                        record_breadcrumb = Breadcrumb(
                            entity_id=record_id,
                            name=record_name,
                            entity_type="AirtableRecordEntity",
                        )
                        record_breadcrumbs = [*table_breadcrumbs, record_breadcrumb]

                        # Generate comment entities for this record
                        async for comment_entity in self._generate_comment_entities(
                            client, base_id, table_id, record, record_breadcrumbs
                        ):
                            yield comment_entity

                        # Generate attachment entities for this record
                        async for attachment_entity in self._generate_attachment_entities(
                            client, base_id, table_id, table_name, record, record_breadcrumbs
                        ):
                            yield attachment_entity

    async def validate(self) -> bool:
        """Verify OAuth2 token by pinging Airtable's bases endpoint."""
        return await self._validate_oauth2(
            ping_url=f"{self.API_BASE}/meta/bases",
            headers={"Accept": "application/json"},
            timeout=10.0,
        )
