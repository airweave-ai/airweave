"""Outlook Mail source implementation.

Simplified version that retrieves:
  - All mail folders (hierarchical discovery)
  - Messages from all folders
  - Attachments

Follows the same structure as the Gmail connector implementation.
"""


from __future__ import annotations

import base64
from datetime import datetime
from typing import TYPE_CHECKING, Any, AsyncGenerator, Dict, List, Optional

from tenacity import retry, stop_after_attempt

from airweave.core.logging import ContextualLogger
from airweave.core.shared_models import RateLimitLevel
from airweave.domains.browse_tree.types import NodeSelectionData
from airweave.domains.sources.exceptions import SourceAuthError, SourceEntityNotFoundError
from airweave.domains.sources.token_providers.protocol import TokenProviderProtocol
from airweave.domains.storage import FileSkippedException
from airweave.domains.storage.file_service import FileService
from airweave.domains.syncs.cursors.cursor import SyncCursor
from airweave.platform.configs.config import OutlookMailConfig
from airweave.platform.cursors import OutlookMailCursor
from airweave.platform.decorators import source
from airweave.platform.entities._base import BaseEntity, Breadcrumb
from airweave.platform.entities.outlook_mail import (
    OutlookAttachmentEntity,
    OutlookMailFolderDeletionEntity,
    OutlookMailFolderEntity,
    OutlookMessageDeletionEntity,
    OutlookMessageEntity,
)
from airweave.platform.http_client.airweave_client import AirweaveHttpClient
from airweave.platform.sources._base import BaseSource
from airweave.platform.sources.http_helpers import raise_for_status
from airweave.platform.sources.retry_helpers import (
    retry_if_rate_limit_or_timeout,
    wait_rate_limit_with_backoff,
)
from airweave.platform.utils.filename_utils import safe_filename
from airweave.schemas.source_connection import AuthenticationMethod, OAuthType

if TYPE_CHECKING:
    from airweave.domains.sync_pipeline.source_hash_lookup import SourceHashLookup


