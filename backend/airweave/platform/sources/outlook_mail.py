"""Outlook Mail source implementation.

Simplified version that retrieves:
  - All mail folders (hierarchical discovery)
  - Messages from all folders
  - Attachments

Follows the same structure as the Gmail connector implementation.
"""

import base64
from datetime import datetime
from typing import Any, AsyncGenerator, Dict, List, Optional

import httpx

from airweave.core.logging import logger
from airweave.platform.auth.schemas import AuthType
from airweave.platform.decorators import source
from airweave.platform.entities._base import Breadcrumb, ChunkEntity
from airweave.platform.entities.outlook_mail import (
    OutlookAttachmentEntity,
    OutlookMailFolderEntity,
    OutlookMessageEntity,
)
from airweave.platform.sources._base import BaseSource


@source(
    name="Outlook Mail",
    short_name="outlook_mail",
    auth_type=AuthType.oauth2_with_refresh_rotating,
    auth_config_class="OutlookMailAuthConfig",
    config_class="OutlookMailConfig",
    labels=["Communication", "Email"],
)
class OutlookMailSource(BaseSource):
    """Outlook Mail source implementation (read-only).

    Retrieves and yields Outlook mail folders, messages and attachments.
    """

    GRAPH_BASE_URL = "https://graph.microsoft.com/v1.0"

    @classmethod
    async def create(
        cls, access_token: str, config: Optional[Dict[str, Any]] = None
    ) -> "OutlookMailSource":
        """Create a new Outlook Mail source instance with the provided OAuth access token."""
        logger.info("Creating new OutlookMailSource instance")
        instance = cls()
        instance.access_token = access_token
        logger.info(f"OutlookMailSource instance created with config: {config}")
        return instance

    async def _get_with_auth(
        self, client: httpx.AsyncClient, url: str, params: Optional[dict] = None
    ) -> dict:
        """Make an authenticated GET request to Microsoft Graph API."""
        self.logger.debug(f"Making authenticated GET request to: {url} with params: {params}")
        try:
            return await self._make_authenticated_request(
                lambda token: client.get(
                    url, headers={"Authorization": f"Bearer {token}"}, params=params
                )
            )
        except Exception as e:
            self.logger.error(f"Error in API request to {url}: {str(e)}")
            raise

    async def _process_folder_messages(
        self,
        client: httpx.AsyncClient,
        folder_entity: OutlookMailFolderEntity,
        folder_breadcrumb: Breadcrumb,
    ) -> AsyncGenerator[ChunkEntity, None]:
        """Process messages in a folder and handle errors gracefully."""
        self.logger.info(f"Processing messages in folder: {folder_entity.display_name}")
        try:
            async for entity in self._generate_message_entities(
                client, folder_entity, folder_breadcrumb
            ):
                yield entity
        except Exception as e:
            self.logger.error(
                f"Error processing messages in folder {folder_entity.display_name}: {str(e)}"
            )
            # Continue with other folders even if one fails

    async def _process_child_folders(
        self,
        client: httpx.AsyncClient,
        folder_entity: OutlookMailFolderEntity,
        parent_breadcrumbs: List[Breadcrumb],
        folder_breadcrumb: Breadcrumb,
    ) -> AsyncGenerator[OutlookMailFolderEntity, None]:
        """Process child folders recursively and handle errors gracefully."""
        if folder_entity.child_folder_count > 0:
            self.logger.info(
                f"Folder {folder_entity.display_name} has "
                f"{folder_entity.child_folder_count} child folders, recursively processing"
            )
            try:
                async for child_entity in self._generate_folder_entities(
                    client,
                    folder_entity.entity_id,
                    parent_breadcrumbs + [folder_breadcrumb],
                ):
                    yield child_entity
            except Exception as e:
                self.logger.error(
                    f"Error processing child folders of {folder_entity.display_name}: {str(e)}"
                )
                # Continue with other folders even if one fails

    async def _generate_folder_entities(
        self,
        client: httpx.AsyncClient,
        folder_id: Optional[str] = None,
        parent_breadcrumbs: Optional[List[Breadcrumb]] = None,
    ) -> AsyncGenerator[OutlookMailFolderEntity, None]:
        """Recursively generate OutlookMailFolderEntity objects.

        Traverses the mail folder hierarchy via Microsoft Graph.
        """
        if parent_breadcrumbs is None:
            parent_breadcrumbs = []

        # Decide the endpoint: top-level vs. child folders
        if folder_id:
            url = f"{self.GRAPH_BASE_URL}/me/mailFolders/{folder_id}/childFolders"
            self.logger.info(f"Fetching child folders for folder ID: {folder_id}")
        else:
            # top-level mail folders
            url = f"{self.GRAPH_BASE_URL}/me/mailFolders"
            self.logger.info("Fetching top-level mail folders")

        try:
            while url:
                self.logger.debug(f"Making request to: {url}")
                data = await self._get_with_auth(client, url)
                folders = data.get("value", [])
                self.logger.info(f"Retrieved {len(folders)} folders")

                for folder in folders:
                    # Create and yield folder entity
                    folder_entity = OutlookMailFolderEntity(
                        entity_id=folder["id"],
                        breadcrumbs=parent_breadcrumbs,
                        display_name=folder["displayName"],
                        parent_folder_id=folder.get("parentFolderId"),
                        child_folder_count=folder.get("childFolderCount", 0),
                        total_item_count=folder.get("totalItemCount", 0),
                        unread_item_count=folder.get("unreadItemCount", 0),
                        well_known_name=folder.get("wellKnownName"),
                    )

                    self.logger.info(
                        f"Processing folder: {folder_entity.display_name} "
                        f"(ID: {folder_entity.entity_id}, Items: {folder_entity.total_item_count})"
                    )
                    yield folder_entity

                    # Build breadcrumb for this folder
                    folder_breadcrumb = Breadcrumb(
                        entity_id=folder_entity.entity_id,
                        name=folder_entity.display_name,
                        type="folder",
                    )

                    # Process messages in this folder
                    async for entity in self._process_folder_messages(
                        client, folder_entity, folder_breadcrumb
                    ):
                        yield entity

                    # Process child folders recursively
                    async for child_entity in self._process_child_folders(
                        client, folder_entity, parent_breadcrumbs, folder_breadcrumb
                    ):
                        yield child_entity

                # Handle pagination
                next_link = data.get("@odata.nextLink")
                if next_link:
                    self.logger.debug(f"Following pagination link: {next_link}")
                url = next_link if next_link else None

        except Exception as e:
            self.logger.error(f"Error fetching folders: {str(e)}")
            raise

    async def _generate_message_entities(
        self,
        client: httpx.AsyncClient,
        folder_entity: OutlookMailFolderEntity,
        folder_breadcrumb: Breadcrumb,
    ) -> AsyncGenerator[ChunkEntity, None]:
        """Generate OutlookMessageEntity objects and their attachments for a given folder."""
        # Skip folders with no messages
        if folder_entity.total_item_count == 0:
            self.logger.debug(f"Skipping folder {folder_entity.display_name} - no messages")
            return

        self.logger.info(
            f"Starting message generation for folder: {folder_entity.display_name} "
            f"({folder_entity.total_item_count} items)"
        )

        url = f"{self.GRAPH_BASE_URL}/me/mailFolders/{folder_entity.entity_id}/messages"
        params = {"$top": 50}  # Fetch 50 messages at a time

        page_count = 0
        message_count = 0

        try:
            while url:
                page_count += 1
                self.logger.info(
                    f"Fetching message list page #{page_count} for folder "
                    f"{folder_entity.display_name}"
                )
                data = await self._get_with_auth(client, url, params=params)
                messages = data.get("value", [])
                self.logger.info(
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

                    # If message doesn't have full data, fetch it
                    if "body" not in message_data:
                        self.logger.debug(f"Fetching full message details for {message_id}")
                        message_url = f"{self.GRAPH_BASE_URL}/me/messages/{message_id}"
                        message_data = await self._get_with_auth(client, message_url)

                    # Process the message
                    try:
                        async for entity in self._process_message(
                            client, message_data, folder_entity.display_name, folder_breadcrumb
                        ):
                            yield entity
                    except Exception as e:
                        self.logger.error(f"Error processing message {message_id}: {str(e)}")
                        # Continue with other messages even if one fails

                # Handle pagination
                url = data.get("@odata.nextLink")
                if url:
                    self.logger.debug("Following pagination to next page")
                    params = None  # params are included in the nextLink
                else:
                    self.logger.info(
                        f"Completed folder {folder_entity.display_name}. "
                        f"Processed {message_count} messages in {page_count} pages."
                    )
                    break

        except Exception as e:
            self.logger.error(
                f"Error processing messages in folder {folder_entity.display_name}: {str(e)}"
            )
            raise

    async def _process_message(
        self,
        client: httpx.AsyncClient,
        message_data: Dict,
        folder_name: str,
        folder_breadcrumb: Breadcrumb,
    ) -> AsyncGenerator[ChunkEntity, None]:
        """Process a message and its attachments."""
        message_id = message_data["id"]
        self.logger.debug(f"Processing message ID: {message_id} in folder: {folder_name}")

        # Extract message fields
        subject = message_data.get("subject")
        sender = (
            message_data.get("from", {}).get("emailAddress", {}).get("address")
            if message_data.get("from")
            else None
        )
        to_recipients = [
            r.get("emailAddress", {}).get("address")
            for r in message_data.get("toRecipients", [])
            if r.get("emailAddress")
        ]
        cc_recipients = [
            r.get("emailAddress", {}).get("address")
            for r in message_data.get("ccRecipients", [])
            if r.get("emailAddress")
        ]

        # Parse dates
        sent_date = None
        received_date = None
        try:
            if message_data.get("sentDateTime"):
                sent_date = datetime.fromisoformat(
                    message_data["sentDateTime"].replace("Z", "+00:00")
                )
            if message_data.get("receivedDateTime"):
                received_date = datetime.fromisoformat(
                    message_data["receivedDateTime"].replace("Z", "+00:00")
                )
        except (ValueError, TypeError) as e:
            self.logger.warning(f"Error parsing dates for message {message_id}: {str(e)}")

        # Extract body content
        body_content = ""
        body_preview = message_data.get("bodyPreview", "")
        if message_data.get("body"):
            body_content = message_data["body"].get("content", "")

        self.logger.debug(f"Creating message entity for message {message_id}")

        # Create message entity
        message_entity = OutlookMessageEntity(
            entity_id=message_id,
            breadcrumbs=[folder_breadcrumb],
            folder_name=folder_name,
            subject=subject,
            sender=sender,
            to_recipients=to_recipients,
            cc_recipients=cc_recipients,
            sent_date=sent_date,
            received_date=received_date,
            body_preview=body_preview,
            body_content=body_content,
            is_read=message_data.get("isRead", False),
            is_draft=message_data.get("isDraft", False),
            importance=message_data.get("importance"),
            has_attachments=message_data.get("hasAttachments", False),
            internet_message_id=message_data.get("internetMessageId"),
        )

        yield message_entity
        self.logger.debug(f"Message entity yielded for {message_id}")

        # Create message breadcrumb for attachments
        message_breadcrumb = Breadcrumb(
            entity_id=message_id,
            name=subject or f"Message {message_id}",
            type="message",
        )

        # Process attachments if the message has any
        if message_entity.has_attachments:
            self.logger.debug(f"Message {message_id} has attachments, processing them")
            attachment_count = 0
            try:
                async for attachment_entity in self._process_attachments(
                    client, message_id, [folder_breadcrumb, message_breadcrumb]
                ):
                    attachment_count += 1
                    self.logger.debug(
                        f"Yielding attachment #{attachment_count} from message {message_id}"
                    )
                    yield attachment_entity
                self.logger.debug(
                    f"Processed {attachment_count} attachments for message {message_id}"
                )
            except Exception as e:
                self.logger.error(
                    f"Error processing attachments for message {message_id}: {str(e)}"
                )
                # Continue with message processing even if attachments fail

    async def _create_content_stream(self, binary_data: bytes):
        """Create an async generator for binary content."""
        yield binary_data

    async def _fetch_attachment_content(
        self, client: httpx.AsyncClient, message_id: str, attachment_id: str
    ) -> Optional[str]:
        """Fetch attachment content from Microsoft Graph API."""
        self.logger.debug(f"Fetching content for attachment {attachment_id}")
        attachment_url = (
            f"{self.GRAPH_BASE_URL}/me/messages/{message_id}/attachments/{attachment_id}"
        )
        attachment_data = await self._get_with_auth(client, attachment_url)
        return attachment_data.get("contentBytes")

    async def _process_single_attachment(
        self,
        client: httpx.AsyncClient,
        attachment: Dict,
        message_id: str,
        breadcrumbs: List[Breadcrumb],
        att_idx: int,
        total_attachments: int,
    ) -> Optional[OutlookAttachmentEntity]:
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
                content_bytes = await self._fetch_attachment_content(
                    client, message_id, attachment_id
                )

                if not content_bytes:
                    self.logger.warning(f"No content found for attachment {attachment_name}")
                    return None

            # Create file entity
            file_entity = OutlookAttachmentEntity(
                entity_id=f"{message_id}_attachment_{attachment_id}",
                breadcrumbs=breadcrumbs,
                file_id=attachment_id,
                name=attachment_name,
                mime_type=attachment.get("contentType"),
                size=attachment.get("size", 0),
                download_url=f"outlook://attachment/{message_id}/{attachment_id}",
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
            )

            # Decode the base64 data
            try:
                binary_data = base64.b64decode(content_bytes)
            except Exception as e:
                self.logger.error(f"Error decoding attachment content: {str(e)}")
                return None

            # Process using the BaseSource method
            self.logger.debug(
                f"Processing file entity for {attachment_name} with direct content stream"
            )
            processed_entity = await self.process_file_entity_with_content(
                file_entity=file_entity,
                content_stream=self._create_content_stream(binary_data),
                metadata={"source": "outlook_mail", "message_id": message_id},
            )

            if processed_entity:
                self.logger.debug(f"Successfully processed attachment: {attachment_name}")
                return processed_entity
            else:
                self.logger.warning(f"Processing failed for attachment: {attachment_name}")
                return None

        except Exception as e:
            self.logger.error(f"Error processing attachment {attachment_id}: {str(e)}")
            return None

    async def _process_attachments(
        self,
        client: httpx.AsyncClient,
        message_id: str,
        breadcrumbs: List[Breadcrumb],
    ) -> AsyncGenerator[OutlookAttachmentEntity, None]:
        """Process message attachments using the standard file processing pipeline."""
        self.logger.debug(f"Processing attachments for message {message_id}")

        url = f"{self.GRAPH_BASE_URL}/me/messages/{message_id}/attachments"

        try:
            while url:
                self.logger.debug(f"Making request to: {url}")
                data = await self._get_with_auth(client, url)
                attachments = data.get("value", [])
                self.logger.debug(
                    f"Retrieved {len(attachments)} attachments for message {message_id}"
                )

                for att_idx, attachment in enumerate(attachments):
                    processed_entity = await self._process_single_attachment(
                        client, attachment, message_id, breadcrumbs, att_idx, len(attachments)
                    )
                    if processed_entity:
                        yield processed_entity

                # Handle pagination
                url = data.get("@odata.nextLink")
                if url:
                    self.logger.debug("Following pagination link")

        except Exception as e:
            self.logger.error(f"Error processing attachments for message {message_id}: {str(e)}")
            # Don't re-raise - continue with other messages even if attachments fail

    async def generate_entities(self) -> AsyncGenerator[ChunkEntity, None]:
        """Generate all Outlook mail entities: Folders, Messages and Attachments."""
        self.logger.info("===== STARTING OUTLOOK MAIL ENTITY GENERATION =====")
        entity_count = 0

        try:
            async with httpx.AsyncClient() as client:
                self.logger.info("HTTP client created, starting entity generation")

                # Start with top-level folders and recursively process all folders and contents
                async for entity in self._generate_folder_entities(client):
                    entity_count += 1
                    entity_type = type(entity).__name__
                    self.logger.info(
                        f"Yielding entity #{entity_count}: {entity_type} with ID {entity.entity_id}"
                    )
                    yield entity

        except Exception as e:
            self.logger.error(f"Error in entity generation: {str(e)}", exc_info=True)
            raise
        finally:
            self.logger.info(
                f"===== OUTLOOK MAIL ENTITY GENERATION COMPLETE: {entity_count} entities ====="
            )
