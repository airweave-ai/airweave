"""Gmail source implementation.

Retrieves data from a user's Gmail account in read-only mode:
  - Labels
  - Threads (and associated Messages)
  - Drafts

Follows the same structure and pattern as other connector implementations
(e.g., Asana, Todoist, HubSpot). The entity schemas are defined in entities/gmail.py.

Reference:
  https://developers.google.com/gmail/api/reference/rest
"""

from typing import AsyncGenerator, List, Optional

import httpx

from airweave.platform.auth.schemas import AuthType
from airweave.platform.decorators import source
from airweave.platform.entities._base import Breadcrumb, ChunkEntity
from airweave.platform.entities.gmail import (
    GmailDraftEntity,
    GmailLabelEntity,
    GmailMessageEntity,
    GmailThreadEntity,
)
from airweave.platform.sources._base import BaseSource


@source(
    "Gmail",
    "gmail",
    AuthType.oauth2_with_refresh,
    auth_config_class="GoogleAuthConfig",
    labels=["Communication", "Email"],
)
class GmailSource(BaseSource):
    """Gmail source implementation (read-only).

    Retrieves and yields Gmail objects (labels, threads, messages, drafts)
    as entity schemas defined in entities/gmail.py.
    """

    @classmethod
    async def create(cls, access_token: str) -> "GmailSource":
        """Create a new Gmail source instance with the provided OAuth access token."""
        instance = cls()
        instance.access_token = access_token
        return instance

    async def _get_with_auth(
        self, client: httpx.AsyncClient, url: str, params: Optional[dict] = None
    ) -> dict:
        """Make an authenticated GET request to the Gmail API."""
        headers = {"Authorization": f"Bearer {self.access_token}"}
        response = await client.get(url, headers=headers, params=params)
        response.raise_for_status()
        return response.json()

    async def _generate_label_entities(
        self, client: httpx.AsyncClient
    ) -> AsyncGenerator[GmailLabelEntity, None]:
        """Generate GmailLabelEntity objects."""
        url = "https://gmail.googleapis.com/gmail/v1/users/me/labels"
        data = await self._get_with_auth(client, url)
        for label in data.get("labels", []):
            yield GmailLabelEntity(
                entity_id=label["id"],
                breadcrumbs=[],
                name=label["name"],
                label_type=label.get("type", "user"),
                message_list_visibility=label.get("messageListVisibility"),
                label_list_visibility=label.get("labelListVisibility"),
                total_messages=label.get("messagesTotal", 0),
                unread_messages=label.get("messagesUnread", 0),
            )

    async def _generate_thread_entities(
        self, client: httpx.AsyncClient
    ) -> AsyncGenerator[ChunkEntity, None]:
        """Generate GmailThreadEntity objects.

        For each thread, generate GmailMessageEntity objects.
        """
        base_url = "https://gmail.googleapis.com/gmail/v1/users/me/threads"
        params = {"maxResults": 100}
        while True:
            data = await self._get_with_auth(client, base_url, params=params)
            threads = data.get("threads", [])

            for thread_info in threads:
                thread_id = thread_info["id"]
                # Fetch full thread detail
                detail_url = f"{base_url}/{thread_id}"
                thread_data = await self._get_with_auth(client, detail_url)

                # Collect top-level fields for the Thread entity
                snippet = thread_data.get("snippet")
                history_id = thread_data.get("historyId")
                message_list = thread_data.get("messages", [])
                label_ids = thread_data.get("labels", [])  # returned in newer API versions
                if not label_ids:
                    # Alternatively, older responses might store "messages[0].labelIds"
                    # We'll unify them below if needed.
                    first_msg_labels = message_list[0].get("labelIds", []) if message_list else []
                    label_ids = first_msg_labels

                # Compute message_count and last message date
                message_count = len(message_list)
                last_message_date = None
                if message_list:
                    # Sort messages by internalDate
                    sorted_msgs = sorted(
                        message_list,
                        key=lambda m: int(m.get("internalDate", 0)),
                        reverse=True,
                    )
                    last_message_date = sorted_msgs[0].get("internalDate")

                # Convert last_message_date to a Python datetime if present
                # internalDate is in milliseconds since epoch
                if last_message_date:
                    from datetime import datetime

                    last_message_date = datetime.utcfromtimestamp(int(last_message_date) / 1000)

                # Create thread entity and its breadcrumb
                thread_entity = GmailThreadEntity(
                    entity_id=thread_id,
                    breadcrumbs=[],  # Thread is top-level, so empty breadcrumbs
                    snippet=snippet,
                    history_id=history_id,
                    message_count=message_count,
                    label_ids=label_ids,
                    last_message_date=last_message_date,
                )
                yield thread_entity

                # Create thread breadcrumb for messages
                thread_breadcrumb = Breadcrumb(
                    entity_id=thread_id,
                    name=snippet[:50] + "..." if len(snippet or "") > 50 else (snippet or ""),
                    type="thread",
                )

                # For each message in the thread, yield a GmailMessageEntity with thread breadcrumb
                async for message_entity in self._generate_message_entities(
                    client,
                    message_list=message_list,
                    thread_id=thread_id,
                    thread_breadcrumb=thread_breadcrumb,  # Pass thread breadcrumb
                ):
                    yield message_entity

            # Handle pagination
            next_page_token = data.get("nextPageToken")
            if not next_page_token:
                break
            params["pageToken"] = next_page_token

    async def _generate_message_entities(  # noqa: C901
        self,
        client: httpx.AsyncClient,
        message_list: List[dict],
        thread_id: str,
        thread_breadcrumb: Breadcrumb,
    ) -> AsyncGenerator[GmailMessageEntity, None]:
        """Generate GmailMessageEntity objects for a list of message references."""
        from datetime import datetime

        for msg in message_list:
            msg_id = msg["id"]
            internal_date_ms = msg.get("internalDate")  # string representing ms-since-epoch
            internal_date_dt = None
            if internal_date_ms:
                internal_date_dt = datetime.utcfromtimestamp(int(internal_date_ms) / 1000)

            payload = msg.get("payload", {})
            headers = payload.get("headers", [])

            # Gather standard fields
            subject = None
            sender = None
            to_list = []
            cc_list = []
            bcc_list = []
            date = None

            # Parse headers
            for header in headers:
                name = header.get("name", "").lower()
                value = header.get("value", "")
                if name == "subject":
                    subject = value
                elif name == "from":
                    sender = value
                elif name == "to":
                    to_list = [addr.strip() for addr in value.split(",")]
                elif name == "cc":
                    cc_list = [addr.strip() for addr in value.split(",")]
                elif name == "bcc":
                    bcc_list = [addr.strip() for addr in value.split(",")]
                elif name == "date":
                    try:
                        # Attempt to parse the date header (RFC 2822 format)
                        from email.utils import parsedate_to_datetime

                        date = parsedate_to_datetime(value)
                    except (TypeError, ValueError):
                        pass

            # snippet is also top-level in the message
            snippet = msg.get("snippet", "")
            label_ids = msg.get("labelIds", [])

            # Possibly parse parts for body content
            # For brevity, we'll store them if easily accessible
            body_plain = None
            body_html = None

            def _extract_body(parts):
                """Recursively extract plain and HTML parts from the payload."""
                p_txt, p_html = None, None
                for part in parts:
                    mime_type = part.get("mimeType", "")
                    data = part.get("body", {}).get("data")
                    if not data:
                        if part.get("parts"):
                            child_txt, child_html = _extract_body(part["parts"])
                            p_txt = child_txt or p_txt
                            p_html = child_html or p_html
                    else:
                        import base64

                        decoded = base64.urlsafe_b64decode(data).decode("utf-8", errors="ignore")
                        if "text/plain" in mime_type and not p_txt:
                            p_txt = decoded
                        elif "text/html" in mime_type and not p_html:
                            p_html = decoded
                return p_txt, p_html

            if payload.get("parts"):
                body_plain, body_html = _extract_body(payload["parts"])
            else:
                # Simple case: maybe the 'body' is direct
                body_data = payload.get("body", {}).get("data")
                if body_data:
                    import base64

                    decoded_body = base64.urlsafe_b64decode(body_data).decode(
                        "utf-8", errors="ignore"
                    )
                    if payload.get("mimeType") == "text/plain":
                        body_plain = decoded_body
                    elif payload.get("mimeType") == "text/html":
                        body_html = decoded_body

            yield GmailMessageEntity(
                entity_id=msg_id,
                breadcrumbs=[thread_breadcrumb],  # Include thread in breadcrumb path
                thread_id=thread_id,
                subject=subject,
                sender=sender,
                to=to_list,
                cc=cc_list,
                bcc=bcc_list,
                date=date,
                snippet=snippet,
                body_plain=body_plain,
                body_html=body_html,
                label_ids=label_ids,
                internal_date=internal_date_dt,
                size_estimate=msg.get("sizeEstimate"),
            )

    async def _generate_draft_entities(  # noqa: C901
        self, client: httpx.AsyncClient
    ) -> AsyncGenerator[GmailDraftEntity, None]:
        """Generate GmailDraftEntity objects."""
        base_url = "https://gmail.googleapis.com/gmail/v1/users/me/drafts"
        params = {"maxResults": 100}

        while True:
            data = await self._get_with_auth(client, base_url, params=params)
            drafts = data.get("drafts", [])

            for draft_info in drafts:
                draft_id = draft_info["id"]
                # fetch full details
                draft_detail_url = f"{base_url}/{draft_id}"
                draft_data = await self._get_with_auth(client, draft_detail_url)
                message_data = draft_data.get("message", {})

                # Basic fields we can parse from the message
                thread_id = message_data.get("threadId")
                msg_id = message_data.get("id")

                # We'll parse headers similarly to messages
                payload = message_data.get("payload", {})
                headers = payload.get("headers", [])
                subject = None
                to_list = []
                cc_list = []
                bcc_list = []
                for header in headers:
                    name = header.get("name", "").lower()
                    value = header.get("value", "")
                    if name == "subject":
                        subject = value
                    elif name == "to":
                        to_list = [addr.strip() for addr in value.split(",")]
                    elif name == "cc":
                        cc_list = [addr.strip() for addr in value.split(",")]
                    elif name == "bcc":
                        bcc_list = [addr.strip() for addr in value.split(",")]

                # For a draft, we usually don't have a date, but we might have internal timestamps
                # that differ from fully sent messages
                # We'll store them if present:
                created_date = None
                updated_date = None

                # The Gmail API doesn't always expose created vs updated timestamps for drafts
                # We'll see if "internalDate" is present
                if message_data.get("internalDate"):
                    from datetime import datetime

                    created_date = datetime.utcfromtimestamp(
                        int(message_data["internalDate"]) / 1000
                    )
                    # For now treat updated_date as same. If your logic fetches older/newer revs,
                    # store them accordingly.

                # Attempt to parse the body as with messages
                body_plain = None
                body_html = None

                def _extract_body(parts):
                    """Recursively extract plain and HTML parts from the draft's payload."""
                    p_txt, p_html = None, None
                    for part in parts:
                        mime_type = part.get("mimeType", "")
                        data = part.get("body", {}).get("data")
                        if not data:
                            if part.get("parts"):
                                child_txt, child_html = _extract_body(part["parts"])
                                p_txt = child_txt or p_txt
                                p_html = child_html or p_html
                        else:
                            import base64

                            decoded = base64.urlsafe_b64decode(data).decode(
                                "utf-8", errors="ignore"
                            )
                            if "text/plain" in mime_type and not p_txt:
                                p_txt = decoded
                            elif "text/html" in mime_type and not p_html:
                                p_html = decoded
                    return p_txt, p_html

                if payload.get("parts"):
                    body_plain, body_html = _extract_body(payload["parts"])
                else:
                    # Simple single-part draft body
                    body_data = payload.get("body", {}).get("data")
                    if body_data:
                        import base64

                        decoded_body = base64.urlsafe_b64decode(body_data).decode(
                            "utf-8", errors="ignore"
                        )
                        if payload.get("mimeType") == "text/plain":
                            body_plain = decoded_body
                        elif payload.get("mimeType") == "text/html":
                            body_html = decoded_body

                # If draft is part of a thread, include thread breadcrumb
                breadcrumbs = []
                if thread_id:
                    # Fetch thread details to get snippet for breadcrumb
                    thread_url = (
                        f"https://gmail.googleapis.com/gmail/v1/users/me/threads/{thread_id}"
                    )
                    thread_data = await self._get_with_auth(client, thread_url)
                    thread_snippet = thread_data.get("snippet", "")

                    thread_breadcrumb = Breadcrumb(
                        entity_id=thread_id,
                        name=(
                            thread_snippet[:50] + "..."
                            if len(thread_snippet) > 50
                            else thread_snippet
                        ),
                        type="thread",
                    )
                    breadcrumbs = [thread_breadcrumb]

                yield GmailDraftEntity(
                    entity_id=draft_id,
                    breadcrumbs=breadcrumbs,  # Include thread breadcrumb if draft is part of thread
                    message_id=msg_id,
                    thread_id=thread_id,
                    subject=subject,
                    to=to_list,
                    cc=cc_list,
                    bcc=bcc_list,
                    body_plain=body_plain,
                    body_html=body_html,
                    created_date=created_date,
                    updated_date=updated_date,
                )

            # Handle pagination
            next_page_token = data.get("nextPageToken")
            if not next_page_token:
                break
            params["pageToken"] = next_page_token

    async def generate_entities(self) -> AsyncGenerator[ChunkEntity, None]:
        """Generate all Gmail entities: Labels, Threads (Messages), Drafts."""
        async with httpx.AsyncClient() as client:
            # 1) Generate label entities
            async for label_entity in self._generate_label_entities(client):
                yield label_entity

            # 2) Generate thread entities (each yields one thread entity + message entities)
            async for thread_or_msg_entity in self._generate_thread_entities(client):
                yield thread_or_msg_entity

            # 3) Generate draft entities
            async for draft_entity in self._generate_draft_entities(client):
                yield draft_entity
