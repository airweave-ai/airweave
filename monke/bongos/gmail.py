"""Gmail-specific bongo implementation."""

import asyncio
import base64
import time
import uuid
from typing import Any, Dict, List

import httpx
from monke.bongos.base_bongo import BaseBongo
from monke.utils.logging import get_logger


class GmailBongo(BaseBongo):
    """Gmail-specific bongo implementation.

    Creates, updates, and deletes test emails via the real Gmail API.
    """

    connector_type = "gmail"

    def __init__(self, credentials: Dict[str, Any], **kwargs):
        """Initialize the Gmail bongo.

        Args:
            credentials: Gmail credentials with access_token
            **kwargs: Additional configuration (e.g., entity_count)
        """
        super().__init__(credentials)
        self.access_token = credentials["access_token"]

        # Configuration from kwargs
        self.entity_count = kwargs.get("entity_count", 10)
        self.openai_model = kwargs.get(
            "openai_model", "gpt-4.1"
        )  # sensible default for JSON mode
        self.llm_max_concurrency = int(kwargs.get("llm_max_concurrency", 8))

        # Test data tracking
        self.test_emails = []

        # Rate limiting (Gmail: 250 quota units per second)
        self.last_request_time = 0
        self.rate_limit_delay = 0.5  # 0.5 second between requests (conservative)

        # Logger
        self.logger = get_logger("gmail_bongo")

    async def create_entities(self) -> List[Dict[str, Any]]:
        """Create test emails in Gmail (LLM generation done concurrently)."""
        self.logger.info(f"🥁 Creating {self.entity_count} test emails in Gmail")
        entities: List[Dict[str, Any]] = []

        from monke.generation.gmail import generate_gmail_artifact

        # Who we're emailing
        user_email = await self._get_user_email()

        # Prepare tokens and run all LLM generations concurrently (bounded)
        tokens = [str(uuid.uuid4())[:8] for _ in range(self.entity_count)]
        sem = asyncio.Semaphore(self.llm_max_concurrency)

        async def gen_one(tok: str):
            async with sem:
                subject, body = await generate_gmail_artifact(self.openai_model, tok)
                return tok, subject, body

        gen_results = await asyncio.gather(*[gen_one(t) for t in tokens])

        # Send the emails sequentially (gentle on Gmail limits)
        for tok, subject, body in gen_results:
            email_data = await self._create_test_email(user_email, subject, body)
            entities.append(
                {
                    "type": "message",
                    "id": email_data["id"],
                    "thread_id": email_data["threadId"],
                    "subject": subject,
                    "token": tok,
                    "expected_content": tok,
                }
            )
            self.logger.info(f"📧 Created test email: {email_data['id']}")

            if self.entity_count > 10:
                await asyncio.sleep(0.5)

        self.test_emails = entities
        return entities

    async def update_entities(self) -> List[Dict[str, Any]]:
        """Update test emails in Gmail (LLM generation done concurrently)."""
        self.logger.info("🥁 Updating test emails in Gmail")
        updated_entities: List[Dict[str, Any]] = []

        from monke.generation.gmail import generate_gmail_artifact

        emails_to_update = min(3, self.entity_count)
        if not self.test_emails:
            return updated_entities

        selected = self.test_emails[:emails_to_update]
        sem = asyncio.Semaphore(self.llm_max_concurrency)

        async def gen_update(email_info: Dict[str, Any]):
            token = email_info.get("token") or str(uuid.uuid4())[:8]
            async with sem:
                subject, body = await generate_gmail_artifact(
                    self.openai_model, token, is_update=True
                )
                return email_info, token, subject, body

        gen_results = await asyncio.gather(*[gen_update(e) for e in selected])

        # Apply label updates sequentially (stay inside Gmail rate limits)
        for email_info, token, subject, body in gen_results:
            await self._add_label_to_email(email_info["id"], "IMPORTANT")
            updated_entities.append(
                {
                    "type": "message",
                    "id": email_info["id"],
                    "thread_id": email_info["thread_id"],
                    "subject": email_info["subject"],
                    "token": token,
                    "expected_content": token,
                    "updated": True,
                }
            )
            self.logger.info(f"📝 Updated test email: {email_info['id']}")

            if self.entity_count > 10:
                await asyncio.sleep(0.5)

        return updated_entities

    async def delete_entities(self) -> List[str]:
        """Delete all test entities from Gmail."""
        self.logger.info("🥁 Deleting all test emails from Gmail")

        # Use the specific deletion method to delete all entities
        return await self.delete_specific_entities(self.created_entities)

    async def delete_specific_entities(
        self, entities: List[Dict[str, Any]]
    ) -> List[str]:
        """Permanently delete specific entities from Gmail."""
        self.logger.info(f"🥁 Deleting {len(entities)} specific emails from Gmail")

        deleted_ids = []

        for entity in entities:
            try:
                # Find the corresponding test email
                test_email = next(
                    (
                        email
                        for email in self.test_emails
                        if email["id"] == entity["id"]
                    ),
                    None,
                )

                if test_email:
                    await self._force_delete_email(test_email["id"])
                    deleted_ids.append(test_email["id"])
                    self.logger.info(
                        f"🗑️ Permanently deleted test email: {test_email['id']}"
                    )
                else:
                    self.logger.warning(
                        f"⚠️ Could not find test email for entity: {entity.get('id')}"
                    )

                # Rate limiting
                if len(entities) > 10:
                    await asyncio.sleep(0.5)

            except Exception as e:
                self.logger.warning(
                    f"⚠️ Could not delete entity {entity.get('id')}: {e}"
                )

        # VERIFICATION: Check if emails are actually deleted from Gmail
        self.logger.info(
            "🔍 VERIFYING: Checking if emails are actually deleted from Gmail"
        )
        for entity in entities:
            if entity["id"] in deleted_ids:
                is_deleted = await self._verify_email_deleted(entity["id"])
                if is_deleted:
                    self.logger.info(
                        f"✅ Email {entity['id']} confirmed deleted from Gmail"
                    )
                else:
                    self.logger.warning(
                        f"⚠️ Email {entity['id']} still exists in Gmail!"
                    )

        return deleted_ids

    async def cleanup(self):
        """Clean up any remaining test data."""
        self.logger.info("🧹 Cleaning up remaining test emails in Gmail")

        # Force delete any remaining test emails
        for test_email in self.test_emails:
            try:
                await self._force_delete_email(test_email["id"])
                self.logger.info(f"🧹 Force deleted email: {test_email['id']}")
            except Exception as e:
                self.logger.warning(
                    f"⚠️ Could not force delete email {test_email['id']}: {e}"
                )

    # Helper methods for Gmail API calls
    async def _get_user_email(self) -> str:
        """Get the authenticated user's email address."""
        await self._rate_limit()

        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://gmail.googleapis.com/gmail/v1/users/me/profile",
                headers={
                    "Authorization": f"Bearer {self.access_token}",
                    "Accept": "application/json",
                },
            )

            if response.status_code != 200:
                raise Exception(
                    f"Failed to get user profile: {response.status_code} - {response.text}"
                )

            return response.json()["emailAddress"]

    async def _create_test_email(
        self, to_email: str, subject: str, body: str
    ) -> Dict[str, Any]:
        """Create a test email via Gmail API."""
        await self._rate_limit()

        # Create email message
        message = f"To: {to_email}\r\nSubject: {subject}\r\n\r\n{body}"
        raw_message = base64.urlsafe_b64encode(message.encode()).decode()

        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://gmail.googleapis.com/gmail/v1/users/me/messages/send",
                headers={
                    "Authorization": f"Bearer {self.access_token}",
                    "Content-Type": "application/json",
                },
                json={"raw": raw_message},
            )

            if response.status_code != 200:
                raise Exception(
                    f"Failed to create email: {response.status_code} - {response.text}"
                )

            result = response.json()

            # Track created email
            self.created_entities.append(
                {"id": result["id"], "thread_id": result["threadId"]}
            )

            return result

    async def _add_label_to_email(self, message_id: str, label: str):
        """Add a label to an email to simulate update."""
        await self._rate_limit()

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"https://gmail.googleapis.com/gmail/v1/users/me/messages/{message_id}/modify",
                headers={
                    "Authorization": f"Bearer {self.access_token}",
                    "Content-Type": "application/json",
                },
                json={"addLabelIds": [label]},
            )

            if response.status_code != 200:
                raise Exception(
                    f"Failed to update email: {response.status_code} - {response.text}"
                )

    async def _delete_test_email(self, message_id: str):
        """Delete a test email via Gmail API (move to trash)."""
        await self._rate_limit()

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"https://gmail.googleapis.com/gmail/v1/users/me/messages/{message_id}/trash",
                headers={"Authorization": f"Bearer {self.access_token}"},
            )

            if response.status_code != 200:
                raise Exception(
                    f"Failed to delete email: {response.status_code} - {response.text}"
                )

    async def _verify_email_deleted(self, message_id: str) -> bool:
        """Verify if an email is actually deleted (in trash) from Gmail."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"https://gmail.googleapis.com/gmail/v1/users/me/messages/{message_id}",
                    headers={"Authorization": f"Bearer {self.access_token}"},
                )

                if response.status_code == 404:
                    # Email not found - successfully deleted
                    return True
                elif response.status_code == 200:
                    # Check if email is in trash
                    data = response.json()
                    return "TRASH" in data.get("labelIds", [])
                else:
                    # Unexpected response
                    self.logger.warning(
                        f"⚠️ Unexpected response checking {message_id}: {response.status_code}"
                    )
                    return False

        except Exception as e:
            self.logger.warning(
                f"⚠️ Error verifying email deletion for {message_id}: {e}"
            )
            return False

    async def _force_delete_email(self, message_id: str):
        """Force delete an email (permanently delete)."""
        try:
            # First move to trash if not already there
            await self._delete_test_email(message_id)

            # Then permanently delete
            async with httpx.AsyncClient() as client:
                response = await client.delete(
                    f"https://gmail.googleapis.com/gmail/v1/users/me/messages/{message_id}",
                    headers={"Authorization": f"Bearer {self.access_token}"},
                )

                if response.status_code == 204:
                    self.logger.info(f"🧹 Force deleted email: {message_id}")
                else:
                    self.logger.warning(
                        f"⚠️ Force delete failed for {message_id}: {response.status_code}"
                    )
        except Exception as e:
            self.logger.warning(f"Could not force delete {message_id}: {e}")

    async def _rate_limit(self):
        """Implement rate limiting for Gmail API."""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time

        if time_since_last < self.rate_limit_delay:
            sleep_time = self.rate_limit_delay - time_since_last
            await asyncio.sleep(sleep_time)

        self.last_request_time = time.time()
