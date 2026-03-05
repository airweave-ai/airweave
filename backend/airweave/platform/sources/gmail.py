"""Gmail source implementation for syncing email threads, messages, and attachments.

Uses concurrent/batching processing for optimal performance:
  * Thread detail fetch + per-thread processing
  * Per-thread message processing
  * Per-message attachment fetch & processing
  * Incremental history message-detail fetch
"""

import asyncio
import base64
from datetime import datetime
from typing import Any, AsyncGenerator, Dict, List, Optional, Set

import httpx
from tenacity import retry, stop_after_attempt

from airweave.core.logging import logger
from airweave.core.shared_models import RateLimitLevel
from airweave.platform.cursors import GmailCursor
from airweave.platform.configs.config import GmailConfig
from airweave.platform.decorators import source
from airweave.platform.entities._base import BaseEntity, Breadcrumb
from airweave.platform.entities.gmail import (
    GmailAttachmentEntity,
    GmailMessageDeletionEntity,
    GmailMessageEntity,
    GmailThreadEntity,
)
from airweave.platform.sources._base import BaseSource
from airweave.platform.sources.retry_helpers import (
    wait_rate_limit_with_backoff,
)
from airweave.platform.storage import FileSkippedException
from airweave.platform.utils.filename_utils import safe_filename
from airweave.schemas.source_connection import AuthenticationMethod, OAuthType


