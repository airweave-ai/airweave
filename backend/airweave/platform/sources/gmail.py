"""Gmail source implementation for syncing email threads, messages, and attachments.

Now supports two flows:
  - Non-batching / sequential (default): preserves original behavior.
  - Batching / concurrent (opt-in): gated by `batch_generation` config and uses the
    bounded-concurrency driver in BaseSource across all major I/O points:
      * Thread detail fetch + per-thread processing
      * Per-thread message processing
      * Per-message attachment fetch & processing
      * Incremental history message-detail fetch

Config (all optional, shown with defaults):
    {
        "batch_generation": False,     # enable/disable concurrent generation
        "batch_size": 30,              # max concurrent workers
        "max_queue_size": 200,         # backpressure queue size
        "preserve_order": False,       # maintain item order per batch
        "stop_on_error": False         # cancel all on first error
    }
"""

import asyncio
import base64
from datetime import datetime
from typing import Any, AsyncGenerator, Dict, List, Optional, Set

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from airweave.core.logging import logger
from airweave.platform.decorators import source
from airweave.platform.entities._base import Breadcrumb, ChunkEntity
from airweave.platform.entities.gmail import (
    GmailAttachmentEntity,
    GmailMessageDeletionEntity,
    GmailMessageEntity,
    GmailThreadEntity,
)
from airweave.platform.sources._base import BaseSource
from airweave.schemas.source_connection import AuthenticationMethod, OAuthType


