"""Gmail source implementation for syncing email threads, messages, and attachments.

Uses concurrent/batching processing for optimal performance:
  * Thread detail fetch + per-thread processing
  * Per-thread message processing
  * Per-message attachment fetch & processing
  * Incremental history message-detail fetch
"""

from __future__ import annotations

import asyncio
import base64
from datetime import datetime
from typing import Any, AsyncGenerator, Dict, List, Optional, Set

import httpx
from tenacity import retry, stop_after_attempt

from airweave.core.logging import ContextualLogger
from airweave.core.shared_models import RateLimitLevel
from airweave.domains.browse_tree.types import NodeSelectionData
from airweave.domains.sources.exceptions import SourceAuthError
from airweave.domains.sources.token_providers.protocol import TokenProviderProtocol
from airweave.domains.storage import FileSkippedException
from airweave.domains.storage.file_service import FileService
from airweave.domains.syncs.cursors.cursor import SyncCursor
from airweave.platform.configs.config import GmailConfig
from airweave.platform.cursors import GmailCursor
from airweave.platform.decorators import source
from airweave.platform.entities._base import BaseEntity, Breadcrumb
from airweave.platform.entities.gmail import (
    GmailAttachmentEntity,
    GmailMessageDeletionEntity,
    GmailMessageEntity,
    GmailThreadEntity,
)
from airweave.platform.http_client.airweave_client import AirweaveHttpClient
from airweave.platform.sources._base import BaseSource
from airweave.platform.sources.http_helpers import raise_for_status
from airweave.platform.sources.retry_helpers import (
    wait_rate_limit_with_backoff,
)
from airweave.platform.utils.filename_utils import safe_filename
from airweave.schemas.source_connection import AuthenticationMethod, OAuthType