def _should_retry_gmail_request(exception: Exception) -> bool:
    """Custom retry condition that excludes 404 errors but includes 429 and timeouts."""
    if isinstance(exception, httpx.HTTPStatusError):
        # Don't retry 404s - let them pass through to call-site handlers
        if exception.response.status_code == 404:
            return False
        # Retry 429 rate limits
        if exception.response.status_code == 429:
            return True
        # Retry other HTTP errors
        return True
    # Retry timeouts
    if isinstance(exception, (httpx.ConnectTimeout, httpx.ReadTimeout)):
        return True
    return False


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
    config_class=GmailConfig,
    labels=["Communication", "Email"],
    supports_continuous=True,
    rate_limit_level=RateLimitLevel.ORG,
    cursor_class=GmailCursor,
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
        logger.debug("Creating new GmailSource instance")
        instance = cls()
        instance.access_token = access_token

        # Concurrency configuration (matches pattern used by other connectors)
        config = config or {}
        instance.batch_size = int(config.get("batch_size", 30))
        instance.max_queue_size = int(config.get("max_queue_size", 200))
        instance.preserve_order = bool(config.get("preserve_order", False))
        instance.stop_on_error = bool(config.get("stop_on_error", False))

        # Filter configuration
        instance.after_date = config.get("after_date")
        instance.included_labels = config.get("included_labels", ["inbox", "sent"])
        instance.excluded_labels = config.get("excluded_labels", ["spam", "trash"])
        instance.excluded_categories = config.get("excluded_categories", ["promotions", "social"])
        instance.gmail_query = config.get("gmail_query")

        logger.debug(f"GmailSource instance created with config: {config}")
        return instance

    def _build_gmail_query(self) -> Optional[str]:
        """Build Gmail API query string from filter configuration.

        Returns:
            Query string for Gmail API, or None if no filters configured.
        """
        # If custom query provided, use it directly
        if getattr(self, "gmail_query", None):
            self.logger.debug(f"Using custom Gmail query: {self.gmail_query}")
            return self.gmail_query

        query_parts = self._build_query_parts()

        if not query_parts:
            return None

        query = " ".join(query_parts)
        self.logger.debug(f"Built Gmail query: {query}")
        return query

    def _build_query_parts(self) -> List[str]:
        """Build individual query parts from filter configuration."""
        parts = []

        # Date filter
        if getattr(self, "after_date", None):
            parts.append(f"after:{self.after_date}")

        # Included labels (OR logic - wrap in parentheses with OR)
        included_labels = getattr(self, "included_labels", [])
        if included_labels:
            if len(included_labels) == 1:
                parts.append(f"in:{included_labels[0]}")
            else:
                # Gmail syntax: {in:inbox OR in:sent}
                label_parts = " OR ".join(f"in:{label}" for label in included_labels)
                parts.append(f"{{{label_parts}}}")

        # Excluded labels
        for label in getattr(self, "excluded_labels", []):
            parts.append(f"-in:{label}")

        # Excluded categories
        for category in getattr(self, "excluded_categories", []):
            parts.append(f"-category:{category}")

        return parts

    def _message_matches_filters(self, message_data: Dict) -> bool:
        """Check if a message matches the configured filters.

        Used for incremental syncs where we can't filter via query parameter.

        Args:
            message_data: Message data from Gmail API

        Returns:
            True if message matches filters, False otherwise
        """
        # If custom query is used, we can't filter post-fetch reliably
        if getattr(self, "gmail_query", None):
            return True

        # Check date filters
        if not self._message_matches_date_filters(message_data):
            return False

        # Check label filters
        if not self._message_matches_label_filters(message_data):
            return False

        return True

    def _message_matches_date_filters(self, message_data: Dict) -> bool:
        """Check if message matches after_date filter."""
        after_date = getattr(self, "after_date", None)
        if not after_date:
            return True

        internal_date_ms = message_data.get("internalDate")
        if not internal_date_ms:
            return True

        try:
            message_date = datetime.utcfromtimestamp(int(internal_date_ms) / 1000)
            after_dt = datetime.strptime(after_date, "%Y/%m/%d")
            if message_date < after_dt:
                self.logger.debug(f"Message {message_data.get('id')} skipped: before after_date")
                return False
        except (ValueError, TypeError) as e:
            self.logger.warning(f"Failed to parse date for message {message_data.get('id')}: {e}")

        return True

    def _message_matches_label_filters(self, message_data: Dict) -> bool:
        """Check if message matches label and category filters."""
        label_ids = message_data.get("labelIds", []) or []
        label_ids_lower = [label.lower() for label in label_ids]

        # Check included labels (at least one must match)
        included_labels = getattr(self, "included_labels", None)
        if included_labels:
            has_included = any(label.lower() in label_ids_lower for label in included_labels)
            if not has_included:
                self.logger.debug(
                    f"Message {message_data.get('id')} skipped: doesn't match included labels"
                )
                return False

        # Check excluded labels (none must match)
        excluded_labels = getattr(self, "excluded_labels", None)
        if excluded_labels:
            has_excluded = any(label.lower() in label_ids_lower for label in excluded_labels)
            if has_excluded:
                self.logger.debug(
                    f"Message {message_data.get('id')} skipped: matches excluded labels"
                )
                return False

        # Check excluded categories (none must match)
        excluded_categories = getattr(self, "excluded_categories", None)
        if excluded_categories:
            category_labels = [f"category_{cat.lower()}" for cat in excluded_categories]
            has_excluded_category = any(cat in label_ids_lower for cat in category_labels)
            if has_excluded_category:
                self.logger.debug(
                    f"Message {message_data.get('id')} skipped: matches excluded categories"
                )
                return False

        return True

    # -----------------------
    # HTTP helpers
    # -----------------------
    @retry(
        stop=stop_after_attempt(5),
        retry=_should_retry_gmail_request,
        wait=wait_rate_limit_with_backoff,
        reraise=True,
    )
    async def _get_with_auth(
        self, client: httpx.AsyncClient, url: str, params: Optional[dict] = None
    ) -> dict:
        """Make an authenticated GET request to the Gmail API with proper 429 handling."""
        self.logger.debug(f"Making authenticated GET request to: {url} with params: {params}")

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
        self.logger.debug(f"Received response from {url} - Status: {response.status_code}")
        self.logger.debug(f"Response data keys: {list(data.keys())}")
        return data

    # -----------------------
    # Cursor helper
    # -----------------------
    async def _resolve_cursor(self) -> Optional[str]:
        """Get last history ID from cursor if available."""
        cursor_data = self.cursor.data if self.cursor else {}
        return cursor_data.get("history_id")

    # -----------------------
    # Listing helpers
    # -----------------------
    async def _list_threads(self, client: httpx.AsyncClient) -> AsyncGenerator[Dict, None]:
        """Yield thread summary objects across all pages."""
        base_url = "https://gmail.googleapis.com/gmail/v1/users/me/threads"
        params = {"maxResults": 100}

        # Add query filter if configured
        query = self._build_gmail_query()
        if query:
            params["q"] = query
            self.logger.debug(f"Filtering threads with query: {query}")

        page_count = 0

        while True:
            page_count += 1
            self.logger.debug(f"Fetching thread list page #{page_count} with params: {params}")
            data = await self._get_with_auth(client, base_url, params=params)
            threads = data.get("threads", []) or []
            self.logger.debug(f"Found {len(threads)} threads on page {page_count}")

            for thread_info in threads:
                yield thread_info

            next_page_token = data.get("nextPageToken")
            if not next_page_token:
                self.logger.debug(f"No more thread pages after page {page_count}")
                break
            params["pageToken"] = next_page_token

    async def _fetch_thread_detail(self, client: httpx.AsyncClient, thread_id: str) -> Dict:
        """Fetch full thread details including messages."""
        base_url = "https://gmail.googleapis.com/gmail/v1/users/me/threads"
        detail_url = f"{base_url}/{thread_id}"
        self.logger.debug(f"Fetching full thread details from: {detail_url}")
        try:
            thread_data = await self._get_with_auth(client, detail_url)
            return thread_data
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                self.logger.warning(f"Thread {thread_id} not found (404) - skipping")
                return None
            raise

    # -----------------------
    # Entity generation (threads/messages/attachments)
    # -----------------------
    async def _generate_thread_entities(  # noqa: C901
        self, client: httpx.AsyncClient, processed_message_ids: Set[str]
    ) -> AsyncGenerator[BaseEntity, None]:
        """Generate GmailThreadEntity objects and associated message entities.

        Processes threads concurrently with per-thread message processing.
        Uses a shared lock to dedupe message IDs safely under concurrency.
        """
        lock = asyncio.Lock()

        async def _thread_worker(thread_info: Dict):
            thread_id = thread_info.get("id")
            if not thread_id:
                return
            try:
                thread_data = await self._fetch_thread_detail(client, thread_id)
                if not thread_data:
                    return
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

        # Create name from snippet
        thread_name = snippet[:50] + "..." if len(snippet) > 50 else snippet or "Thread"

        return GmailThreadEntity(
            breadcrumbs=[],
            thread_key=f"thread_{thread_id}",
            gmail_thread_id=thread_id,
            title=thread_name,
            last_message_at=last_message_date,
            snippet=snippet,
            history_id=history_id,
            message_count=message_count,
            label_ids=label_ids,
        )

    async def _process_thread_messages(
        self,
        client: httpx.AsyncClient,
        message_list: List[Dict],
        thread_id: str,
        thread_breadcrumb: Breadcrumb,
        processed_message_ids: Set[str],
        lock: Optional[asyncio.Lock],
    ) -> AsyncGenerator[BaseEntity, None]:
        """Process messages in a thread concurrently."""

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
    ) -> AsyncGenerator[BaseEntity, None]:
        """Emit a thread entity and then all entities from its messages.

        If a lock is provided, use it to dedupe message IDs safely under concurrency.
        """
        # Create and yield thread entity
        thread_entity = await self._create_thread_entity(thread_id, thread_data)
        self.logger.debug(f"Yielding thread entity: {thread_id}")
        yield thread_entity

        # Breadcrumb for messages under this thread
        thread_breadcrumb = Breadcrumb(
            entity_id=thread_entity.thread_key,
            name=thread_entity.title,
            entity_type=GmailThreadEntity.__name__,
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
                self.logger.debug(f"Skipping message {msg_id} - already processed")
                return True
            processed_message_ids.add(msg_id)
            return False
        async with lock:
            if msg_id in processed_message_ids:
                self.logger.debug(f"Skipping message {msg_id} - already processed")
                return True
            processed_message_ids.add(msg_id)
            return False

    async def _process_message(  # noqa: C901
        self,
        client: httpx.AsyncClient,
        message_data: Dict,
        thread_id: str,
        thread_breadcrumb: Breadcrumb,
    ) -> AsyncGenerator[BaseEntity, None]:
        """Process a message and its attachments."""
        # Get detailed message data if needed
        message_id = message_data.get("id")
        self.logger.debug(f"Processing message ID: {message_id} in thread: {thread_id}")

        if "payload" not in message_data:
            self.logger.debug(
                f"Payload not in message data, fetching full message details for {message_id}"
            )
            message_url = f"https://gmail.googleapis.com/gmail/v1/users/me/messages/{message_id}"
            try:
                message_data = await self._get_with_auth(client, message_url)
                self.logger.debug(
                    f"Fetched full message data with keys: {list(message_data.keys())}"
                )
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 404:
                    self.logger.warning(f"Message {message_id} not found (404) - skipping")
                    return
                raise
        else:
            self.logger.debug("Message already contains payload data")

        # Extract message fields
        self.logger.debug(f"Extracting fields for message {message_id}")
        internal_date_ms = message_data.get("internalDate")
        internal_date = None
        if internal_date_ms:
            internal_date = datetime.utcfromtimestamp(int(internal_date_ms) / 1000)
            self.logger.debug(f"Internal date: {internal_date}")

        payload = message_data.get("payload", {}) or {}
        headers = payload.get("headers", []) or []

        # Parse headers
        self.logger.debug(f"Parsing headers for message {message_id}")
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
        self.logger.debug(f"Extracting body content for message {message_id}")
        body_plain, body_html = self._extract_body_content(payload)

        # Create message entity
        self.logger.debug(f"Creating message entity for message {message_id}")
        subject_value = subject or f"Message {message_id}"
        sent_at = date or internal_date or datetime.utcfromtimestamp(0)
        internal_ts = internal_date or sent_at

        message_entity = GmailMessageEntity(
            breadcrumbs=[thread_breadcrumb],
            message_key=f"msg_{message_id}",
            message_id=message_id,
            subject=subject_value,
            sent_at=sent_at,
            internal_timestamp=internal_ts,
            url=f"https://mail.google.com/mail/u/0/#inbox/{message_id}",
            size=message_data.get("sizeEstimate", 0),
            file_type="html",
            mime_type="text/html",
            local_path=None,  # Will be set after downloading HTML body
            thread_id=thread_id,
            sender=sender,
            to=to_list,
            cc=cc_list,
            bcc=bcc_list,
            date=date,
            snippet=message_data.get("snippet"),
            label_ids=message_data.get("labelIds", []),
            internal_date=internal_date,
            web_url_value=f"https://mail.google.com/mail/u/0/#inbox/{message_id}",
        )
        self.logger.debug(f"Message entity created with key: {message_entity.message_key}")

        # Download email body to file (NOT stored in entity fields)
        # Email content is only in the local file for conversion
        # NOTE: BaseEntity.name is populated later in the sync pipeline from flagged fields,
        # so we must not rely on message_entity.name here (it is still None).
        # Use the subject (which is required and already set) as the human-readable filename.
        try:
            if body_html:
                filename = safe_filename(subject_value, ".html")
                await self.file_downloader.save_bytes(
                    entity=message_entity,
                    content=body_html.encode("utf-8"),
                    filename_with_extension=filename,
                    logger=self.logger,
                )
            elif body_plain:
                # Save plain-text emails as .txt files for conversion
                filename = safe_filename(subject_value, ".txt")
                await self.file_downloader.save_bytes(
                    entity=message_entity,
                    content=body_plain.encode("utf-8"),
                    filename_with_extension=filename,
                    logger=self.logger,
                )
                # Update file metadata to match plain text
                message_entity.file_type = "text"
                message_entity.mime_type = "text/plain"
        except FileSkippedException as e:
            # Email body skipped (unsupported type, too large) - not an error
            self.logger.debug(f"Skipping message body for {message_id}: {e.reason}")
            return  # Skip this message if we can't save the body

        yield message_entity
        self.logger.debug(f"Message entity yielded for {message_id}")

        # Breadcrumb for attachments
        message_breadcrumb = Breadcrumb(
            entity_id=message_entity.message_key,
            name=message_entity.subject,
            entity_type=GmailMessageEntity.__name__,
        )

        # Process attachments (sequential vs concurrent)
        async for attachment_entity in self._process_attachments(
            client, payload, message_id, thread_id, [thread_breadcrumb, message_breadcrumb]
        ):
            yield attachment_entity

    def _extract_body_content(self, payload: Dict) -> tuple:  # noqa: C901
        """Extract plain text and HTML body content from message payload."""
        self.logger.debug("Extracting body content from message payload")
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

        self.logger.debug(
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
        """Process message attachments concurrently using bounded concurrency driver."""

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

        async def _attachment_worker(descriptor: Dict):
            mime_type = descriptor["mime_type"]
            filename = descriptor["filename"]
            attachment_id = descriptor["attachment_id"]

            attachment_url = (
                f"https://gmail.googleapis.com/gmail/v1/users/me/messages/"
                f"{message_id}/attachments/{attachment_id}"
            )
            try:
                try:
                    attachment_data = await self._get_with_auth(client, attachment_url)
                except httpx.HTTPStatusError as e:
                    if e.response.status_code == 404:
                        self.logger.warning(
                            f"Attachment {attachment_id} not found (404) - skipping"
                        )
                        return
                    raise
                size = attachment_data.get("size", 0)

                # Determine file type from mime_type
                file_type = mime_type.split("/")[0] if "/" in mime_type else "file"

                # Create stable entity_id using message_id + filename
                # Note: attachment_id is ephemeral and changes between API calls
                # Using filename ensures same attachment has same entity_id across syncs
                sanitized_filename = safe_filename(filename)
                stable_entity_id = f"attach_{message_id}_{sanitized_filename}"

                # Create FileEntity wrapper
                attachment_name = filename or f"Attachment {attachment_id}"
                file_entity = GmailAttachmentEntity(
                    breadcrumbs=breadcrumbs,
                    attachment_key=stable_entity_id,
                    filename=attachment_name,
                    url=f"gmail://attachment/{message_id}/{attachment_id}",  # dummy URL
                    size=size,
                    file_type=file_type,
                    mime_type=mime_type,
                    local_path=None,
                    message_id=message_id,
                    attachment_id=attachment_id,
                    thread_id=thread_id,
                    web_url_value=f"https://mail.google.com/mail/u/0/#inbox/{message_id}",
                )

                base64_data = attachment_data.get("data", "")
                if not base64_data:
                    self.logger.warning(f"No data found for attachment {filename}")
                    return

                binary_data = base64.urlsafe_b64decode(base64_data)

                # Save bytes using downloader
                try:
                    await self.file_downloader.save_bytes(
                        entity=file_entity,
                        content=binary_data,
                        filename_with_extension=filename,  # Attachment name from API
                        logger=self.logger,
                    )

                    # Verify save succeeded
                    if not file_entity.local_path:
                        raise ValueError(f"Save failed - no local path set for {file_entity.name}")

                    yield file_entity

                except FileSkippedException as e:
                    # Attachment intentionally skipped (unsupported type, too large, etc.)
                    self.logger.debug(f"Skipping attachment {filename}: {e.reason}")
                    return

                except Exception as e:
                    self.logger.error(f"Failed to save attachment {filename}: {e}")
                    return
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

    # -----------------------
    # Incremental sync
    # -----------------------
    async def _run_incremental_sync(
        self, client: httpx.AsyncClient, start_history_id: str
    ) -> AsyncGenerator[BaseEntity, None]:
        """Run Gmail incremental sync using users.history.list pages."""
        base_url = "https://gmail.googleapis.com/gmail/v1/users/me/history"
        params: Dict[str, Any] = {
            "startHistoryId": start_history_id,
            "maxResults": 500,
        }
        latest_history_id: Optional[str] = None
        processed_message_ids: Set[str] = set()
        lock = asyncio.Lock()

        while True:
            data = await self._get_with_auth(client, base_url, params=params)

            # Deletions: lightweight; process sequentially
            async for deletion in self._yield_history_deletions(data):
                yield deletion

            # Additions: potentially heavy (network per message); support concurrency
            async for addition in self._yield_history_additions(
                client, data, processed_message_ids, lock
            ):
                yield addition

            latest_history_id = data.get("historyId") or latest_history_id

            next_token = data.get("nextPageToken")
            if next_token:
                params["pageToken"] = next_token
            else:
                break

        if latest_history_id and self.cursor:
            self.cursor.update(history_id=str(latest_history_id))
            self.logger.debug("Updated Gmail cursor with latest historyId for next run")

    async def _yield_history_deletions(
        self, data: Dict[str, Any]
    ) -> AsyncGenerator[BaseEntity, None]:
        """Yield deletion entities from a history page."""
        for h in data.get("history", []) or []:
            for deleted in h.get("messagesDeleted", []) or []:
                msg = deleted.get("message") or {}
                msg_id = msg.get("id")
                thread_id = msg.get("threadId")
                if not msg_id:
                    continue
                yield GmailMessageDeletionEntity(
                    breadcrumbs=[],
                    message_key=f"msg_{msg_id}",
                    label=f"Deleted message {msg_id}",
                    message_id=msg_id,
                    thread_id=thread_id,
                    deletion_status="removed",
                )

    async def _yield_history_additions(  # noqa: C901
        self,
        client: httpx.AsyncClient,
        data: Dict[str, Any],
        processed_message_ids: Set[str],
        lock: asyncio.Lock,
    ) -> AsyncGenerator[BaseEntity, None]:
        """Yield entities for added/changed messages from a history page.

        Fetches message details concurrently for optimal performance.
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

        async def _added_worker(item: Dict[str, str]):
            msg_id = item["msg_id"]
            thread_id = item.get("thread_id") or "unknown"
            try:
                if await self._should_skip_message(msg_id, processed_message_ids, lock):
                    return

                detail_url = f"https://gmail.googleapis.com/gmail/v1/users/me/messages/{msg_id}"
                try:
                    message_data = await self._get_with_auth(client, detail_url)
                except httpx.HTTPStatusError as e:
                    if e.response.status_code == 404:
                        self.logger.warning(f"Message {msg_id} not found (404) - skipping")
                        return
                    raise

                # Apply filters for incremental sync
                if not self._message_matches_filters(message_data):
                    self.logger.debug(f"Skipping message {msg_id} - doesn't match filters")
                    return

                thread_key = f"thread_{thread_id}"
                thread_name = (message_data.get("snippet") or "").strip() or f"Thread {thread_id}"
                thread_breadcrumb = Breadcrumb(
                    entity_id=thread_key,
                    name=thread_name[:50] + "..." if len(thread_name) > 50 else thread_name,
                    entity_type=GmailThreadEntity.__name__,
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

    # -----------------------
    # Top-level orchestration
    # -----------------------
    async def generate_entities(self) -> AsyncGenerator[BaseEntity, None]:
        """Generate Gmail entities with incremental History API support."""
        try:
            async with self.http_client() as client:
                last_history_id = await self._resolve_cursor()
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
                            if history_id and self.cursor:
                                self.cursor.update(history_id=str(history_id))
                                self.logger.debug(
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
