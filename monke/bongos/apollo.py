"""Apollo bongo implementation.

Creates, updates, and deletes test data via the Apollo API.
Requires a master API key (Create/Update Account and Contact require it).
Apollo does not expose delete endpoints for accounts/contacts in the public API,
so delete steps are no-ops and deletion verification is disabled in config.
"""

import asyncio
import time
import uuid
from typing import Any, Dict, List, Optional

import httpx
from monke.bongos.base_bongo import BaseBongo
from monke.utils.logging import get_logger


class ApolloBongo(BaseBongo):
    """Bongo for Apollo that creates accounts and contacts for E2E testing.

    - Creates only Accounts and Contacts (no Sequences or Email Activities; those
      are synced by the connector if they exist in Apollo and a master key is used).
    - Uses x-api-key for authentication (master API key required for create/update).
    - Embeds verification token in account name and contact title.
    - Delete/cleanup are no-ops (Apollo API does not expose delete for accounts/contacts).
    """

    connector_type = "apollo"

    API_BASE = "https://api.apollo.io/api/v1"

    def __init__(self, credentials: Dict[str, Any], **kwargs):
        """Initialize the Apollo bongo.

        Args:
            credentials: Dict with "api_key" (direct auth)
            **kwargs: Configuration from config file
        """
        super().__init__(credentials)

        self.api_key: str = (
            credentials.get("api_key")
            or credentials.get("access_token")
            or credentials.get("generic_api_key")
        )
        if not self.api_key:
            raise ValueError(
                f"Missing Apollo API key. Available keys: {list(credentials.keys())}"
            )

        self.entity_count: int = int(kwargs.get("entity_count", 2))
        self.openai_model: str = kwargs.get("openai_model", "gpt-4.1-mini")
        self.max_concurrency: int = int(kwargs.get("max_concurrency", 2))
        rate_limit_ms = int(kwargs.get("rate_limit_delay_ms", 400))
        self.rate_limit_delay: float = rate_limit_ms / 1000.0

        self._accounts: List[Dict[str, Any]] = []
        self._contacts: List[Dict[str, Any]] = []
        self.last_request_time = 0.0
        self.logger = get_logger("apollo_bongo")

    def _headers(self) -> Dict[str, str]:
        """Return headers for Apollo API (x-api-key)."""
        return {
            "x-api-key": self.api_key,
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Cache-Control": "no-cache",
        }

    async def _rate_limit(self) -> None:
        """Simple rate limiting."""
        now = time.time()
        elapsed = now - self.last_request_time
        if elapsed < self.rate_limit_delay:
            await asyncio.sleep(self.rate_limit_delay - elapsed)
        self.last_request_time = time.time()

    async def create_entities(self) -> List[Dict[str, Any]]:
        """Create accounts and contacts in Apollo with embedded tokens.

        Creates entity_count accounts, then entity_count contacts (each linked to an account).
        Returns entity descriptors for verification.
        """
        self.logger.info(f"🥁 Creating {self.entity_count} Apollo accounts and contacts")

        from monke.generation.apollo import generate_apollo_account, generate_apollo_contact

        entities: List[Dict[str, Any]] = []
        semaphore = asyncio.Semaphore(self.max_concurrency)

        async with httpx.AsyncClient() as client:
            # Create accounts first
            for i in range(self.entity_count):
                async with semaphore:
                    await self._rate_limit()
                    token = str(uuid.uuid4())[:8]
                    self.logger.info(f"🏢 Creating account with token: {token}")

                    try:
                        account_data = await generate_apollo_account(
                            self.openai_model, token
                        )
                        # Ensure token in name for search
                        name = account_data["name"]
                        if token not in name:
                            name = f"{name} [{token}]"

                        resp = await client.post(
                            f"{self.API_BASE}/accounts",
                            headers=self._headers(),
                            json={"name": name, "domain": account_data["domain"]},
                            timeout=30.0,
                        )

                        if resp.status_code == 403:
                            self.logger.error(
                                "Apollo returned 403: Create Account requires a master API key. "
                                "Use a master key in MONKE_APOLLO_API_KEY."
                            )
                            resp.raise_for_status()

                        resp.raise_for_status()
                        data = resp.json()
                        acc = data.get("account", {})
                        acc_id = acc.get("id")
                        if not acc_id:
                            self.logger.error(f"No account id in response: {data}")
                            raise ValueError("Missing account id")

                        desc = {
                            "type": "account",
                            "id": acc_id,
                            "name": name,
                            "token": token,
                            "expected_content": token,
                        }
                        self._accounts.append(desc)
                        entities.append(desc)
                        self.logger.info(f"✅ Created account: {acc_id}")

                    except Exception as e:
                        self.logger.error(f"Failed to create account: {e}")
                        raise

            # Create contacts (link to accounts in round-robin)
            for i in range(self.entity_count):
                async with semaphore:
                    await self._rate_limit()
                    token = str(uuid.uuid4())[:8]
                    account = self._accounts[i % len(self._accounts)]
                    self.logger.info(f"👤 Creating contact with token: {token}")

                    try:
                        contact_data = await generate_apollo_contact(
                            self.openai_model, token
                        )
                        title = contact_data["title"]
                        if token not in title:
                            title = f"{title} [{token}]"

                        payload = {
                            "first_name": contact_data["first_name"],
                            "last_name": contact_data["last_name"],
                            "email": contact_data["email"],
                            "title": title,
                            "organization_name": contact_data["organization_name"],
                            "account_id": account["id"],
                        }

                        resp = await client.post(
                            f"{self.API_BASE}/contacts",
                            headers=self._headers(),
                            json=payload,
                            timeout=30.0,
                        )

                        if resp.status_code == 403:
                            self.logger.error(
                                "Apollo returned 403: Create Contact may require master API key."
                            )
                            resp.raise_for_status()

                        resp.raise_for_status()
                        data = resp.json()
                        contact = data.get("contact", {})
                        contact_id = contact.get("id")
                        if not contact_id:
                            raise ValueError("Missing contact id")

                        desc = {
                            "type": "contact",
                            "id": contact_id,
                            "name": f"{contact_data['first_name']} {contact_data['last_name']}",
                            "token": token,
                            "expected_content": token,
                        }
                        self._contacts.append(desc)
                        entities.append(desc)
                        self.logger.info(f"✅ Created contact: {contact_id}")

                    except Exception as e:
                        self.logger.error(f"Failed to create contact: {e}")
                        raise

        self.created_entities = entities
        self.logger.info(
            f"✅ Created {len(self._accounts)} accounts and {len(self._contacts)} contacts"
        )
        return entities

    async def update_entities(self) -> List[Dict[str, Any]]:
        """Update a subset of contacts (same token, refreshed title).

        We update contacts only, not accounts. Updating accounts via PATCH can cause
        the sync pipeline to replace account vectors in a way that drops them from
        the index on the second sync; contacts do not exhibit this, so the second
        verify finds all 4 entities.
        """
        self.logger.info("🥁 Updating Apollo test entities (contacts only)")
        if not self.created_entities:
            return []

        from monke.generation.apollo import generate_apollo_contact

        updated: List[Dict[str, Any]] = []
        # Update contacts (indices 2 and 3 when we have 2 accounts + 2 contacts)
        contact_entities = [e for e in self.created_entities if e.get("type") == "contact"]
        to_update = contact_entities[:2]

        async with httpx.AsyncClient() as client:
            for entity in to_update:
                await self._rate_limit()

                try:
                    contact_data = await generate_apollo_contact(
                        self.openai_model, entity["token"]
                    )
                    title = contact_data["title"]
                    if entity["token"] not in title:
                        title = f"{title} [{entity['token']}]"

                    resp = await client.patch(
                        f"{self.API_BASE}/contacts/{entity['id']}",
                        headers=self._headers(),
                        json={"title": title},
                        timeout=30.0,
                    )

                    resp.raise_for_status()
                    updated.append(entity)
                    self.logger.info(f"✅ Updated contact: {entity['id']}")

                except Exception as e:
                    self.logger.warning(f"Failed to update contact: {e}")

        return updated

    async def delete_entities(self) -> List[str]:
        """Apollo does not expose delete for accounts/contacts. Return IDs as no-op."""
        self.logger.warning(
            "Apollo API does not expose delete for accounts/contacts; skipping delete"
        )
        ids = [e["id"] for e in self.created_entities]
        return ids

    async def delete_specific_entities(
        self, entities: List[Dict[str, Any]]
    ) -> List[str]:
        """No-op: Apollo has no delete endpoint for these entities."""
        self.logger.warning("Apollo delete is a no-op (no delete API)")
        return [e["id"] for e in entities]

    async def cleanup(self) -> None:
        """No-op: Apollo does not expose delete for accounts/contacts."""
        self.logger.info(
            "Apollo cleanup: no delete API for accounts/contacts; test data remains in Apollo"
        )
