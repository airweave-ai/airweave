"""Gmail source implementation.

Simplified version that retrieves:
  - Threads
  - Messages
  - Attachments

Follows the same structure as other connector implementations.
"""

import base64
from datetime import datetime
from typing import Any, AsyncGenerator, Dict, List, Optional

import httpx

from airweave.core.logging import logger
from airweave.platform.auth.schemas import AuthType
from airweave.platform.decorators import source
from airweave.platform.entities._base import Breadcrumb, ChunkEntity
from airweave.platform.entities.gmail import (
    GmailAttachmentEntity,
    GmailMessageEntity,
    GmailThreadEntity,
)
from airweave.platform.sources._base import BaseSource


@source(
    name="Gmail",
    short_name="gmail",
    auth_type=AuthType.oauth2_with_refresh,
    auth_config_class="GmailAuthConfig",
    config_class="GmailConfig",
    labels=["Communication", "Email"],
)
class GmailSource(BaseSource):
    """Gmail source implementation (read-only).

    Retrieves and yields Gmail objects (threads, messages, attachments).
    """

    @classmethod
    async def create(
        cls, access_token: str, config: Optional[Dict[str, Any]] = None
    ) -> "GmailSource":
        """Create a new Gmail source instance with the provided OAuth access token."""
        logger.info("Creating new GmailSource instance")
        instance = cls()
        instance.access_token = access_token
        logger.info(f"GmailSource instance created with config: {config}")
        return instance

    async def _get_with_auth(
        self, client: httpx.AsyncClient, url: str, params: Optional[dict] = None
    ) -> dict:
        """Make an authenticated GET request to the Gmail API."""
        logger.info(f"Making authenticated GET request to: {url} with params: {params}")
        headers = {"Authorization": f"Bearer {self.access_token}"}
        try:
            response = await client.get(url, headers=headers, params=params)
            response.raise_for_status()
            data = response.json()
            logger.info(f"Received response from {url} - Status: {response.status_code}")
            logger.debug(f"Response data keys: {list(data.keys())}")
            return data
        except Exception as e:
            logger.error(f"Error in API request to {url}: {str(e)}")
            raise

    async def _generate_thread_entities(
        self, client: httpx.AsyncClient
    ) -> AsyncGenerator[ChunkEntity, None]:
        """Generate GmailThreadEntity objects and associated message entities."""
        logger.info("Starting thread entity generation")
        base_url = "https://gmail.googleapis.com/gmail/v1/users/me/threads"
        params = {"maxResults": 100}

        page_count = 0
        thread_count = 0

        while True:
            page_count += 1
            logger.info(f"Fetching thread list page #{page_count} with params: {params}")
            data = await self._get_with_auth(client, base_url, params=params)
            threads = data.get("threads", [])
            logger.info(f"Found {len(threads)} threads on page {page_count}")

            for thread_idx, thread_info in enumerate(threads):
                thread_count += 1
                thread_id = thread_info["id"]
                logger.info(f"Processing thread #{thread_idx + 1}/{len(threads)} (ID: {thread_id})")

                # Fetch full thread detail
                detail_url = f"{base_url}/{thread_id}"
                logger.info(f"Fetching full thread details from: {detail_url}")
                thread_data = await self._get_with_auth(client, detail_url)

                # Collect thread information
                snippet = thread_data.get("snippet", "")
                history_id = thread_data.get("historyId")
                message_list = thread_data.get("messages", [])

                logger.info(f"Thread {thread_id} contains {len(message_list)} messages")
                logger.debug(f"Thread snippet: {snippet[:50]}...")
                logger.debug(f"Thread history ID: {history_id}")

                # Calculate message count
                message_count = len(message_list)

                # Find last message date
                last_message_date = None
                if message_list:
                    logger.debug("Sorting messages by date to find most recent")
                    sorted_msgs = sorted(
                        message_list, key=lambda m: int(m.get("internalDate", 0)), reverse=True
                    )
                    last_message_date_ms = sorted_msgs[0].get("internalDate")
                    if last_message_date_ms:
                        last_message_date = datetime.utcfromtimestamp(
                            int(last_message_date_ms) / 1000
                        )
                        logger.debug(f"Last message date: {last_message_date}")

                # Get label IDs from first message if available
                label_ids = []
                if message_list:
                    label_ids = message_list[0].get("labelIds", [])
                    logger.debug(f"Thread labels: {label_ids}")

                # Create thread entity
                logger.info(f"Creating thread entity for thread ID: {thread_id}")
                thread_entity = GmailThreadEntity(
                    entity_id=thread_id,
                    breadcrumbs=[],  # Thread is top-level
                    snippet=snippet,
                    history_id=history_id,
                    message_count=message_count,
                    label_ids=label_ids,
                    last_message_date=last_message_date,
                )
                logger.debug(f"Thread entity created: {thread_entity.dict()}")
                yield thread_entity
                logger.info(f"Thread entity yielded: {thread_id}")

                # Create thread breadcrumb for messages
                thread_breadcrumb = Breadcrumb(
                    entity_id=thread_id,
                    name=snippet[:50] + "..." if len(snippet) > 50 else snippet,
                    type="thread",
                )
                logger.debug(f"Created thread breadcrumb: {thread_breadcrumb}")

                # Process each message in the thread
                logger.info(f"Processing {len(message_list)} messages in thread {thread_id}")
                for msg_idx, message_data in enumerate(message_list):
                    msg_id = message_data.get("id", "unknown")
                    msg_info = (
                        f"Processing message #{msg_idx + 1}/{len(message_list)} "
                        f"(ID: {msg_id}) in thread {thread_id}"
                    )
                    logger.info(msg_info)

                    msg_entity_count = 0
                    async for entity in self._process_message(
                        client, message_data, thread_id, thread_breadcrumb
                    ):
                        msg_entity_count += 1
                        entity_type = type(entity).__name__
                        logger.info(f"Yielding {entity_type} entity from message {msg_id}")
                        yield entity

                    logger.info(f"Yielded {msg_entity_count} entities for message {msg_id}")

            # Handle pagination
            next_page_token = data.get("nextPageToken")
            if not next_page_token:
                msg = (
                    f"No more pages to fetch. Processed {thread_count} threads "
                    f"in {page_count} pages."
                )
                logger.info(msg)
                break

            logger.info(f"Found next page token: {next_page_token[:10]}...")
            params["pageToken"] = next_page_token

    async def _process_message(  # noqa: C901
        self,
        client: httpx.AsyncClient,
        message_data: Dict,
        thread_id: str,
        thread_breadcrumb: Breadcrumb,
    ) -> AsyncGenerator[ChunkEntity, None]:
        """Process a message and its attachments."""
        # Get detailed message data if needed
        message_id = message_data["id"]
        logger.info(f"Processing message ID: {message_id} in thread: {thread_id}")

        if "payload" not in message_data:
            logger.info(
                f"Payload not in message data, fetching full message details for {message_id}"
            )
            message_url = f"https://gmail.googleapis.com/gmail/v1/users/me/messages/{message_id}"
            message_data = await self._get_with_auth(client, message_url)
            logger.debug(f"Fetched full message data with keys: {list(message_data.keys())}")
        else:
            logger.debug("Message already contains payload data")

        # Extract message fields
        logger.info(f"Extracting fields for message {message_id}")
        internal_date_ms = message_data.get("internalDate")
        internal_date = None
        if internal_date_ms:
            internal_date = datetime.utcfromtimestamp(int(internal_date_ms) / 1000)
            logger.debug(f"Internal date: {internal_date}")

        payload = message_data.get("payload", {})
        logger.debug(f"Message payload has keys: {list(payload.keys())}")
        headers = payload.get("headers", [])
        logger.debug(f"Found {len(headers)} headers in message")

        # Parse headers
        logger.info(f"Parsing headers for message {message_id}")
        subject = None
        sender = None
        to_list = []
        cc_list = []
        bcc_list = []
        date = None

        for header in headers:
            name = header.get("name", "").lower()
            value = header.get("value", "")
            if name == "subject":
                subject = value
                logger.debug(f"Subject: {subject}")
            elif name == "from":
                sender = value
                logger.debug(f"From: {sender}")
            elif name == "to":
                to_list = [addr.strip() for addr in value.split(",")]
                logger.debug(f"To: {to_list}")
            elif name == "cc":
                cc_list = [addr.strip() for addr in value.split(",")]
                logger.debug(f"CC: {cc_list}")
            elif name == "bcc":
                bcc_list = [addr.strip() for addr in value.split(",")]
                logger.debug(f"BCC: {bcc_list}")
            elif name == "date":
                try:
                    from email.utils import parsedate_to_datetime

                    date = parsedate_to_datetime(value)
                    logger.debug(f"Date: {date}")
                except (TypeError, ValueError):
                    logger.warning(f"Failed to parse date header: {value}")

        # Extract message body
        logger.info(f"Extracting body content for message {message_id}")
        body_plain, body_html = self._extract_body_content(payload)
        logger.debug(f"Found body_plain: {bool(body_plain)}, body_html: {bool(body_html)}")
        if body_plain:
            logger.debug(f"Plain text body (first 100 chars): {body_plain[:100]}...")
        if body_html:
            logger.debug(f"HTML body (first 100 chars): {body_html[:100]}...")

        # Create message entity
        logger.info(f"Creating message entity for message {message_id}")
        message_entity = GmailMessageEntity(
            entity_id=message_id,
            breadcrumbs=[thread_breadcrumb],
            thread_id=thread_id,
            subject=subject,
            sender=sender,
            to=to_list,
            cc=cc_list,
            bcc=bcc_list,
            date=date,
            snippet=message_data.get("snippet"),
            body_plain=body_plain,
            body_html=body_html,
            label_ids=message_data.get("labelIds", []),
            internal_date=internal_date,
            size_estimate=message_data.get("sizeEstimate"),
        )
        logger.debug(f"Message entity created with ID: {message_entity.entity_id}")
        yield message_entity
        logger.info(f"Message entity yielded for {message_id}")

        # Create message breadcrumb for attachments
        message_breadcrumb = Breadcrumb(
            entity_id=message_id,
            name=subject or f"Message {message_id}",
            type="message",
        )
        logger.debug(f"Created message breadcrumb: {message_breadcrumb}")

        # Process attachments
        logger.info(f"Looking for attachments in message {message_id}")
        attachment_count = 0
        async for attachment_entity in self._process_attachments(
            client, payload, message_id, thread_id, [thread_breadcrumb, message_breadcrumb]
        ):
            attachment_count += 1
            logger.info(f"Yielding attachment #{attachment_count} from message {message_id}")
            yield attachment_entity

        logger.info(f"Processed {attachment_count} attachments for message {message_id}")

    def _extract_body_content(self, payload: Dict) -> tuple:  # noqa: C901
        """Extract plain text and HTML body content from message payload."""
        logger.info("Extracting body content from message payload")
        body_plain = None
        body_html = None

        # Function to recursively extract body parts
        def extract_from_parts(parts, depth=0):
            indent = "  " * depth
            logger.debug(f"{indent}Extracting body from {len(parts)} parts at depth {depth}")
            p_txt, p_html = None, None

            for i, part in enumerate(parts):
                mime_type = part.get("mimeType", "")
                logger.debug(f"{indent}Part {i + 1}/{len(parts)}: mime_type={mime_type}")
                body = part.get("body", {})

                # Check if part has data
                if body.get("data"):
                    data = body.get("data")
                    logger.debug(f"{indent}Found data in part {i + 1} with mime_type {mime_type}")
                    try:
                        decoded = base64.urlsafe_b64decode(data).decode("utf-8", errors="ignore")
                        logger.debug(f"{indent}Decoded {len(decoded)} characters")

                        if mime_type == "text/plain" and not p_txt:
                            logger.debug(f"{indent}Found plain text content ({len(decoded)} chars)")
                            p_txt = decoded
                        elif mime_type == "text/html" and not p_html:
                            logger.debug(f"{indent}Found HTML content ({len(decoded)} chars)")
                            p_html = decoded
                    except Exception as e:
                        logger.error(f"{indent}Error decoding body content: {str(e)}")

                # Check if part has sub-parts
                elif part.get("parts"):
                    sub_parts = part.get("parts", [])
                    logger.debug(f"{indent}Part has {len(sub_parts)} sub-parts, recursing...")
                    sub_txt, sub_html = extract_from_parts(sub_parts, depth + 1)
                    if not p_txt:
                        p_txt = sub_txt
                    if not p_html:
                        p_html = sub_html

            log_msg = (
                f"{indent}Extraction at depth {depth} complete: "
                f"found_text={bool(p_txt)}, found_html={bool(p_html)}"
            )
            logger.debug(log_msg)
            return p_txt, p_html

        # Handle multipart messages
        if payload.get("parts"):
            parts = payload.get("parts", [])
            logger.info(f"Processing multipart message with {len(parts)} parts")
            body_plain, body_html = extract_from_parts(parts)
        # Handle single part messages
        else:
            mime_type = payload.get("mimeType", "")
            logger.info(f"Processing single part message with mime_type: {mime_type}")

            body = payload.get("body", {})
            if body.get("data"):
                data = body.get("data")
                logger.debug(f"Found body data of length: {len(data) if data else 0}")
                try:
                    decoded = base64.urlsafe_b64decode(data).decode("utf-8", errors="ignore")
                    logger.debug(f"Decoded {len(decoded)} characters")

                    if mime_type == "text/plain":
                        logger.debug("Found plain text content in single part")
                        body_plain = decoded
                    elif mime_type == "text/html":
                        logger.debug("Found HTML content in single part")
                        body_html = decoded
                except Exception as e:
                    logger.error(f"Error decoding single part body: {str(e)}")

        logger.info(
            f"Body extraction complete: found_text={bool(body_plain)}, found_html={bool(body_html)}"
        )
        return body_plain, body_html

    async def _process_attachments(  # noqa: C901
        self,
        client: httpx.AsyncClient,
        payload: Dict,
        message_id: str,
        thread_id: str,
        breadcrumbs: List[Breadcrumb],
    ) -> AsyncGenerator[GmailAttachmentEntity, None]:
        """Process message attachments using the standard file processing pipeline."""
        logger.info(f"Processing attachments for message {message_id}")

        # Function to recursively find attachments
        async def find_attachments(part, depth=0):
            indent = "  " * depth
            mime_type = part.get("mimeType", "")
            filename = part.get("filename", "")
            part_id = part.get("partId", "unknown")

            part_info = (
                f"{indent}Checking part {part_id} at depth {depth}: "
                f"mime_type={mime_type}, filename={filename}"
            )
            logger.debug(part_info)
            body = part.get("body", {})

            # If part has filename and is not an inline image or text part, treat as attachment
            if (
                filename
                and mime_type not in ("text/plain", "text/html")
                and not (mime_type.startswith("image/") and not filename)
            ):
                attachment_id = body.get("attachmentId")
                attachment_info = (
                    f"{indent}Found potential attachment: {filename} ({mime_type}), "
                    f"attachment_id: {attachment_id}"
                )
                logger.info(attachment_info)

                # Skip if no attachment ID (might be inline content)
                if not attachment_id:
                    logger.debug(f"{indent}Skipping part with filename but no attachment ID")
                    return

                # Get full attachment data
                logger.info(f"{indent}Fetching attachment data for attachment_id: {attachment_id}")
                attachment_url = (
                    f"https://gmail.googleapis.com/gmail/v1/users/me/messages/"
                    f"{message_id}/attachments/{attachment_id}"
                )
                try:
                    attachment_data = await self._get_with_auth(client, attachment_url)
                    keys_info = (
                        f"{indent}Attachment data received with keys: "
                        f"{list(attachment_data.keys())}"
                    )
                    logger.debug(keys_info)
                    size = attachment_data.get("size", 0)
                    logger.info(f"{indent}Attachment size: {size} bytes")

                    # Create a dummy download URL (required by FileEntity)
                    # We'll actually use the content directly, but this satisfies the schema
                    dummy_download_url = f"gmail://attachment/{message_id}/{attachment_id}"

                    # Create file entity
                    file_entity = GmailAttachmentEntity(
                        entity_id=f"{message_id}_{attachment_id}",
                        breadcrumbs=breadcrumbs,
                        file_id=attachment_id,
                        name=filename,
                        mime_type=mime_type,
                        size=size,
                        total_size=size,
                        download_url=dummy_download_url,  # Required by FileEntity
                        message_id=message_id,
                        attachment_id=attachment_id,
                        thread_id=thread_id,
                    )

                    # Get base64 data
                    base64_data = attachment_data.get("data", "")
                    if not base64_data:
                        logger.warning(f"{indent}No data found for attachment {filename}")
                        return

                    # Decode the base64 data
                    binary_data = base64.urlsafe_b64decode(base64_data)

                    # Create a memory stream from the decoded data
                    async def content_stream():
                        yield binary_data

                    # Process using the BaseSource method (now abstracted)
                    logger.info(
                        f"{indent}Processing file entity for {filename} with direct content stream"
                    )
                    processed_entity = await self.process_file_entity_with_content(
                        file_entity=file_entity,
                        content_stream=content_stream(),
                        metadata={"source": "gmail", "message_id": message_id},
                    )

                    if processed_entity:
                        logger.info(f"{indent}Yielding processed attachment: {filename}")
                        yield processed_entity
                    else:
                        logger.warning(f"{indent}Processing failed for attachment: {filename}")

                except Exception as e:
                    logger.error(f"{indent}Error processing attachment {attachment_id}: {str(e)}")

            # Recursively process parts for multipart messages
            if part.get("parts"):
                sub_parts = part.get("parts", [])
                logger.debug(f"{indent}Part has {len(sub_parts)} sub-parts, recursing...")
                for sub_part in sub_parts:
                    async for attachment in find_attachments(sub_part, depth + 1):
                        yield attachment

        # Start processing from the top-level payload
        logger.info(f"Starting attachment search from top-level payload for message {message_id}")
        attachment_count = 0
        async for attachment in find_attachments(payload):
            attachment_count += 1
            yield attachment

        completion_msg = (
            f"Attachment processing complete for message {message_id}: "
            f"found {attachment_count} attachments"
        )
        logger.info(completion_msg)

    def _safe_filename(self, filename: str) -> str:
        """Create a safe version of a filename."""
        # Replace potentially problematic characters
        safe_name = "".join(c for c in filename if c.isalnum() or c in "._- ")
        return safe_name.strip()

    async def generate_entities(self) -> AsyncGenerator[ChunkEntity, None]:
        """Generate all Gmail entities: Threads, Messages, and Attachments."""
        logger.info("===== STARTING GMAIL ENTITY GENERATION =====")
        entity_count = 0
        try:
            async with httpx.AsyncClient() as client:
                logger.info("HTTP client created, starting entity generation")
                # Generate thread entities (which also generates messages and attachments)
                async for entity in self._generate_thread_entities(client):
                    entity_count += 1
                    entity_type = type(entity).__name__
                    logger.info(
                        f"Yielding entity #{entity_count}: {entity_type} with ID {entity.entity_id}"
                    )
                    yield entity
        except Exception as e:
            logger.error(f"Error in entity generation: {str(e)}", exc_info=True)
            raise
        finally:
            logger.info(f"===== GMAIL ENTITY GENERATION COMPLETE: {entity_count} entities =====")
