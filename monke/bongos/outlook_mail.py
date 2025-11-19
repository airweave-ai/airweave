import asyncio
import time
import uuid
from typing import Any, Dict, List

import httpx
from monke.bongos.base_bongo import BaseBongo
from monke.generation.outlook_mail import generate_outlook_message
from monke.utils.logging import get_logger

GRAPH = "https://graph.microsoft.com/v1.0"


class OutlookMailBongo(BaseBongo):
    connector_type = "outlook_mail"

    def __init__(self, credentials: Dict[str, Any], **kwargs):
        super().__init__(credentials)
        self.access_token: str = credentials["access_token"]
        self.entity_count: int = int(kwargs.get("entity_count", 3))
        self.openai_model: str = kwargs.get("openai_model", "gpt-4.1-mini")
        self.rate_limit_delay = float(kwargs.get("rate_limit_delay_ms", 500)) / 1000.0
        self.logger = get_logger("outlook_mail_bongo")
        self._messages: List[Dict[str, Any]] = []
        self._last_req = 0.0

    async def create_entities(self) -> List[Dict[str, Any]]:
        """Create test emails in Outlook by sending to oneself."""
        self.logger.info(f"🥁 Creating {self.entity_count} test emails in Outlook")
        out: List[Dict[str, Any]] = []

        async with httpx.AsyncClient(base_url=GRAPH, timeout=30) as client:
            # Get user's email address
            user_email = await self._get_user_email(client)
            self.logger.info(f"📧 Sending test emails to: {user_email}")

            # Generate tokens
            tokens = [uuid.uuid4().hex[:8] for _ in range(self.entity_count)]

            # Generate and send emails
            for token in tokens:
                await self._pace()

                # Generate email content
                subject, body = await generate_outlook_message(self.openai_model, token)

                # Create and send email to oneself
                payload = {
                    "message": {
                        "subject": subject,
                        "body": {"contentType": "Text", "content": body},
                        "toRecipients": [{"emailAddress": {"address": user_email}}],
                    },
                    "saveToSentItems": "true",
                }

                r = await client.post(
                    "/me/sendMail", headers=self._hdrs(), json=payload
                )

                if r.status_code not in (200, 202):
                    self.logger.error(f"Send mail failed {r.status_code}: {r.text}")
                    r.raise_for_status()

                # Note: sendMail doesn't return the message ID, so we'll use token as reference
                ent = {
                    "type": "message",
                    "id": token,  # Use token as ID for tracking
                    "subject": subject,
                    "token": token,
                    "expected_content": token,
                    "user_email": user_email,
                }
                out.append(ent)
                self._messages.append(ent)
                self.created_entities.append({"id": token, "name": subject})
                self.logger.info(f"📧 Sent test email with token: {token}")

                # Brief delay between sends
                if self.entity_count > 10:
                    await asyncio.sleep(0.5)

        return out

    async def update_entities(self) -> List[Dict[str, Any]]:
        """Update entities by sending new emails with updated content.

        Note: Sent emails cannot be edited, so we send new ones with [Updated] suffix.
        """
        if not self._messages:
            return []

        self.logger.info(f"🥁 Sending {len(self._messages)} updated emails")
        updated = []

        async with httpx.AsyncClient(base_url=GRAPH, timeout=30) as client:
            user_email = await self._get_user_email(client)

            for ent in self._messages[: min(3, len(self._messages))]:
                await self._pace()

                # Generate updated content with same token
                subject, body = await generate_outlook_message(
                    self.openai_model, ent["token"], is_update=True
                )
                subject = f"{subject} [Updated]"

                # Send updated email
                payload = {
                    "message": {
                        "subject": subject,
                        "body": {"contentType": "Text", "content": body},
                        "toRecipients": [{"emailAddress": {"address": user_email}}],
                    },
                    "saveToSentItems": "true",
                }

                r = await client.post(
                    "/me/sendMail", headers=self._hdrs(), json=payload
                )

                if r.status_code in (200, 202):
                    updated.append({**ent, "updated": True, "updated_subject": subject})
                    self.logger.info(f"📧 Sent updated email for token: {ent['token']}")
                else:
                    self.logger.warning(
                        f"Failed to send updated email: {r.status_code}"
                    )

        return updated

    async def delete_entities(self) -> List[str]:
        return await self.delete_specific_entities(self._messages)

    async def delete_specific_entities(
        self, entities: List[Dict[str, Any]]
    ) -> List[str]:
        """Delete specific entities by searching for them by token."""
        self.logger.info(f"🥁 Deleting {len(entities)} Outlook emails")
        deleted: List[str] = []

        async with httpx.AsyncClient(base_url=GRAPH, timeout=30) as client:
            for ent in entities:
                try:
                    await self._pace()

                    # Get the token to search for
                    token = ent.get("token", "")
                    if not token:
                        self.logger.warning(f"No token for entity, skipping: {ent}")
                        continue

                    # Use $search for full-text search across subject and body
                    # This is more flexible than $filter for finding tokens
                    r = await client.get(
                        "/me/messages",
                        headers=self._hdrs(),
                        params={"$search": f'"{token}"', "$top": 50},
                    )

                    if r.status_code == 200:
                        messages = r.json().get("value", [])
                        self.logger.info(
                            f"🔍 Found {len(messages)} messages matching token '{token}'"
                        )

                        # Filter messages that actually contain the token
                        # (search can be imprecise, so verify by fetching full body)
                        matching_messages = []
                        for msg in messages:
                            subject = msg.get("subject", "")
                            # Check subject first (quick check)
                            if token in subject:
                                matching_messages.append(msg)
                                continue

                            # Check bodyPreview (may be truncated, so not definitive)
                            body_preview = msg.get("bodyPreview", "")
                            if token in body_preview:
                                matching_messages.append(msg)
                                continue

                            # Fetch full body to verify (needed because bodyPreview is truncated)
                            try:
                                await self._pace()
                                full_msg_r = await client.get(
                                    f"/me/messages/{msg['id']}",
                                    headers=self._hdrs(),
                                    params={"$select": "body"},
                                )
                                if full_msg_r.status_code == 200:
                                    full_body = (
                                        full_msg_r.json()
                                        .get("body", {})
                                        .get("content", "")
                                    )
                                    if token in full_body:
                                        matching_messages.append(msg)
                            except Exception as e:
                                self.logger.warning(
                                    f"⚠️ Failed to fetch full body for {msg['id']}: {e}"
                                )

                        self.logger.info(
                            f"🎯 {len(matching_messages)} messages verified to contain token '{token}'"
                        )

                        # Delete all matching messages
                        for msg in matching_messages:
                            try:
                                await self._pace()
                                del_r = await client.delete(
                                    f"/me/messages/{msg['id']}", headers=self._hdrs()
                                )
                                if del_r.status_code == 204:
                                    deleted.append(token)
                                    self.logger.info(
                                        f"✅ Deleted email: {msg.get('subject', 'Unknown')[:50]}"
                                    )
                                else:
                                    self.logger.warning(
                                        f"Delete failed for {msg['id']}: {del_r.status_code}"
                                    )
                            except Exception as e:
                                self.logger.warning(
                                    f"Error deleting message {msg['id']}: {e}"
                                )
                    else:
                        self.logger.warning(
                            f"Search failed for token {token}: {r.status_code} - {r.text[:200]}"
                        )

                except Exception as e:
                    self.logger.warning(
                        f"Delete error for entity {ent.get('token', 'unknown')}: {e}"
                    )

        return deleted

    async def cleanup(self):
        """Comprehensive cleanup of all test emails."""
        self.logger.info("🧹 Starting comprehensive Outlook Mail cleanup")

        cleanup_stats = {"messages_deleted": 0, "errors": 0}

        try:
            # First, delete current session messages
            if self._messages:
                self.logger.info(
                    f"🗑️ Cleaning up {len(self._messages)} current session messages"
                )
                deleted = await self.delete_specific_entities(self._messages)
                cleanup_stats["messages_deleted"] += len(deleted)
                self._messages.clear()

            # Search for any remaining monke test emails
            await self._cleanup_orphaned_test_messages(cleanup_stats)

            self.logger.info(
                f"🧹 Cleanup completed: {cleanup_stats['messages_deleted']} messages deleted, "
                f"{cleanup_stats['errors']} errors"
            )
        except Exception as e:
            self.logger.error(f"❌ Error during comprehensive cleanup: {e}")

    async def _cleanup_orphaned_test_messages(self, stats: Dict[str, Any]):
        """Find and delete orphaned test messages from previous runs."""
        try:
            async with httpx.AsyncClient(base_url=GRAPH, timeout=30) as client:
                # Use $search for full-text search to find test messages
                # Search for common patterns in our generated content
                search_terms = ["product", "reference:", "synthetic"]

                for term in search_terms:
                    try:
                        await self._pace()
                        r = await client.get(
                            "/me/messages",
                            headers=self._hdrs(),
                            params={"$search": f'"{term}"', "$top": 100},
                        )
                        if r.status_code == 200:
                            messages = r.json().get("value", [])

                            # Filter for messages that look like test emails
                            test_patterns = [
                                "product",
                                "tech",
                                "reference:",
                                "synthetic",
                            ]
                            test_messages = [
                                m
                                for m in messages
                                if any(
                                    pattern in m.get("subject", "").lower()
                                    or (
                                        m.get("bodyPreview")
                                        and pattern in m.get("bodyPreview", "").lower()
                                    )
                                    for pattern in test_patterns
                                )
                            ]

                            if test_messages:
                                self.logger.info(
                                    f"🔍 Found {len(test_messages)} potential test messages "
                                    f"(search term: {term})"
                                )
                                for msg in test_messages:
                                    try:
                                        await self._pace()
                                        del_r = await client.delete(
                                            f"/me/messages/{msg['id']}",
                                            headers=self._hdrs(),
                                        )
                                        if del_r.status_code == 204:
                                            stats["messages_deleted"] += 1
                                            self.logger.info(
                                                f"✅ Deleted orphaned message: "
                                                f"{msg.get('subject', 'Unknown')[:50]}"
                                            )
                                        else:
                                            stats["errors"] += 1
                                    except Exception as e:
                                        stats["errors"] += 1
                                        self.logger.warning(
                                            f"⚠️ Failed to delete message {msg['id']}: {e}"
                                        )
                    except Exception as e:
                        self.logger.warning(f"⚠️ Search failed for term '{term}': {e}")
        except Exception as e:
            self.logger.warning(f"⚠️ Could not search for orphaned messages: {e}")

    async def _get_user_email(self, client: httpx.AsyncClient) -> str:
        """Get the authenticated user's email address."""
        r = await client.get("/me", headers=self._hdrs())
        r.raise_for_status()
        data = r.json()
        return data.get("mail") or data.get("userPrincipalName")

    def _hdrs(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }

    async def _pace(self):
        now = time.time()
        if (delta := now - self._last_req) < self.rate_limit_delay:
            await asyncio.sleep(self.rate_limit_delay - delta)
        self._last_req = time.time()