def _should_retry_gmail_request(exception: Exception) -> bool:
    """Custom retry condition that excludes 404 errors but includes 429 and timeouts."""
    if isinstance(exception, httpx.HTTPStatusError):
        if exception.response.status_code == 404:
            return False
        if exception.response.status_code == 429:
            return True
        return True
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
        cls,
        *,
        auth: TokenProviderProtocol,
        logger: ContextualLogger,
        http_client: AirweaveHttpClient,
        config: GmailConfig,
    ) -> GmailSource:
        """Create a new Gmail source instance."""
        instance = cls(auth=auth, logger=logger, http_client=http_client)

        config_dict = config.model_dump() if config else {}
        instance.batch_size = int(config_dict.get("batch_size", 30))
        instance.max_queue_size = int(config_dict.get("max_queue_size", 200))
        instance.preserve_order = bool(config_dict.get("preserve_order", False))
        instance.stop_on_error = bool(config_dict.get("stop_on_error", False))

        instance.after_date = config_dict.get("after_date")
        instance.included_labels = config_dict.get("included_labels", ["inbox", "sent"])
        instance.excluded_labels = config_dict.get("excluded_labels", ["spam", "trash"])
        instance.excluded_categories = config_dict.get(
            "excluded_categories", ["promotions", "social"]
        )
        instance.gmail_query = config_dict.get("gmail_query")

        return instance

    def _build_gmail_query(self) -> Optional[str]:
        """Build Gmail API query string from filter configuration."""
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

        if getattr(self, "after_date", None):
            parts.append(f"after:{self.after_date}")

        included_labels = getattr(self, "included_labels", [])
        if included_labels:
            if len(included_labels) == 1:
                parts.append(f"in:{included_labels[0]}")
            else:
                label_parts = " OR ".join(f"in:{label}" for label in included_labels)
                parts.append(f"{{{label_parts}}}")

        for label in getattr(self, "excluded_labels", []):
            parts.append(f"-in:{label}")

        for category in getattr(self, "excluded_categories", []):
            parts.append(f"-category:{category}")

        return parts

    def _message_matches_filters(self, message_data: Dict) -> bool:
        """Check if a message matches the configured filters.

        Used for incremental syncs where we can't filter via query parameter.
        """
        if getattr(self, "gmail_query", None):
            return True

        if not self._message_matches_date_filters(message_data):
            return False

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

        included_labels = getattr(self, "included_labels", None)
        if included_labels:
            has_included = any(label.lower() in label_ids_lower for label in included_labels)
            if not has_included:
                self.logger.debug(
                    f"Message {message_data.get('id')} skipped: doesn't match included labels"
                )
                return False

        excluded_labels = getattr(self, "excluded_labels", None)
        if excluded_labels:
            has_excluded = any(label.lower() in label_ids_lower for label in excluded_labels)
            if has_excluded:
                self.logger.debug(
                    f"Message {message_data.get('id')} skipped: matches excluded labels"
                )
                return False

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

    async def _authed_headers(self) -> Dict[str, str]:
        """Build Authorization headers with a fresh token."""
        token = await self.auth.get_token()
        return {"Authorization": f"Bearer {token}"}

    async def _refresh_and_get_headers(self) -> Dict[str, str]:
        """Force-refresh the token and return updated headers."""
        new_token = await self.auth.force_refresh()
        return {"Authorization": f"Bearer {new_token}"}

    @retry(
        stop=stop_after_attempt(5),
        retry=_should_retry_gmail_request,
        wait=wait_rate_limit_with_backoff,
        reraise=True,
    )
    async def _get(self, url: str, params: Optional[dict] = None) -> dict:
        """Make an authenticated GET request to the Gmail API with proper 429 handling."""
        self.logger.debug(f"Making authenticated GET request to: {url} with params: {params}")

        headers = await self._authed_headers()
        response = await self.http_client.get(url, headers=headers, params=params)

        if response.status_code == 401 and self.auth.supports_refresh:
            self.logger.warning(
                f"Got 401 Unauthorized from Gmail API at {url}, refreshing token..."
            )
            headers = await self._refresh_and_get_headers()
            response = await self.http_client.get(url, headers=headers, params=params)

        if response.status_code == 429:
            retry_after = response.headers.get("Retry-After", "unknown")
            self.logger.warning(f"Got 429 Rate Limited from Gmail API. Retry-After: {retry_after}")

        raise_for_status(
            response,
            source_short_name=self.short_name,
            token_provider_kind=self.auth.provider_kind,
        )
        data = response.json()
        self.logger.debug(f"Received response from {url} - Status: {response.status_code}")
        self.logger.debug(f"Response data keys: {list(data.keys())}")
        return data

    # -----------------------
    # Cursor helper
    # -----------------------
    async def _resolve_cursor(self, cursor: SyncCursor | None) -> Optional[str]:
        """Get last history ID from cursor if available."""
        cursor_data = cursor.data if cursor else {}
        return cursor_data.get("history_id")

    # -----------------------
    # Listing helpers
    # -----------------------
    async def _list_threads(self) -> AsyncGenerator[Dict, None]:
        """Yield thread summary objects across all pages."""
        base_url = "https://gmail.googleapis.com/gmail/v1/users/me/threads"
        params: Dict[str, Any] = {"maxResults": 100}

        query = self._build_gmail_query()
        if query:
            params["q"] = query
            self.logger.debug(f"Filtering threads with query: {query}")

        page_count = 0

        while True:
            page_count += 1
            self.logger.debug(f"Fetching thread list page #{page_count} with params: {params}")
            data = await self._get(base_url, params=params)
            threads = data.get("threads", []) or []
            self.logger.debug(f"Found {len(threads)} threads on page {page_count}")

            for thread_info in threads:
                yield thread_info

            next_page_token = data.get("nextPageToken")
            if not next_page_token:
                self.logger.debug(f"No more thread pages after page {page_count}")
                break
            params["pageToken"] = next_page_token

    async def _fetch_thread_detail(self, thread_id: str) -> Dict:
        """Fetch full thread details including messages."""
        base_url = "https://gmail.googleapis.com/gmail/v1/users/me/threads"
        detail_url = f"{base_url}/{thread_id}"
        self.logger.debug(f"Fetching full thread details from: {detail_url}")
        try:
            thread_data = await self._get(detail_url)
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
        self,
        processed_message_ids: Set[str],
        cursor: SyncCursor | None = None,
        files: FileService | None = None,
    ) -> AsyncGenerator[BaseEntity, None]:
        """Generate GmailThreadEntity objects and associated message entities."""
        lock = asyncio.Lock()

        async def _thread_worker(thread_info: Dict):
            thread_id = thread_info.get("id")
            if not thread_id:
                return
            try:
                thread_data = await self._fetch_thread_detail(thread_id)
                if not thread_data:
                    return
                async for ent in self._emit_thread_and_messages(
                    thread_id, thread_data, processed_message_ids, lock=lock, files=files
                ):
                    yield ent
            except SourceAuthError:
                raise
            except Exception as e:
                self.logger.warning(f"Error processing thread {thread_id}: {e}", exc_info=True)

        async for ent in self.process_entities_concurrent(
            items=self._list_threads(),
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
        return GmailThreadEntity.from_api(thread_data, thread_id=thread_id)

    async def _process_thread_messages(
        self,
        message_list: List[Dict],
        thread_id: str,
        thread_breadcrumb: Breadcrumb,
        processed_message_ids: Set[str],
        lock: Optional[asyncio.Lock],
        files: FileService | None = None,
    ) -> AsyncGenerator[BaseEntity, None]:
        """Process messages in a thread concurrently."""

        async def _message_worker(message_data: Dict):
            msg_id = message_data.get("id", "unknown")
            if await self._should_skip_message(msg_id, processed_message_ids, lock=lock):
                return
            async for ent in self._process_message(
                message_data, thread_id, thread_breadcrumb, files=files
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
        thread_id: str,
        thread_data: Dict,
        processed_message_ids: Set[str],
        lock: Optional[asyncio.Lock] = None,
        files: FileService | None = None,
    ) -> AsyncGenerator[BaseEntity, None]:
        """Emit a thread entity and then all entities from its messages."""
        thread_entity = await self._create_thread_entity(thread_id, thread_data)
        self.logger.debug(f"Yielding thread entity: {thread_id}")
        yield thread_entity

        thread_breadcrumb = Breadcrumb(
            entity_id=thread_entity.thread_key,
            name=thread_entity.title,
            entity_type=GmailThreadEntity.__name__,
        )

        message_list = thread_data.get("messages", []) or []
        async for entity in self._process_thread_messages(
            message_list, thread_id, thread_breadcrumb, processed_message_ids, lock, files=files
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
        message_data: Dict,
        thread_id: str,
        thread_breadcrumb: Breadcrumb,
        files: FileService | None = None,
    ) -> AsyncGenerator[BaseEntity, None]:
        """Process a message and its attachments."""
        message_id = message_data.get("id")
        self.logger.debug(f"Processing message ID: {message_id} in thread: {thread_id}")

        if "payload" not in message_data:
            self.logger.debug(
                f"Payload not in message data, fetching full message details for {message_id}"
            )
            message_url = f"https://gmail.googleapis.com/gmail/v1/users/me/messages/{message_id}"
            try:
                message_data = await self._get(message_url)
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

        self.logger.debug(f"Creating message entity for message {message_id}")
        message_entity = GmailMessageEntity.from_api(
            message_data, thread_id=thread_id, breadcrumbs=[thread_breadcrumb]
        )
        self.logger.debug(f"Message entity created with key: {message_entity.message_key}")

        payload = message_data.get("payload", {}) or {}
        self.logger.debug(f"Extracting body content for message {message_id}")
        body_plain, body_html = self._extract_body_content(payload)

        try:
            if files:
                subject = message_entity.subject or message_entity.name or "message"
                if body_html:
                    filename = safe_filename(subject, ".html")
                    await files.save_bytes(
                        entity=message_entity,
                        content=body_html.encode("utf-8"),
                        filename_with_extension=filename,
                        logger=self.logger,
                    )
                elif body_plain:
                    filename = safe_filename(subject, ".txt")
                    await files.save_bytes(
                        entity=message_entity,
                        content=body_plain.encode("utf-8"),
                        filename_with_extension=filename,
                        logger=self.logger,
                    )
                    message_entity.file_type = "text"
                    message_entity.mime_type = "text/plain"
        except FileSkippedException as e:
            self.logger.debug(f"Skipping message body for {message_id}: {e.reason}")
            return

        yield message_entity
        self.logger.debug(f"Message entity yielded for {message_id}")

        message_breadcrumb = Breadcrumb(
            entity_id=message_entity.message_key,
            name=message_entity.subject,
            entity_type=GmailMessageEntity.__name__,
        )

        async for attachment_entity in self._process_attachments(
            payload, message_id, thread_id, [thread_breadcrumb, message_breadcrumb], files=files
        ):
            yield attachment_entity

    def _extract_body_content(self, payload: Dict) -> tuple:  # noqa: C901
        """Extract plain text and HTML body content from message payload."""
        self.logger.debug("Extracting body content from message payload")
        body_plain = None
        body_html = None

        def extract_from_parts(parts, depth=0):
            p_txt, p_html = None, None

            for part in parts:
                mime_type = part.get("mimeType", "")
                body = part.get("body", {}) or {}

                if body.get("data"):
                    data = body.get("data")
                    try:
                        decoded = base64.urlsafe_b64decode(data).decode("utf-8", errors="ignore")
                        if mime_type == "text/plain" and not p_txt:
                            p_txt = decoded
                        elif mime_type == "text/html" and not p_html:
                            p_html = decoded
                    except Exception as e:
                        self.logger.warning(f"Error decoding body content: {str(e)}")

                elif part.get("parts"):
                    sub_txt, sub_html = extract_from_parts(part.get("parts", []), depth + 1)
                    if not p_txt:
                        p_txt = sub_txt
                    if not p_html:
                        p_html = sub_html

            return p_txt, p_html

        if payload.get("parts"):
            parts = payload.get("parts", [])
            body_plain, body_html = extract_from_parts(parts)
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
                    self.logger.warning(f"Error decoding single part body: {str(e)}")

        self.logger.debug(
            f"Body extraction complete: found_text={bool(body_plain)}, found_html={bool(body_html)}"
        )
        return body_plain, body_html

    # -----------------------
    # Attachments
    # -----------------------
    async def _process_attachments(  # noqa: C901
        self,
        payload: Dict,
        message_id: str,
        thread_id: str,
        breadcrumbs: List[Breadcrumb],
        files: FileService | None = None,
    ) -> AsyncGenerator[GmailAttachmentEntity, None]:
        """Process message attachments concurrently using bounded concurrency driver."""

        def collect_attachment_descriptors(part, out: List[Dict], depth=0):
            mime_type = part.get("mimeType", "")
            filename = part.get("filename", "")
            body = part.get("body", {}) or {}

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

            for sub in part.get("parts", []) or []:
                collect_attachment_descriptors(sub, out, depth + 1)

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
                    attachment_data = await self._get(attachment_url)
                except httpx.HTTPStatusError as e:
                    if e.response.status_code == 404:
                        self.logger.warning(
                            f"Attachment {attachment_id} not found (404) - skipping"
                        )
                        return
                    raise
                size = attachment_data.get("size", 0)

                file_type = mime_type.split("/")[0] if "/" in mime_type else "file"

                sanitized_filename = safe_filename(filename)
                stable_entity_id = f"attach_{message_id}_{sanitized_filename}"

                attachment_name = filename or f"Attachment {attachment_id}"
                file_entity = GmailAttachmentEntity(
                    breadcrumbs=breadcrumbs,
                    attachment_key=stable_entity_id,
                    filename=attachment_name,
                    url=f"gmail://attachment/{message_id}/{attachment_id}",
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

                try:
                    if files:
                        await files.save_bytes(
                            entity=file_entity,
                            content=binary_data,
                            filename_with_extension=filename,
                            logger=self.logger,
                        )

                    if file_entity.local_path or not files:
                        yield file_entity
                    elif files:
                        raise ValueError(f"Save failed - no local path set for {file_entity.name}")

                except FileSkippedException as e:
                    self.logger.debug(f"Skipping attachment {filename}: {e.reason}")
                    return

                except SourceAuthError:
                    raise

                except Exception as e:
                    self.logger.warning(f"Failed to save attachment {filename}: {e}")
                    return

            except SourceAuthError:
                raise
            except Exception as e:
                self.logger.warning(
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
        self,
        start_history_id: str,
        cursor: SyncCursor | None = None,
        files: FileService | None = None,
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
            data = await self._get(base_url, params=params)

            async for deletion in self._yield_history_deletions(data):
                yield deletion

            async for addition in self._yield_history_additions(
                data, processed_message_ids, lock, files=files
            ):
                yield addition

            latest_history_id = data.get("historyId") or latest_history_id

            next_token = data.get("nextPageToken")
            if next_token:
                params["pageToken"] = next_token
            else:
                break

        if latest_history_id and cursor:
            cursor.update(history_id=str(latest_history_id))
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
        data: Dict[str, Any],
        processed_message_ids: Set[str],
        lock: asyncio.Lock,
        files: FileService | None = None,
    ) -> AsyncGenerator[BaseEntity, None]:
        """Yield entities for added/changed messages from a history page."""
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
                    message_data = await self._get(detail_url)
                except httpx.HTTPStatusError as e:
                    if e.response.status_code == 404:
                        self.logger.warning(f"Message {msg_id} not found (404) - skipping")
                        return
                    raise

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
                    message_data, thread_id, thread_breadcrumb, files=files
                ):
                    yield ent
            except SourceAuthError:
                raise
            except Exception as e:
                self.logger.warning(f"Failed to fetch/process message {msg_id}: {e}")

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
    async def generate_entities(
        self,
        *,
        cursor: SyncCursor | None = None,
        files: FileService | None = None,
        node_selections: list[NodeSelectionData] | None = None,
    ) -> AsyncGenerator[BaseEntity, None]:
        """Generate Gmail entities with incremental History API support."""
        try:
            last_history_id = await self._resolve_cursor(cursor)
            if last_history_id:
                async for e in self._run_incremental_sync(
                    last_history_id, cursor=cursor, files=files
                ):
                    yield e
            else:
                processed_message_ids: Set[str] = set()
                async for e in self._generate_thread_entities(
                    processed_message_ids, cursor=cursor, files=files
                ):
                    yield e

                try:
                    url = "https://gmail.googleapis.com/gmail/v1/users/me/messages"
                    latest_list = await self._get(url, params={"maxResults": 1})
                    msgs = latest_list.get("messages", [])
                    if msgs:
                        detail = await self._get(
                            f"https://gmail.googleapis.com/gmail/v1/users/me/messages/{msgs[0]['id']}",
                        )
                        history_id = detail.get("historyId")
                        if history_id and cursor:
                            cursor.update(history_id=str(history_id))
                            self.logger.debug(
                                "Stored Gmail historyId after full sync for next incremental run"
                            )
                except SourceAuthError:
                    raise
                except Exception as e:
                    self.logger.warning(f"Failed to capture starting Gmail historyId: {e}")

        except SourceAuthError:
            raise
        except Exception as e:
            self.logger.warning(f"Error in entity generation: {str(e)}", exc_info=True)
            raise

    async def validate(self) -> None:
        """Validate credentials by pinging the Gmail user profile."""
        await self._get("https://gmail.googleapis.com/gmail/v1/users/me/profile")