@source(
    name="Gmail",
    short_name="gmail",
    auth_methods=[
        AuthenticationMethod.OAUTH_BROWSER,
        AuthenticationMethod.OAUTH_TOKEN,
        AuthenticationMethod.AUTH_PROVIDER,
    ],
    oauth_type=OAuthType.WITH_REFRESH,
    requires_byoc=True,
    auth_config_class=None,
    config_class="GmailConfig",
    labels=["Communication", "Email"],
)
class GmailSource(BaseSource):
    """Gmail source connector integrates with the Gmail API to extract and synchronize email data.

    Connects to your Gmail account.

    It supports syncing email threads, individual messages, and file attachments.
    """

    # -----------------------
    # Construction / Config
    # -----------------------
    @classmethod
    async def create(
        cls, access_token: str, config: Optional[Dict[str, Any]] = None
    ) -> "GmailSource":
        """Create a new Gmail source instance with the provided OAuth access token."""
        logger.info("Creating new GmailSource instance")
        instance = cls()
        instance.access_token = access_token

        # Concurrency configuration (matches pattern used by other connectors)
        config = config or {}
        instance.batch_generation = bool(config.get("batch_generation", False))
        instance.batch_size = int(config.get("batch_size", 30))
        instance.max_queue_size = int(config.get("max_queue_size", 200))
        instance.preserve_order = bool(config.get("preserve_order", False))
        instance.stop_on_error = bool(config.get("stop_on_error", False))

        logger.info(f"GmailSource instance created with config: {config}")
        return instance

    # -----------------------
    # HTTP helpers
    # -----------------------
    @retry(
        stop=stop_after_attempt(5), wait=wait_exponential(multiplier=1, min=2, max=60), reraise=True
    )
    async def _get_with_auth(
        self, client: httpx.AsyncClient, url: str, params: Optional[dict] = None
    ) -> dict:
        """Make an authenticated GET request to the Gmail API with proper 429 handling."""
        self.logger.info(f"Making authenticated GET request to: {url} with params: {params}")

        # Get fresh token (will refresh if needed)
        access_token = await self.get_access_token()
        headers = {"Authorization": f"Bearer {access_token}"}

        response = await client.get(url, headers=headers, params=params)

        # Handle 401 errors by refreshing token and retrying
        if response.status_code == 401:
            self.logger.warning(
                f"Got 401 Unauthorized from Gmail API at {url}, refreshing token..."
            )
            await self.refresh_on_unauthorized()

            # Get new token and retry
            access_token = await self.get_access_token()
            headers = {"Authorization": f"Bearer {access_token}"}
            response = await client.get(url, headers=headers, params=params)

        # Handle 429 rate limiting errors by respecting Retry-After header
        if response.status_code == 429:
            self.logger.warning(
                f"Got 429 Rate Limited from Gmail API. Headers: {response.headers}. "
                f"Body: {response.text}."
            )

        response.raise_for_status()
        data = response.json()
        self.logger.info(f"Received response from {url} - Status: {response.status_code}")
        self.logger.debug(f"Response data keys: {list(data.keys())}")
        return data

    # -----------------------
    # Cursor helpers
    # -----------------------
    def get_default_cursor_field(self) -> Optional[str]:
        """Default cursor field for Gmail incremental sync.

        Gmail uses historyId for incremental changes. We'll store it under a named cursor field.
        """
        return "history_id"

    def validate_cursor_field(self, cursor_field: str) -> None:
        """Validate the cursor field for Gmail incremental sync."""
        valid_field = self.get_default_cursor_field()
        if cursor_field != valid_field:
            raise ValueError(
                f"Invalid cursor field '{cursor_field}' for Gmail. Use '{valid_field}'."
            )

    def _get_cursor_data(self) -> Dict[str, Any]:
        if self.cursor:
            return self.cursor.cursor_data or {}
        return {}

    def _update_cursor_data(self, new_history_id: str) -> None:
        if not self.cursor:
            return
        cursor_field = self.get_effective_cursor_field() or self.get_default_cursor_field()
        if not cursor_field:
            return
        if not self.cursor.cursor_data:
            self.cursor.cursor_data = {}
        self.cursor.cursor_data[cursor_field] = new_history_id

    async def _resolve_cursor_and_token(self) -> tuple[Optional[str], Optional[str]]:
        cursor_field = self.get_effective_cursor_field() or self.get_default_cursor_field()
        if cursor_field and cursor_field != self.get_default_cursor_field():
            self.validate_cursor_field(cursor_field)
        cursor_data = self._get_cursor_data()
        last_history_id = cursor_data.get(cursor_field) if cursor_field else None
        return cursor_field, last_history_id

    # -----------------------
    # Listing helpers
    # -----------------------
    async def _list_threads(self, client: httpx.AsyncClient) -> AsyncGenerator[Dict, None]:
        """Yield thread summary objects across all pages."""
        base_url = "https://gmail.googleapis.com/gmail/v1/users/me/threads"
        params = {"maxResults": 100}
        page_count = 0

        while True:
            page_count += 1
            self.logger.info(f"Fetching thread list page #{page_count} with params: {params}")
            data = await self._get_with_auth(client, base_url, params=params)
            threads = data.get("threads", []) or []
            self.logger.info(f"Found {len(threads)} threads on page {page_count}")

            for thread_info in threads:
                yield thread_info

            next_page_token = data.get("nextPageToken")
            if not next_page_token:
                self.logger.info(f"No more thread pages after page {page_count}")
                break
            params["pageToken"] = next_page_token

    async def _fetch_thread_detail(self, client: httpx.AsyncClient, thread_id: str) -> Dict:
        """Fetch full thread details including messages."""
        base_url = "https://gmail.googleapis.com/gmail/v1/users/me/threads"
        detail_url = f"{base_url}/{thread_id}"
        self.logger.info(f"Fetching full thread details from: {detail_url}")
        thread_data = await self._get_with_auth(client, detail_url)
        return thread_data

    # -----------------------
    # Entity generation (threads/messages/attachments)
    # -----------------------
    async def _generate_thread_entities(
        self, client: httpx.AsyncClient, processed_message_ids: Set[str]
    ) -> AsyncGenerator[ChunkEntity, None]:
        """Generate GmailThreadEntity objects and associated message entities.

        Two modes:
          - Sequential: iterate threads, fetch details, process messages in-order.
          - Concurrent: run per-thread workers (and within each, per-message workers).
        """
        if not getattr(self, "batch_generation", False):
            # --- Non-batching / sequential path (original behavior) ---
            async for thread_info in self._list_threads(client):
                thread_id = thread_info["id"]
                thread_data = await self._fetch_thread_detail(client, thread_id)
                # Yield thread entity, then process messages sequentially
                async for e in self._emit_thread_and_messages(
                    client, thread_id, thread_data, processed_message_ids
                ):
                    yield e
            return

        # --- Batching / concurrent path ---
        # We'll process threads concurrently. Inside each thread, messages can also be
        # processed concurrently. We still use a shared set to dedupe message IDs.
        lock = asyncio.Lock()

        async def _thread_worker(thread_info: Dict):
            thread_id = thread_info.get("id")
            if not thread_id:
                return
            try:
                thread_data = await self._fetch_thread_detail(client, thread_id)
                async for ent in self._emit_thread_and_messages(
                    client, thread_id, thread_data, processed_message_ids, lock=lock
                ):
                    yield ent
            except Exception as e:
                self.logger.error(f"Error processing thread {thread_id}: {e}", exc_info=True)

        async for ent in self.process_entities_concurrent(
            items=self._list_threads(client),
            worker=_thread_worker,
            batch_size=getattr(self, "batch_size", 30),
            preserve_order=getattr(self, "preserve_order", False),
            stop_on_error=getattr(self, "stop_on_error", False),
            max_queue_size=getattr(self, "max_queue_size", 200),
        ):
            if ent is not None:
                yield ent

    async def _create_thread_entity(self, thread_id: str, thread_data: Dict) -> GmailThreadEntity:
        """Create a thread entity from thread data."""
        snippet = thread_data.get("snippet", "")
        history_id = thread_data.get("historyId")
        message_list = thread_data.get("messages", []) or []

        # Calculate metadata
        message_count = len(message_list)
        last_message_date = None
        if message_list:
            sorted_msgs = sorted(
                message_list, key=lambda m: int(m.get("internalDate", 0)), reverse=True
            )
            last_message_date_ms = sorted_msgs[0].get("internalDate")
            if last_message_date_ms:
                last_message_date = datetime.utcfromtimestamp(int(last_message_date_ms) / 1000)

        label_ids = message_list[0].get("labelIds", []) if message_list else []

        return GmailThreadEntity(
            entity_id=f"thread_{thread_id}",  # Prefix to ensure uniqueness
            breadcrumbs=[],  # Thread is top-level
            snippet=snippet,
            history_id=history_id,
            message_count=message_count,
            label_ids=label_ids,
            last_message_date=last_message_date,
        )

    async def _process_thread_messages(
        self,
        client: httpx.AsyncClient,
        message_list: List[Dict],
        thread_id: str,
        thread_breadcrumb: Breadcrumb,
        processed_message_ids: Set[str],
        lock: Optional[asyncio.Lock],
    ) -> AsyncGenerator[ChunkEntity, None]:
        """Process messages in a thread, either sequentially or concurrently."""
        if not getattr(self, "batch_generation", False):
            for message_data in message_list:
                msg_id = message_data.get("id", "unknown")
                if await self._should_skip_message(msg_id, processed_message_ids, lock=None):
                    continue
                async for entity in self._process_message(
                    client, message_data, thread_id, thread_breadcrumb
                ):
                    yield entity
            return

        # Concurrent per-message workers
        async def _message_worker(message_data: Dict):
            msg_id = message_data.get("id", "unknown")
            if await self._should_skip_message(msg_id, processed_message_ids, lock=lock):
                return
            async for ent in self._process_message(
                client, message_data, thread_id, thread_breadcrumb
            ):
                yield ent

        async for ent in self.process_entities_concurrent(
            items=message_list,
            worker=_message_worker,
            batch_size=getattr(self, "batch_size", 30),
            preserve_order=getattr(self, "preserve_order", False),
            stop_on_error=getattr(self, "stop_on_error", False),
            max_queue_size=getattr(self, "max_queue_size", 200),
        ):
            if ent is not None:
                yield ent

    async def _emit_thread_and_messages(
        self,
        client: httpx.AsyncClient,
        thread_id: str,
        thread_data: Dict,
        processed_message_ids: Set[str],
        lock: Optional[asyncio.Lock] = None,
    ) -> AsyncGenerator[ChunkEntity, None]:
        """Emit a thread entity and then all entities from its messages.

        If a lock is provided, use it to dedupe message IDs safely under concurrency.
        """
        # Create and yield thread entity
        thread_entity = await self._create_thread_entity(thread_id, thread_data)
        self.logger.info(f"Yielding thread entity: {thread_id}")
        yield thread_entity

        # Breadcrumb for messages under this thread
        thread_breadcrumb = Breadcrumb(
            entity_id=f"thread_{thread_id}",  # Match the thread entity's ID
            name=(
                thread_entity.snippet[:50] + "..."
                if len(thread_entity.snippet) > 50
                else thread_entity.snippet
            ),
            type="thread",
        )

        # Process messages
        message_list = thread_data.get("messages", []) or []
        async for entity in self._process_thread_messages(
            client, message_list, thread_id, thread_breadcrumb, processed_message_ids, lock
        ):
            yield entity

    async def _should_skip_message(
        self, msg_id: str, processed_message_ids: Set[str], lock: Optional[asyncio.Lock]
    ) -> bool:
        """Check and mark message as processed. Uses lock if provided."""
        if not msg_id:
            return True
        if lock is None:
            if msg_id in processed_message_ids:
                self.logger.info(f"Skipping message {msg_id} - already processed")
                return True
            processed_message_ids.add(msg_id)
            return False
        async with lock:
            if msg_id in processed_message_ids:
                self.logger.info(f"Skipping message {msg_id} - already processed")
                return True
            processed_message_ids.add(msg_id)
            return False

    async def _process_message(  # noqa: C901
        self,
        client: httpx.AsyncClient,
        message_data: Dict,
        thread_id: str,
        thread_breadcrumb: Breadcrumb,
    ) -> AsyncGenerator[ChunkEntity, None]:
        """Process a message and its attachments."""
        # Get detailed message data if needed
        message_id = message_data.get("id")
        self.logger.info(f"Processing message ID: {message_id} in thread: {thread_id}")

        if "payload" not in message_data:
            self.logger.info(
                f"Payload not in message data, fetching full message details for {message_id}"
            )
            message_url = f"https://gmail.googleapis.com/gmail/v1/users/me/messages/{message_id}"
            message_data = await self._get_with_auth(client, message_url)
            self.logger.debug(f"Fetched full message data with keys: {list(message_data.keys())}")
        else:
            self.logger.debug("Message already contains payload data")

        # Extract message fields
        self.logger.info(f"Extracting fields for message {message_id}")
        internal_date_ms = message_data.get("internalDate")
        internal_date = None
        if internal_date_ms:
            internal_date = datetime.utcfromtimestamp(int(internal_date_ms) / 1000)
            self.logger.debug(f"Internal date: {internal_date}")

        payload = message_data.get("payload", {}) or {}
        headers = payload.get("headers", []) or []

        # Parse headers
        self.logger.info(f"Parsing headers for message {message_id}")
        subject = None
        sender = None
        to_list: List[str] = []
        cc_list: List[str] = []
        bcc_list: List[str] = []
        date = None

        for header in headers:
            name = header.get("name", "").lower()
            value = header.get("value", "")
            if name == "subject":
                subject = value
            elif name == "from":
                sender = value
            elif name == "to":
                to_list = [addr.strip() for addr in value.split(",")] if value else []
            elif name == "cc":
                cc_list = [addr.strip() for addr in value.split(",")] if value else []
            elif name == "bcc":
                bcc_list = [addr.strip() for addr in value.split(",")] if value else []
            elif name == "date":
                try:
                    from email.utils import parsedate_to_datetime

                    date = parsedate_to_datetime(value)
                except (TypeError, ValueError):
                    self.logger.warning(f"Failed to parse date header: {value}")

        # Extract message body
        self.logger.info(f"Extracting body content for message {message_id}")
        body_plain, body_html = self._extract_body_content(payload)

        # Create message entity
        self.logger.info(f"Creating message entity for message {message_id}")
        message_entity = GmailMessageEntity(
            entity_id=f"msg_{message_id}",  # Prefix to ensure uniqueness
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
        self.logger.debug(f"Message entity created with ID: {message_entity.entity_id}")
        yield message_entity
        self.logger.info(f"Message entity yielded for {message_id}")

        # Breadcrumb for attachments
        message_breadcrumb = Breadcrumb(
            entity_id=f"msg_{message_id}",  # Match the message entity's ID
            name=subject or f"Message {message_id}",
            type="message",
        )

        # Process attachments (sequential vs concurrent)
        async for attachment_entity in self._process_attachments(
            client, payload, message_id, thread_id, [thread_breadcrumb, message_breadcrumb]
        ):
            yield attachment_entity

    def _extract_body_content(self, payload: Dict) -> tuple:  # noqa: C901
        """Extract plain text and HTML body content from message payload."""
        self.logger.info("Extracting body content from message payload")
        body_plain = None
        body_html = None

        # Function to recursively extract body parts
        def extract_from_parts(parts, depth=0):
            p_txt, p_html = None, None

            for part in parts:
                mime_type = part.get("mimeType", "")
                body = part.get("body", {}) or {}

                # Check if part has data
                if body.get("data"):
                    data = body.get("data")
                    try:
                        decoded = base64.urlsafe_b64decode(data).decode("utf-8", errors="ignore")
                        if mime_type == "text/plain" and not p_txt:
                            p_txt = decoded
                        elif mime_type == "text/html" and not p_html:
                            p_html = decoded
                    except Exception as e:
                        self.logger.error(f"Error decoding body content: {str(e)}")

                # Check if part has sub-parts
                elif part.get("parts"):
                    sub_txt, sub_html = extract_from_parts(part.get("parts", []), depth + 1)
                    if not p_txt:
                        p_txt = sub_txt
                    if not p_html:
                        p_html = sub_html

            return p_txt, p_html

        # Handle multipart messages
        if payload.get("parts"):
            parts = payload.get("parts", [])
            body_plain, body_html = extract_from_parts(parts)
        # Handle single part messages
        else:
            mime_type = payload.get("mimeType", "")
            body = payload.get("body", {}) or {}
            if body.get("data"):
                data = body.get("data")
                try:
                    decoded = base64.urlsafe_b64decode(data).decode("utf-8", errors="ignore")
                    if mime_type == "text/plain":
                        body_plain = decoded
                    elif mime_type == "text/html":
                        body_html = decoded
                except Exception as e:
                    self.logger.error(f"Error decoding single part body: {str(e)}")

        self.logger.info(
            f"Body extraction complete: found_text={bool(body_plain)}, found_html={bool(body_html)}"
        )
        return body_plain, body_html

    # -----------------------
    # Attachments
    # -----------------------
    async def _process_attachments(  # noqa: C901
        self,
        client: httpx.AsyncClient,
        payload: Dict,
        message_id: str,
        thread_id: str,
        breadcrumbs: List[Breadcrumb],
    ) -> AsyncGenerator[GmailAttachmentEntity, None]:
        """Process message attachments using the standard file processing pipeline.

        In concurrent mode, we first discover attachment descriptors, then process them
        via the bounded concurrency driver. In sequential mode, we stream them one-by-one.
        """

        # Helper: recursively collect candidate attachment descriptors (no network yet)
        def collect_attachment_descriptors(part, out: List[Dict], depth=0):
            mime_type = part.get("mimeType", "")
            filename = part.get("filename", "")
            body = part.get("body", {}) or {}

            # If part has filename and is not an inline image or text part, treat as attachment
            if (
                filename
                and mime_type not in ("text/plain", "text/html")
                and not (mime_type.startswith("image/") and not filename)
            ):
                attachment_id = body.get("attachmentId")
                if attachment_id:
                    out.append(
                        {
                            "mime_type": mime_type,
                            "filename": filename,
                            "attachment_id": attachment_id,
                        }
                    )

            # Recurse into sub-parts
            for sub in part.get("parts", []) or []:
                collect_attachment_descriptors(sub, out, depth + 1)

        # Build descriptor list
        descriptors: List[Dict] = []
        if payload:
            collect_attachment_descriptors(payload, descriptors)

        if not descriptors:
            return

        # --- Concurrent path ---
        if getattr(self, "batch_generation", False):

            async def _attachment_worker(descriptor: Dict):
                mime_type = descriptor["mime_type"]
                filename = descriptor["filename"]
                attachment_id = descriptor["attachment_id"]

                attachment_url = (
                    f"https://gmail.googleapis.com/gmail/v1/users/me/messages/"
                    f"{message_id}/attachments/{attachment_id}"
                )
                try:
                    attachment_data = await self._get_with_auth(client, attachment_url)
                    size = attachment_data.get("size", 0)

                    # Create FileEntity wrapper
                    file_entity = GmailAttachmentEntity(
                        entity_id=f"attach_{message_id}_{attachment_id}",
                        breadcrumbs=breadcrumbs,
                        file_id=attachment_id,
                        name=filename,
                        mime_type=mime_type,
                        size=size,
                        total_size=size,
                        download_url=f"gmail://attachment/{message_id}/{attachment_id}",  # dummy
                        message_id=message_id,
                        attachment_id=attachment_id,
                        thread_id=thread_id,
                    )

                    base64_data = attachment_data.get("data", "")
                    if not base64_data:
                        self.logger.warning(f"No data found for attachment {filename}")
                        return

                    binary_data = base64.urlsafe_b64decode(base64_data)

                    async def content_stream(data=binary_data):
                        yield data

                    processed_entity = await self.process_file_entity_with_content(
                        file_entity=file_entity,
                        content_stream=content_stream(),
                        metadata={"source": "gmail", "message_id": message_id},
                    )
                    if processed_entity:
                        yield processed_entity
                except Exception as e:
                    self.logger.error(
                        f"Error processing attachment {attachment_id} on message {message_id}: {e}"
                    )

            async for ent in self.process_entities_concurrent(
                items=descriptors,
                worker=_attachment_worker,
                batch_size=getattr(self, "batch_size", 30),
                preserve_order=getattr(self, "preserve_order", False),
                stop_on_error=getattr(self, "stop_on_error", False),
                max_queue_size=getattr(self, "max_queue_size", 200),
            ):
                if ent is not None:
                    yield ent
            return

        # --- Sequential path (original logic) ---
        async def _sequential_iter():
            # Implement the previous behavior: fetch, decode, process, yield
            for descriptor in descriptors:
                mime_type = descriptor["mime_type"]
                filename = descriptor["filename"]
                attachment_id = descriptor["attachment_id"]

                attachment_url = (
                    f"https://gmail.googleapis.com/gmail/v1/users/me/messages/"
                    f"{message_id}/attachments/{attachment_id}"
                )
                try:
                    attachment_data = await self._get_with_auth(client, attachment_url)
                    size = attachment_data.get("size", 0)

                    file_entity = GmailAttachmentEntity(
                        entity_id=f"attach_{message_id}_{attachment_id}",
                        breadcrumbs=breadcrumbs,
                        file_id=attachment_id,
                        name=filename,
                        mime_type=mime_type,
                        size=size,
                        total_size=size,
                        download_url=f"gmail://attachment/{message_id}/{attachment_id}",
                        message_id=message_id,
                        attachment_id=attachment_id,
                        thread_id=thread_id,
                    )

                    base64_data = attachment_data.get("data", "")
                    if not base64_data:
                        self.logger.warning(f"No data found for attachment {filename}")
                        continue

                    binary_data = base64.urlsafe_b64decode(base64_data)

                    async def content_stream(data=binary_data):
                        yield data

                    processed_entity = await self.process_file_entity_with_content(
                        file_entity=file_entity,
                        content_stream=content_stream(),
                        metadata={"source": "gmail", "message_id": message_id},
                    )
                    if processed_entity:
                        yield processed_entity
                    else:
                        self.logger.warning(f"Processing failed for attachment: {filename}")
                except Exception as e:
                    self.logger.error(f"Error processing attachment {attachment_id}: {str(e)}")

        async for a in _sequential_iter():
            yield a

    def _safe_filename(self, filename: str) -> str:
        """Create a safe version of a filename."""
        # Replace potentially problematic characters
        safe_name = "".join(c for c in filename if c.isalnum() or c in "._- ")
        return safe_name.strip()

    # -----------------------
    # Incremental sync
    # -----------------------
    async def _run_incremental_sync(
        self, client: httpx.AsyncClient, start_history_id: str
    ) -> AsyncGenerator[ChunkEntity, None]:
        """Run Gmail incremental sync using users.history.list pages."""
        base_url = "https://gmail.googleapis.com/gmail/v1/users/me/history"
        params: Dict[str, Any] = {
            "startHistoryId": start_history_id,
            "maxResults": 500,
        }
        latest_history_id: Optional[str] = None

        while True:
            data = await self._get_with_auth(client, base_url, params=params)

            # Deletions: lightweight; process sequentially
            async for deletion in self._yield_history_deletions(data):
                yield deletion

            # Additions: potentially heavy (network per message); support concurrency
            async for addition in self._yield_history_additions(client, data):
                yield addition

            latest_history_id = data.get("historyId") or latest_history_id

            next_token = data.get("nextPageToken")
            if next_token:
                params["pageToken"] = next_token
            else:
                break

        if latest_history_id:
            self._update_cursor_data(str(latest_history_id))
            self.logger.info("Updated Gmail cursor with latest historyId for next run")

    async def _yield_history_deletions(
        self, data: Dict[str, Any]
    ) -> AsyncGenerator[ChunkEntity, None]:
        """Yield deletion entities from a history page."""
        for h in data.get("history", []) or []:
            for deleted in h.get("messagesDeleted", []) or []:
                msg = deleted.get("message") or {}
                msg_id = msg.get("id")
                thread_id = msg.get("threadId")
                if not msg_id:
                    continue
                yield GmailMessageDeletionEntity(
                    entity_id=f"msg_{msg_id}",
                    message_id=msg_id,
                    thread_id=thread_id,
                    deletion_status="removed",
                )

    async def _process_history_additions_sequential(
        self, client: httpx.AsyncClient, items: List[Dict[str, str]]
    ) -> AsyncGenerator[ChunkEntity, None]:
        """Process history additions sequentially."""
        for it in items:
            msg_id = it["msg_id"]
            thread_id = it.get("thread_id") or "unknown"
            try:
                detail_url = f"https://gmail.googleapis.com/gmail/v1/users/me/messages/{msg_id}"
                message_data = await self._get_with_auth(client, detail_url)
                thread_breadcrumb = Breadcrumb(
                    entity_id=f"thread_{thread_id}",
                    name=f"Thread {thread_id}",
                    type="thread",
                )
                async for entity in self._process_message(
                    client, message_data, thread_id, thread_breadcrumb
                ):
                    yield entity
            except Exception as e:
                self.logger.error(f"Failed to fetch/process message {msg_id}: {e}")

    async def _process_history_additions_concurrent(
        self, client: httpx.AsyncClient, items: List[Dict[str, str]]
    ) -> AsyncGenerator[ChunkEntity, None]:
        """Process history additions concurrently."""

        async def _added_worker(item: Dict[str, str]):
            msg_id = item["msg_id"]
            thread_id = item.get("thread_id") or "unknown"
            try:
                detail_url = f"https://gmail.googleapis.com/gmail/v1/users/me/messages/{msg_id}"
                message_data = await self._get_with_auth(client, detail_url)
                thread_breadcrumb = Breadcrumb(
                    entity_id=f"thread_{thread_id}",
                    name=f"Thread {thread_id}",
                    type="thread",
                )
                async for ent in self._process_message(
                    client, message_data, thread_id, thread_breadcrumb
                ):
                    yield ent
            except Exception as e:
                self.logger.error(f"Failed to fetch/process message {msg_id}: {e}")

        async for ent in self.process_entities_concurrent(
            items=items,
            worker=_added_worker,
            batch_size=getattr(self, "batch_size", 30),
            preserve_order=getattr(self, "preserve_order", False),
            stop_on_error=getattr(self, "stop_on_error", False),
            max_queue_size=getattr(self, "max_queue_size", 200),
        ):
            if ent is not None:
                yield ent

    async def _yield_history_additions(
        self, client: httpx.AsyncClient, data: Dict[str, Any]
    ) -> AsyncGenerator[ChunkEntity, None]:
        """Yield entities for added/changed messages from a history page.

        If batch_generation is enabled, fetch message details concurrently.
        """
        # Flatten all message IDs from this page
        items: List[Dict[str, str]] = []
        for h in data.get("history", []) or []:
            for added in h.get("messagesAdded", []) or []:
                msg = added.get("message") or {}
                msg_id = msg.get("id")
                thread_id = msg.get("threadId")
                if msg_id:
                    items.append({"msg_id": msg_id, "thread_id": thread_id})

        if not items:
            return

        if not getattr(self, "batch_generation", False):
            async for entity in self._process_history_additions_sequential(client, items):
                yield entity
        else:
            async for entity in self._process_history_additions_concurrent(client, items):
                yield entity

    # -----------------------
    # Top-level orchestration
    # -----------------------
    async def generate_entities(self) -> AsyncGenerator[ChunkEntity, None]:
        """Generate Gmail entities with incremental History API support."""
        try:
            async with self.http_client() as client:
                cursor_field, last_history_id = await self._resolve_cursor_and_token()
                if last_history_id:
                    async for e in self._run_incremental_sync(client, last_history_id):
                        yield e
                else:
                    processed_message_ids: Set[str] = set()
                    async for e in self._generate_thread_entities(client, processed_message_ids):
                        yield e

                    # Capture a starting historyId
                    try:
                        url = "https://gmail.googleapis.com/gmail/v1/users/me/messages"
                        latest_list = await self._get_with_auth(
                            client, url, params={"maxResults": 1}
                        )
                        msgs = latest_list.get("messages", [])
                        if msgs:
                            detail = await self._get_with_auth(
                                client,
                                f"https://gmail.googleapis.com/gmail/v1/users/me/messages/{msgs[0]['id']}",
                            )
                            history_id = detail.get("historyId")
                            if history_id:
                                self._update_cursor_data(str(history_id))
                                self.logger.info(
                                    "Stored Gmail historyId after full sync "
                                    "for next incremental run"
                                )
                    except Exception as e:
                        self.logger.error(f"Failed to capture starting Gmail historyId: {e}")

        except Exception as e:
            self.logger.error(f"Error in entity generation: {str(e)}", exc_info=True)
            raise

    async def validate(self) -> bool:
        """Verify Gmail OAuth2 token by pinging the users.getProfile endpoint."""
        return await self._validate_oauth2(
            ping_url="https://gmail.googleapis.com/gmail/v1/users/me/profile",
            headers={"Accept": "application/json"},
            timeout=10.0,
        )