@source(
    name="Outlook Mail",
    short_name="outlook_mail",
    auth_methods=[
        AuthenticationMethod.OAUTH_BROWSER,
        AuthenticationMethod.OAUTH_TOKEN,
        AuthenticationMethod.AUTH_PROVIDER,
    ],
    oauth_type=OAuthType.WITH_REFRESH,
    auth_config_class=None,
    config_class=OutlookMailConfig,
    labels=["Communication", "Email"],
    supports_continuous=True,
    rate_limit_level=RateLimitLevel.ORG,
    cursor_class=OutlookMailCursor,
)
class OutlookMailSource(BaseSource):
    """Outlook Mail source connector integrates with the Microsoft Graph API to extract email data.

    Synchronizes data from Outlook mailboxes.

    It provides comprehensive access to mail folders, messages, and
    attachments with hierarchical folder organization and content processing capabilities.
    """

    GRAPH_BASE_URL = "https://graph.microsoft.com/v1.0"

    @classmethod
    async def create(
        cls,
        *,
        auth: TokenProviderProtocol,
        logger: ContextualLogger,
        http_client: AirweaveHttpClient,
        config: OutlookMailConfig,
    ) -> "OutlookMailSource":
        """Create a new Outlook Mail source instance."""
        instance = cls(auth=auth, logger=logger, http_client=http_client)
        instance.after_date = config.after_date
        instance.included_folders = config.included_folders
        instance.excluded_folders = config.excluded_folders
        return instance

    # ------------------------------------------------------------------
    # HTTP helpers
    # ------------------------------------------------------------------

    async def _authed_headers(self) -> Dict[str, str]:
        """Build Authorization header with a fresh token."""
        token = await self.auth.get_token()
        return {"Authorization": f"Bearer {token}"}

    async def _refresh_and_get_headers(self) -> Dict[str, str]:
        """Force-refresh the token and return updated headers."""
        new_token = await self.auth.force_refresh()
        return {"Authorization": f"Bearer {new_token}"}

    @retry(
        stop=stop_after_attempt(5),
        retry=retry_if_rate_limit_or_timeout,
        wait=wait_rate_limit_with_backoff,
        reraise=True,
    )
    async def _get(self, url: str, params: Optional[dict] = None) -> dict:
        """Make an authenticated GET request to Microsoft Graph API."""
        self.logger.debug(f"Making authenticated GET request to: {url} with params: {params}")

        headers = await self._authed_headers()
        response = await self.http_client.get(url, headers=headers, params=params)

        if response.status_code == 401 and self.auth.supports_refresh:
            self.logger.warning(
                f"Got 401 Unauthorized from Microsoft Graph API at {url}, refreshing token..."
            )
            headers = await self._refresh_and_get_headers()
            response = await self.http_client.get(url, headers=headers, params=params)

        raise_for_status(
            response,
            source_short_name=self.short_name,
            token_provider_kind=self.auth.provider_kind,
        )
        data = response.json()
        self.logger.debug(f"Received response from {url} - Status: {response.status_code}")
        return data

    # ------------------------------------------------------------------
    # Cursor helpers
    # ------------------------------------------------------------------

    def _update_folder_cursor(
        self,
        delta_link: str,
        folder_id: str,
        folder_name: str,
        cursor: SyncCursor | None,
    ) -> None:
        """Update cursor with delta link for a specific folder."""
        if not cursor:
            return

        cursor_data = cursor.data
        folder_links = cursor_data.get("folder_delta_links", {})
        folder_names = cursor_data.get("folder_names", {})
        folder_last_sync = cursor_data.get("folder_last_sync", {})

        folder_links[folder_id] = delta_link
        folder_names[folder_id] = folder_name
        folder_last_sync[folder_id] = datetime.utcnow().isoformat()

        cursor.update(
            delta_link=delta_link,
            folder_id=folder_id,
            folder_name=folder_name,
            last_sync=datetime.utcnow().isoformat(),
            folder_delta_links=folder_links,
            folder_names=folder_names,
            folder_last_sync=folder_last_sync,
        )

    # ------------------------------------------------------------------
    # Filter helpers
    # ------------------------------------------------------------------

    def _should_process_folder(self, folder_data: Dict[str, Any]) -> bool:
        """Check if folder should be processed based on configured filters."""
        well_known_name = folder_data.get("wellKnownName", "").lower()
        display_name = folder_data.get("displayName", "").lower()

        if not well_known_name:
            return True

        included_folders = getattr(self, "included_folders", [])
        excluded_folders = getattr(self, "excluded_folders", [])

        if excluded_folders and well_known_name in [f.lower() for f in excluded_folders]:
            self.logger.debug(f"Skipping folder {display_name} - matches excluded folders")
            return False

        if included_folders:
            if well_known_name not in [f.lower() for f in included_folders]:
                self.logger.debug(
                    f"Skipping folder {display_name} - doesn't match included folders"
                )
                return False

        return True

    def _message_matches_date_filter(self, message_data: Dict[str, Any]) -> bool:
        """Check if message matches after_date filter."""
        after_date = getattr(self, "after_date", None)
        if not after_date:
            return True

        received_date_str = message_data.get("receivedDateTime")
        if not received_date_str:
            return True

        try:
            received_date = datetime.fromisoformat(received_date_str.replace("Z", "+00:00"))
            after_dt = datetime.strptime(after_date, "%Y/%m/%d")
            from datetime import timezone

            after_dt = after_dt.replace(tzinfo=timezone.utc)

            if received_date < after_dt:
                self.logger.debug(f"Message {message_data.get('id')} skipped: before after_date")
                return False
        except (ValueError, TypeError) as e:
            self.logger.warning(f"Failed to parse date for message {message_data.get('id')}: {e}")

        return True

    # ------------------------------------------------------------------
    # Folder processing
    # ------------------------------------------------------------------

    async def _process_folder_messages(
        self,
        folder_entity: OutlookMailFolderEntity,
        folder_breadcrumb: Breadcrumb,
        files: FileService | None = None,
    ) -> AsyncGenerator[BaseEntity, None]:
        """Process messages in a folder and handle errors gracefully."""
        self.logger.debug(f"Processing messages in folder: {folder_entity.display_name}")
        try:
            async for entity in self._generate_message_entities(
                folder_entity, folder_breadcrumb, files=files
            ):
                yield entity
        except SourceAuthError:
            raise
        except Exception as e:
            self.logger.warning(
                f"Error processing messages in folder {folder_entity.display_name}: {str(e)}"
            )

    async def _process_child_folders(
        self,
        folder_entity: OutlookMailFolderEntity,
        parent_breadcrumbs: List[Breadcrumb],
        folder_breadcrumb: Breadcrumb,
        cursor: SyncCursor | None = None,
        files: FileService | None = None,
    ) -> AsyncGenerator[OutlookMailFolderEntity, None]:
        """Process child folders recursively and handle errors gracefully."""
        if folder_entity.child_folder_count > 0:
            self.logger.debug(
                f"Folder {folder_entity.display_name} has "
                f"{folder_entity.child_folder_count} child folders, recursively processing"
            )
            try:
                async for child_entity in self._generate_folder_entities(
                    folder_id=folder_entity.id,
                    parent_breadcrumbs=parent_breadcrumbs + [folder_breadcrumb],
                    cursor=cursor,
                    files=files,
                ):
                    yield child_entity
            except SourceAuthError:
                raise
            except Exception as e:
                self.logger.warning(
                    f"Error processing child folders of {folder_entity.display_name}: {str(e)}"
                )

    async def _init_and_store_message_delta_for_folder(
        self,
        folder_entity: OutlookMailFolderEntity,
        cursor: SyncCursor | None = None,
    ) -> None:
        """Initialize the per-folder message delta link and store it in the cursor."""
        try:
            delta_url = f"{self.GRAPH_BASE_URL}/me/mailFolders/{folder_entity.id}/messages/delta"
            self.logger.debug(f"Calling delta endpoint: {delta_url}")
            delta_data = await self._get(delta_url)

            attempts = 0
            max_attempts = 1000
            while attempts < max_attempts:
                attempts += 1
                if isinstance(delta_data, dict) and "@odata.deltaLink" in delta_data:
                    delta_link = delta_data["@odata.deltaLink"]
                    self.logger.debug(
                        f"Storing delta link for folder: {folder_entity.display_name}"
                    )
                    self._update_folder_cursor(
                        delta_link, folder_entity.id, folder_entity.display_name, cursor
                    )
                    break

                next_link = (
                    delta_data.get("@odata.nextLink") if isinstance(delta_data, dict) else None
                )
                if next_link:
                    self.logger.debug(
                        f"Following delta pagination nextLink for folder "
                        f"{folder_entity.display_name}"
                    )
                    delta_data = await self._get(next_link)
                else:
                    self.logger.warning(
                        f"No deltaLink or nextLink received for folder "
                        f"{folder_entity.display_name} while initializing delta."
                    )
                    break
        except SourceAuthError:
            raise
        except Exception as e:
            self.logger.warning(
                f"Failed to get delta token for folder {folder_entity.display_name}: {str(e)}"
            )

    async def _process_single_folder_tree(
        self,
        folder: Dict[str, Any],
        parent_breadcrumbs: List[Breadcrumb],
        cursor: SyncCursor | None = None,
        files: FileService | None = None,
    ) -> AsyncGenerator[BaseEntity, None]:
        """Yield the folder entity, its messages, initialize delta, then recurse children."""
        if not self._should_process_folder(folder):
            self.logger.debug(f"Skipping folder {folder.get('displayName')} due to folder filters")
            return

        folder_entity = OutlookMailFolderEntity(
            id=folder["id"],
            breadcrumbs=parent_breadcrumbs,
            display_name=folder["displayName"],
            parent_folder_id=folder.get("parentFolderId"),
            child_folder_count=folder.get("childFolderCount", 0),
            total_item_count=folder.get("totalItemCount", 0),
            unread_item_count=folder.get("unreadItemCount", 0),
            well_known_name=folder.get("wellKnownName"),
        )

        self.logger.debug(
            f"Processing folder: {folder_entity.display_name} "
            f"(ID: {folder_entity.id}, Items: {folder_entity.total_item_count})"
        )
        yield folder_entity

        folder_breadcrumb = Breadcrumb(
            entity_id=folder_entity.id,
            name=folder_entity.display_name,
            entity_type="OutlookMailFolderEntity",
        )

        async for entity in self._process_folder_messages(
            folder_entity, folder_breadcrumb, files=files
        ):
            yield entity

        await self._init_and_store_message_delta_for_folder(folder_entity, cursor=cursor)

        async for child_entity in self._process_child_folders(
            folder_entity, parent_breadcrumbs, folder_breadcrumb, cursor=cursor, files=files
        ):
            yield child_entity

    async def _generate_folder_entities(
        self,
        folder_id: Optional[str] = None,
        parent_breadcrumbs: Optional[List[Breadcrumb]] = None,
        cursor: SyncCursor | None = None,
        files: FileService | None = None,
    ) -> AsyncGenerator[OutlookMailFolderEntity, None]:
        """Recursively generate OutlookMailFolderEntity objects.

        Traverses the mail folder hierarchy via Microsoft Graph.
        """
        if parent_breadcrumbs is None:
            parent_breadcrumbs = []

        if folder_id:
            url = f"{self.GRAPH_BASE_URL}/me/mailFolders/{folder_id}/childFolders"
            self.logger.debug(f"Fetching child folders for folder ID: {folder_id}")
        else:
            url = f"{self.GRAPH_BASE_URL}/me/mailFolders"
            self.logger.debug("Fetching top-level mail folders")

        try:
            while url:
                self.logger.debug(f"Making request to: {url}")
                data = await self._get(url)
                folders = data.get("value", [])
                self.logger.debug(f"Retrieved {len(folders)} folders")

                for folder in folders:
                    async for entity in self._process_single_folder_tree(
                        folder, parent_breadcrumbs, cursor=cursor, files=files
                    ):
                        yield entity

                next_link = data.get("@odata.nextLink")
                if next_link:
                    self.logger.debug(f"Following pagination link: {next_link}")
                url = next_link if next_link else None

        except SourceAuthError:
            raise
        except Exception as e:
            self.logger.warning(f"Error fetching folders: {str(e)}")
            raise

    # ------------------------------------------------------------------
    # Message processing
    # ------------------------------------------------------------------

    async def _generate_message_entities(  # noqa: C901
        self,
        folder_entity: OutlookMailFolderEntity,
        folder_breadcrumb: Breadcrumb,
        files: FileService | None = None,
    ) -> AsyncGenerator[BaseEntity, None]:
        """Generate OutlookMessageEntity objects and their attachments for a given folder."""
        if folder_entity.total_item_count == 0:
            self.logger.debug(f"Skipping folder {folder_entity.display_name} - no messages")
            return

        self.logger.debug(
            f"Starting message generation for folder: {folder_entity.display_name} "
            f"({folder_entity.total_item_count} items)"
        )

        url = f"{self.GRAPH_BASE_URL}/me/mailFolders/{folder_entity.id}/messages"
        params = {"$top": 50}

        page_count = 0
        message_count = 0

        try:
            while url:
                page_count += 1
                self.logger.debug(
                    f"Fetching message list page #{page_count} for folder "
                    f"{folder_entity.display_name}"
                )
                data = await self._get(url, params=params)
                messages = data.get("value", [])
                self.logger.debug(
                    f"Found {len(messages)} messages on page {page_count} in folder "
                    f"{folder_entity.display_name}"
                )

                for msg_idx, message_data in enumerate(messages):
                    message_count += 1
                    message_id = message_data.get("id", "unknown")
                    self.logger.debug(
                        f"Processing message #{msg_idx + 1}/{len(messages)} (ID: {message_id}) "
                        f"in folder {folder_entity.display_name}"
                    )

                    if not self._message_matches_date_filter(message_data):
                        self.logger.debug(
                            f"Skipping message {message_id} - doesn't match date filter"
                        )
                        continue

                    if "body" not in message_data:
                        self.logger.debug(f"Fetching full message details for {message_id}")
                        message_url = f"{self.GRAPH_BASE_URL}/me/messages/{message_id}"
                        try:
                            message_data = await self._get(message_url)
                        except SourceEntityNotFoundError:
                            self.logger.warning(f"Message {message_id} not found (404) - skipping")
                            continue

                    try:
                        async for entity in self._process_message(
                            message_data, folder_entity.display_name, folder_breadcrumb, files=files
                        ):
                            yield entity
                    except SourceAuthError:
                        raise
                    except Exception as e:
                        self.logger.warning(f"Error processing message {message_id}: {str(e)}")

                url = data.get("@odata.nextLink")
                if url:
                    self.logger.debug("Following pagination to next page")
                    params = None
                else:
                    self.logger.debug(
                        f"Completed folder {folder_entity.display_name}. "
                        f"Processed {message_count} messages in {page_count} pages."
                    )
                    break

        except SourceAuthError:
            raise
        except Exception as e:
            self.logger.warning(
                f"Error processing messages in folder {folder_entity.display_name}: {str(e)}"
            )
            raise

    async def _process_message(
        self,
        message_data: Dict,
        folder_name: str,
        folder_breadcrumb: Breadcrumb,
        files: FileService | None = None,
    ) -> AsyncGenerator[BaseEntity, None]:
        """Process a message and its attachments."""
        message_id = message_data["id"]
        self.logger.debug(f"Processing message ID: {message_id} in folder: {folder_name}")

        message_entity = OutlookMessageEntity.from_api(
            message_data, folder_name=folder_name, folder_breadcrumb=folder_breadcrumb
        )

        body_obj = message_data.get("body") or {}
        body_content = body_obj.get("content", "")
        is_plain_text = body_obj.get("contentType", "html").lower() == "text"

        try:
            if body_content and files:
                file_extension = ".txt" if is_plain_text else ".html"
                filename = safe_filename(message_entity.name, file_extension)
                await files.save_bytes(
                    entity=message_entity,
                    content=body_content.encode("utf-8"),
                    filename_with_extension=filename,
                    logger=self.logger,
                )
        except FileSkippedException as e:
            self.logger.debug(f"Skipping message body for {message_id}: {e.reason}")
            return

        yield message_entity
        self.logger.debug(f"Message entity yielded for {message_id}")

        message_breadcrumb = Breadcrumb(
            entity_id=message_id,
            name=message_entity.subject,
            entity_type="OutlookMessageEntity",
        )

        if message_entity.has_attachments:
            self.logger.debug(f"Message {message_id} has attachments, processing them")
            attachment_count = 0
            try:
                async for attachment_entity in self._process_attachments(
                    message_id,
                    [folder_breadcrumb, message_breadcrumb],
                    message_entity.web_url,
                    files=files,
                ):
                    attachment_count += 1
                    self.logger.debug(
                        f"Yielding attachment #{attachment_count} from message {message_id}"
                    )
                    yield attachment_entity
                self.logger.debug(
                    f"Processed {attachment_count} attachments for message {message_id}"
                )
            except SourceAuthError:
                raise
            except Exception as e:
                self.logger.warning(
                    f"Error processing attachments for message {message_id}: {str(e)}"
                )

    # ------------------------------------------------------------------
    # Attachment processing
    # ------------------------------------------------------------------

    async def _fetch_attachment_content(self, message_id: str, attachment_id: str) -> Optional[str]:
        """Fetch attachment content from Microsoft Graph API."""
        self.logger.debug(f"Fetching content for attachment {attachment_id}")
        attachment_url = (
            f"{self.GRAPH_BASE_URL}/me/messages/{message_id}/attachments/{attachment_id}"
        )
        attachment_data = await self._get(attachment_url)
        return attachment_data.get("contentBytes")

    async def _process_single_attachment(  # noqa: C901
        self,
        attachment: Dict,
        message_id: str,
        breadcrumbs: List[Breadcrumb],
        att_idx: int,
        total_attachments: int,
        message_web_url: Optional[str],
        files: FileService | None = None,
    ) -> Optional[OutlookAttachmentEntity]:
        """Process a single attachment and return the processed entity."""
        attachment_id = attachment["id"]
        attachment_type = attachment.get("@odata.type", "")
        attachment_name = attachment.get("name", "unknown")

        self.logger.debug(
            f"Processing attachment #{att_idx + 1}/{total_attachments} "
            f"(ID: {attachment_id}, Name: {attachment_name}, Type: {attachment_type})"
        )

        if "#microsoft.graph.fileAttachment" not in attachment_type:
            self.logger.debug(
                f"Skipping non-file attachment: {attachment_name} (type: {attachment_type})"
            )
            return None

        try:
            content_bytes = attachment.get("contentBytes")
            if not content_bytes:
                try:
                    content_bytes = await self._fetch_attachment_content(message_id, attachment_id)
                except SourceEntityNotFoundError:
                    self.logger.warning(f"Attachment {attachment_id} not found (404) - skipping")
                    return None

                if not content_bytes:
                    self.logger.warning(f"No content found for attachment {attachment_name}")
                    return None

            composite_id = f"{message_id}_attachment_{attachment_id}"
            file_entity = OutlookAttachmentEntity(
                composite_id=composite_id,
                breadcrumbs=breadcrumbs,
                name=attachment_name,
                url=f"outlook://attachment/{message_id}/{attachment_id}",
                mime_type=attachment.get("contentType"),
                size=attachment.get("size", 0),
                message_id=message_id,
                attachment_id=attachment_id,
                content_type=attachment.get("contentType"),
                is_inline=attachment.get("isInline", False),
                content_id=attachment.get("contentId"),
                metadata={
                    "source": "outlook_mail",
                    "message_id": message_id,
                    "attachment_id": attachment_id,
                },
                message_web_url=message_web_url,
            )

            try:
                binary_data = base64.b64decode(content_bytes)
            except Exception as e:
                self.logger.warning(f"Error decoding attachment content: {str(e)}")
                return None

            if files:
                self.logger.debug(f"Saving attachment {attachment_name} to disk")
                safe_name = safe_filename(attachment_name, default_ext="")
                await files.save_bytes(
                    entity=file_entity,
                    content=binary_data,
                    filename_with_extension=safe_name,
                    logger=self.logger,
                )

                if not file_entity.local_path:
                    raise ValueError(f"Save failed - no local path set for {attachment_name}")

            self.logger.debug(f"Successfully processed attachment: {attachment_name}")
            return file_entity

        except FileSkippedException as e:
            self.logger.debug(f"Skipping attachment {attachment_name}: {e.reason}")
            return None

        except SourceAuthError:
            raise

        except Exception as e:
            self.logger.warning(f"Error processing attachment {attachment_id}: {str(e)}")
            return None

    async def _process_attachments(
        self,
        message_id: str,
        breadcrumbs: List[Breadcrumb],
        message_web_url: Optional[str],
        files: FileService | None = None,
    ) -> AsyncGenerator[OutlookAttachmentEntity, None]:
        """Process message attachments using the standard file processing pipeline."""
        self.logger.debug(f"Processing attachments for message {message_id}")

        url = f"{self.GRAPH_BASE_URL}/me/messages/{message_id}/attachments"

        try:
            while url:
                self.logger.debug(f"Making request to: {url}")
                data = await self._get(url)
                attachments = data.get("value", [])
                self.logger.debug(
                    f"Retrieved {len(attachments)} attachments for message {message_id}"
                )

                for att_idx, attachment in enumerate(attachments):
                    processed_entity = await self._process_single_attachment(
                        attachment,
                        message_id,
                        breadcrumbs,
                        att_idx,
                        len(attachments),
                        message_web_url,
                        files=files,
                    )
                    if processed_entity:
                        yield processed_entity

                url = data.get("@odata.nextLink")
                if url:
                    self.logger.debug("Following pagination link")

        except SourceAuthError:
            raise
        except Exception as e:
            self.logger.warning(f"Error processing attachments for message {message_id}: {str(e)}")

    # ------------------------------------------------------------------
    # Delta / incremental sync
    # ------------------------------------------------------------------

    async def _process_delta_changes(
        self,
        delta_token: str,
        folder_id: str,
        folder_name: str,
        cursor: SyncCursor | None = None,
        files: FileService | None = None,
    ) -> AsyncGenerator[BaseEntity, None]:
        """Process delta changes for a specific folder using Microsoft Graph delta API."""
        self.logger.debug(f"Processing delta changes for folder: {folder_name}")

        try:
            url = f"{self.GRAPH_BASE_URL}/me/mailFolders/{folder_id}/messages/delta"
            params = {"$deltatoken": delta_token}
            while url:
                self.logger.debug(f"Fetching delta changes from: {url}")
                data = await self._get(url, params=params)
                params = None

                changes = data.get("value", [])
                self.logger.debug(f"Found {len(changes)} changes in delta response")

                for change in changes:
                    if not self._message_matches_date_filter(change):
                        self.logger.debug(
                            f"Skipping delta change {change.get('id')} - doesn't match date filter"
                        )
                        continue

                    async for entity in self._yield_message_change_entities(
                        change=change,
                        folder_id=folder_id,
                        folder_name=folder_name,
                        files=files,
                    ):
                        yield entity

                new_delta_token = data.get("@odata.deltaLink")
                if new_delta_token:
                    self.logger.debug("Updating cursor with new delta token")
                    self._update_folder_cursor(new_delta_token, folder_id, folder_name, cursor)
                else:
                    self.logger.warning("No new delta token received - this may indicate an issue")

                url = data.get("@odata.nextLink")
                if url:
                    self.logger.debug("Following delta pagination")

        except SourceAuthError:
            raise
        except Exception as e:
            self.logger.warning(
                f"Error processing delta changes for folder {folder_name}: {str(e)}"
            )
            raise

    async def _yield_message_change_entities(
        self,
        change: Dict[str, Any],
        folder_id: str,
        folder_name: str,
        files: FileService | None = None,
    ) -> AsyncGenerator[BaseEntity, None]:
        """Yield entities for a single message change item from Graph delta."""
        change_type = change.get("@odata.type", "")

        if "@removed" in change:
            message_id = change.get("id")
            if message_id:
                deletion_entity = OutlookMessageDeletionEntity(
                    breadcrumbs=[],
                    message_id=message_id,
                    label=f"Deleted message {message_id}",
                    deletion_status="removed",
                )
                yield deletion_entity
            return

        if "#microsoft.graph.message" in change_type or change.get("id"):
            folder_breadcrumb = Breadcrumb(
                entity_id=folder_id,
                name=folder_name,
                entity_type="OutlookMailFolderEntity",
            )
            async for entity in self._process_message(
                change, folder_name, folder_breadcrumb, files=files
            ):
                yield entity

    async def _initialize_folders_delta_link(self, cursor: SyncCursor | None = None) -> None:
        """Initialize and store the delta link for the mailFolders collection."""
        try:
            init_url = f"{self.GRAPH_BASE_URL}/me/mailFolders/delta"
            self.logger.debug(f"Initializing folders delta link via: {init_url}")
            data = await self._get(init_url)

            safety_counter = 0
            while isinstance(data, dict) and safety_counter < 1000:
                safety_counter += 1
                delta_link = data.get("@odata.deltaLink")
                if delta_link:
                    if cursor:
                        cursor.update(folders_delta_link=delta_link)
                    self.logger.debug("Stored folders_delta_link for future incremental syncs")
                    break

                next_link = data.get("@odata.nextLink")
                if next_link:
                    self.logger.debug("Following folders delta nextLink")
                    data = await self._get(next_link)
                else:
                    self.logger.warning("No deltaLink or nextLink while initializing folders delta")
                    break
        except SourceAuthError:
            raise
        except Exception as e:
            self.logger.warning(f"Failed to initialize folders delta link: {e}")

    async def _process_folders_delta_changes(
        self,
        cursor: SyncCursor | None = None,
        files: FileService | None = None,
    ) -> AsyncGenerator[BaseEntity, None]:
        """Process changes in mail folders using the stored folders_delta_link."""
        cursor_data = cursor.data if cursor else {}
        delta_url = cursor_data.get("folders_delta_link")
        if not delta_url:
            self.logger.debug("No folders_delta_link stored; skipping folders delta processing")
            return

        try:
            async for data in self._iterate_delta_pages(delta_url):
                changes = data.get("value", [])
                self.logger.debug(f"Found {len(changes)} folder changes in delta response")

                async for entity in self._yield_folder_changes(changes, cursor=cursor, files=files):
                    yield entity

                new_delta_link = data.get("@odata.deltaLink")
                if new_delta_link and cursor:
                    cursor.update(folders_delta_link=new_delta_link)
                    self.logger.debug("Updated folders_delta_link for next incremental run")

        except SourceAuthError:
            raise
        except Exception as e:
            self.logger.warning(f"Error processing folders delta changes: {e}")

    async def _iterate_delta_pages(self, start_url: str) -> AsyncGenerator[Dict[str, Any], None]:
        """Iterate delta/next pages starting from a delta or nextLink URL."""
        url = start_url
        while url:
            self.logger.debug(f"Fetching folders delta changes from: {url}")
            data = await self._get(url)
            yield data
            url = data.get("@odata.nextLink")

    async def _yield_folder_changes(
        self,
        changes: List[Dict[str, Any]],
        cursor: SyncCursor | None = None,
        files: FileService | None = None,
    ) -> AsyncGenerator[BaseEntity, None]:
        """Yield entities for a batch of folder changes from Graph delta."""
        for folder in changes:
            folder_id = folder.get("id")
            if not folder_id:
                continue

            if "@removed" in folder:
                async for e in self._emit_folder_removal(folder_id, cursor=cursor):
                    yield e
                continue

            async for e in self._emit_folder_add_or_update(folder, cursor=cursor, files=files):
                yield e

    async def _emit_folder_removal(
        self, folder_id: str, cursor: SyncCursor | None = None
    ) -> AsyncGenerator[BaseEntity, None]:
        """Emit a folder deletion entity and clean up stored links/names."""
        self.logger.debug(f"Folder removed: {folder_id}")
        deletion_entity = OutlookMailFolderDeletionEntity(
            breadcrumbs=[],
            folder_id=folder_id,
            label=f"Deleted folder {folder_id}",
            deletion_status="removed",
        )
        if cursor:
            cursor_data = cursor.data
            folder_links = cursor_data.get("folder_delta_links", {})
            folder_names = cursor_data.get("folder_names", {})
            folder_links.pop(folder_id, None)
            folder_names.pop(folder_id, None)
            cursor.update(folder_delta_links=folder_links, folder_names=folder_names)
        yield deletion_entity

    async def _emit_folder_add_or_update(  # noqa: C901
        self,
        folder: Dict[str, Any],
        cursor: SyncCursor | None = None,
        files: FileService | None = None,
    ) -> AsyncGenerator[BaseEntity, None]:
        """Emit folder entity and ensure per-folder message delta is initialized."""
        if not self._should_process_folder(folder):
            self.logger.debug(
                f"Skipping folder {folder.get('displayName')} in delta - "
                f"doesn't match folder filters"
            )
            return

        folder_id = folder.get("id")
        display_name = folder.get("displayName", "")
        parent_folder_id = folder.get("parentFolderId")
        child_folder_count = folder.get("childFolderCount", 0)
        total_item_count = folder.get("totalItemCount", 0)
        unread_item_count = folder.get("unreadItemCount", 0)
        well_known_name = folder.get("wellKnownName")

        folder_entity = OutlookMailFolderEntity(
            id=folder_id,
            breadcrumbs=[],
            display_name=display_name,
            parent_folder_id=parent_folder_id,
            child_folder_count=child_folder_count,
            total_item_count=total_item_count,
            unread_item_count=unread_item_count,
            well_known_name=well_known_name,
        )
        yield folder_entity

        try:
            msg_delta_url = f"{self.GRAPH_BASE_URL}/me/mailFolders/{folder_id}/messages/delta"
            msg_delta_data = await self._get(msg_delta_url)

            safety_counter = 0
            while isinstance(msg_delta_data, dict) and safety_counter < 1000:
                safety_counter += 1

                messages = msg_delta_data.get("value", [])
                folder_breadcrumb = Breadcrumb(
                    entity_id=folder_id,
                    name=display_name or folder_id,
                    entity_type="OutlookMailFolderEntity",
                )
                for change in messages:
                    if "@removed" in change:
                        message_id = change.get("id")
                        if message_id:
                            deletion_entity = OutlookMessageDeletionEntity(
                                breadcrumbs=[],
                                message_id=message_id,
                                label=f"Deleted message {message_id}",
                                deletion_status="removed",
                            )
                            yield deletion_entity
                        continue

                    if not self._message_matches_date_filter(change):
                        self.logger.debug(
                            f"Skipping message {change.get('id')} in folder init - "
                            f"doesn't match date filter"
                        )
                        continue

                    async for entity in self._process_message(
                        change, display_name or folder_id, folder_breadcrumb, files=files
                    ):
                        yield entity

                delta_link = msg_delta_data.get("@odata.deltaLink")
                if delta_link and cursor:
                    cursor_data = cursor.data
                    folder_links = cursor_data.get("folder_delta_links", {})
                    folder_names_map = cursor_data.get("folder_names", {})
                    folder_links[folder_id] = delta_link
                    folder_names_map[folder_id] = display_name or folder_id
                    cursor.update(folder_delta_links=folder_links, folder_names=folder_names_map)
                    break

                next_link = msg_delta_data.get("@odata.nextLink")
                if next_link:
                    msg_delta_data = await self._get(next_link)
                else:
                    break
        except SourceAuthError:
            raise
        except Exception as e:
            self.logger.warning(f"Failed to initialize message delta for folder {folder_id}: {e}")

    async def _process_delta_changes_url(  # noqa: C901
        self,
        delta_url: str,
        folder_id: str,
        folder_name: str,
        cursor: SyncCursor | None = None,
        files: FileService | None = None,
    ) -> AsyncGenerator[BaseEntity, None]:
        """Process delta changes starting from a delta or nextLink URL (opaque state)."""
        self.logger.debug(f"Processing delta changes (URL) for folder: {folder_name}")

        try:
            url = delta_url
            while url:
                self.logger.debug(f"Fetching delta changes from: {url}")
                data = await self._get(url)

                changes = data.get("value", [])
                self.logger.debug(f"Found {len(changes)} changes in delta response")

                for change in changes:
                    change_type = change.get("@odata.type", "")

                    if "@removed" in change:
                        message_id = change.get("id")
                        if message_id:
                            deletion_entity = OutlookMessageDeletionEntity(
                                breadcrumbs=[],
                                message_id=message_id,
                                label=f"Deleted message {message_id}",
                                deletion_status="removed",
                            )
                            yield deletion_entity
                        continue

                    if not self._message_matches_date_filter(change):
                        self.logger.debug(
                            f"Skipping delta change {change.get('id')} - doesn't match date filter"
                        )
                        continue

                    if "#microsoft.graph.message" in change_type or change.get("id"):
                        folder_breadcrumb = Breadcrumb(
                            entity_id=folder_id,
                            name=folder_name,
                            entity_type="OutlookMailFolderEntity",
                        )
                        async for entity in self._process_message(
                            change, folder_name, folder_breadcrumb, files=files
                        ):
                            yield entity

                next_link = data.get("@odata.nextLink")
                if next_link:
                    self.logger.debug("Following delta pagination nextLink")
                    url = next_link
                    continue

                delta_link = data.get("@odata.deltaLink")
                if delta_link:
                    self.logger.debug("Updating cursor with new delta link")
                    self._update_folder_cursor(delta_link, folder_id, folder_name, cursor)
                else:
                    self.logger.warning(
                        "No nextLink or deltaLink in delta response; ending this delta cycle"
                    )
                break

        except SourceAuthError:
            raise
        except Exception as e:
            self.logger.warning(
                f"Error processing delta changes (URL) for folder {folder_name}: {str(e)}"
            )
            raise

    async def _generate_folder_entities_incremental(
        self,
        delta_token: str,
        cursor: SyncCursor | None = None,
        files: FileService | None = None,
    ) -> AsyncGenerator[BaseEntity, None]:
        """Generate entities for incremental sync using delta token."""
        self.logger.debug("Starting incremental sync")

        cursor_data = cursor.data if cursor else {}
        folder_links = cursor_data.get("folder_delta_links", {}) or {}
        folder_names = cursor_data.get("folder_names", {}) or {}

        if folder_links:
            for folder_id, delta_link in folder_links.items():
                folder_name = folder_names.get(folder_id, folder_id)
                async for entity in self._process_delta_changes_url(
                    delta_link, folder_id, folder_name, cursor=cursor, files=files
                ):
                    yield entity
            return

        folder_id = cursor_data.get("folder_id")
        folder_name = cursor_data.get("folder_name", "Unknown Folder")
        if not folder_id:
            self.logger.warning("No folder_id in cursor data for legacy delta token; skipping")
            return
        async for entity in self._process_delta_changes(
            delta_token, folder_id, folder_name, cursor=cursor, files=files
        ):
            yield entity

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def generate_entities(  # noqa: C901
        self,
        *,
        cursor: SyncCursor | None = None,
        files: FileService | None = None,
        node_selections: list[NodeSelectionData] | None = None,
        source_hash_lookup: SourceHashLookup | None = None,
    ) -> AsyncGenerator[BaseEntity, None]:
        """Generate all Outlook mail entities: Folders, Messages and Attachments.

        Supports both full sync (first run) and incremental sync (subsequent runs)
        using Microsoft Graph delta API.
        """
        self.logger.debug("===== STARTING OUTLOOK MAIL ENTITY GENERATION =====")
        entity_count = 0

        try:
            cursor_data = cursor.data if cursor else {}
            delta_token = cursor_data.get("delta_link")

            if delta_token:
                self.logger.debug("Incremental sync from cursor")
            else:
                self.logger.debug("Full sync (no cursor)")

            has_folder_links = bool(cursor_data.get("folder_delta_links"))

            if has_folder_links or delta_token:
                self.logger.debug("Performing INCREMENTAL sync")
                async for entity in self._generate_folder_entities_incremental(
                    delta_token, cursor=cursor, files=files
                ):
                    entity_count += 1
                    entity_type = type(entity).__name__
                    self.logger.debug(
                        (
                            f"Yielding delta entity #{entity_count}: {entity_type} "
                            f"with ID {entity.entity_id}"
                        )
                    )
                    yield entity
            else:
                self.logger.debug("Performing FULL sync (first sync or cursor reset)")
                await self._initialize_folders_delta_link(cursor=cursor)

                async for entity in self._generate_folder_entities(cursor=cursor, files=files):
                    entity_count += 1
                    entity_type = type(entity).__name__
                    self.logger.debug(
                        (
                            f"Yielding full sync entity #{entity_count}: {entity_type} "
                            f"with ID {entity.entity_id}"
                        )
                    )
                    yield entity

        except SourceAuthError:
            raise
        except Exception as e:
            self.logger.warning(f"Error in entity generation: {str(e)}", exc_info=True)
            raise
        finally:
            self.logger.debug(
                f"===== OUTLOOK MAIL ENTITY GENERATION COMPLETE: {entity_count} entities ====="
            )

    async def validate(self) -> None:
        """Validate credentials by pinging the mailFolders endpoint."""
        await self._get(
            f"{self.GRAPH_BASE_URL}/me/mailFolders",
            params={"$top": "1"},
        )
