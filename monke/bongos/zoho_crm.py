"""Zoho CRM bongo for E2E testing.

Creates, updates, and deletes test data for multiple entity types:
- Contacts
- Accounts
- Deals
- Leads

Supports OAuth via:
- Direct access_token + refresh_token
- client_id + client_secret + refresh_token (automatically exchanges for access_token)
"""

import asyncio
import random
import time
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import httpx
from monke.bongos.base_bongo import BaseBongo
from monke.generation.zoho_crm import (
    generate_zoho_crm_account,
    generate_zoho_crm_contact,
    generate_zoho_crm_deal,
    generate_zoho_crm_lead,
)
from monke.utils.logging import get_logger


class ZohoCRMBongo(BaseBongo):
    """Creates/updates/deletes Zoho CRM entities using OAuth token.

    Supports testing of: Contacts, Accounts, Deals, Leads.

    Authentication options:
    - access_token + refresh_token: Use directly
    - client_id + client_secret + refresh_token: Auto-refreshes access token at init
    """

    connector_type = "zoho_crm"

    def __init__(self, credentials: Dict[str, Any], **kwargs):
        # Don't call super().__init__ yet - we need to set up _raw_credentials first
        self._raw_credentials = credentials
        self.created_entities = []  # From BaseBongo

        self.logger = get_logger("zoho_crm_bongo")

        # OAuth credentials - support both direct token and refresh flow
        self.access_token: Optional[str] = credentials.get("access_token")
        self.client_id: Optional[str] = credentials.get("client_id")
        self.client_secret: Optional[str] = credentials.get("client_secret")
        self.refresh_token: Optional[str] = credentials.get("refresh_token")

        # API domains - vary by region (US, EU, IN, AU, etc.)
        self.api_domain: str = kwargs.get("api_domain", "https://www.zohoapis.com")
        self.accounts_url: str = kwargs.get("accounts_url", "https://accounts.zoho.com")

        self.entity_count: int = int(kwargs.get("entity_count", 3))
        self.openai_model: str = kwargs.get("openai_model", "gpt-4.1-mini")
        # Zoho CRM has strict rate limits - use 500ms between requests
        self.rate_limit_delay = float(kwargs.get("rate_limit_delay_ms", 500)) / 1000.0

        # Track entities by type
        self._contacts: List[Dict[str, Any]] = []
        self._accounts: List[Dict[str, Any]] = []
        self._deals: List[Dict[str, Any]] = []
        self._leads: List[Dict[str, Any]] = []

        self._last_req = 0.0
        self._token_refreshed = False

        # If we have client credentials but no access token, refresh NOW (sync)
        # This ensures credentials are ready before infrastructure reads them
        if self.client_id and self.client_secret and self.refresh_token and not self.access_token:
            self._refresh_access_token_sync()

    @property
    def credentials(self) -> Dict[str, Any]:
        """Return credentials in the format expected by backend (access_token + refresh_token)."""
        return {
            "access_token": self.access_token,
            "refresh_token": self.refresh_token,
        }

    @credentials.setter
    def credentials(self, value: Dict[str, Any]) -> None:
        """Allow setting credentials (required by base class pattern)."""
        self._raw_credentials = value

    def _is_rate_limit_error(self, response: httpx.Response) -> bool:
        """Check if response is a Zoho rate limit error.

        Zoho returns 400 (not 429) with specific error for OAuth rate limits:
        - error_description: "You have made too many requests continuously..."
        - error: "Access Denied"
        """
        if response.status_code == 429:
            return True
        if response.status_code == 400:
            try:
                data = response.json()
                error_desc = data.get("error_description", "").lower()
                error_type = data.get("error", "").lower()
                # Zoho's specific rate limit signature
                if "too many requests" in error_desc and error_type == "access denied":
                    return True
            except Exception:
                pass
        return False

    def _refresh_access_token_sync(self):
        """Synchronously exchange refresh token for a new access token with retry."""
        token_url = f"{self.accounts_url}/oauth/v2/token"
        params = {
            "grant_type": "refresh_token",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "refresh_token": self.refresh_token,
        }

        max_retries = 5
        base_delay = 5.0  # Start with 5 seconds

        self.logger.info("🔑 Exchanging refresh token for access token (sync)...")

        for attempt in range(max_retries):
            with httpx.Client(timeout=30) as client:
                response = client.post(token_url, params=params)

                if response.status_code == 200:
                    data = response.json()
                    self.access_token = data.get("access_token")
                    self._token_refreshed = True
                    self.logger.info("✅ Successfully obtained access token")
                    return

                # Check for rate limiting
                if self._is_rate_limit_error(response):
                    # Exponential backoff with jitter
                    delay = base_delay * (2 ** attempt) + random.uniform(0, 2)
                    self.logger.warning(
                        f"⏳ Zoho rate limit hit, waiting {delay:.1f}s before retry "
                        f"(attempt {attempt + 1}/{max_retries})"
                    )
                    time.sleep(delay)
                    continue

                # Non-rate-limit error
                self.logger.error(f"Token refresh failed: {response.status_code} - {response.text}")
                raise ValueError(f"Failed to refresh Zoho token: {response.text}")

        # Exhausted all retries
        raise ValueError(f"Failed to refresh Zoho token after {max_retries} attempts (rate limited)")

    async def _ensure_access_token(self):
        """Ensure we have a valid access token, refreshing if needed."""
        if self.access_token and self._token_refreshed:
            return

        if self.client_id and self.client_secret and self.refresh_token:
            self.logger.info("🔑 Exchanging refresh token for access token...")
            await self._refresh_access_token()
        elif not self.access_token:
            raise ValueError(
                "No valid credentials provided. Need either 'access_token' or "
                "'client_id' + 'client_secret' + 'refresh_token'"
            )

    async def _refresh_access_token(self):
        """Exchange refresh token for a new access token with retry."""
        token_url = f"{self.accounts_url}/oauth/v2/token"
        params = {
            "grant_type": "refresh_token",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "refresh_token": self.refresh_token,
        }

        max_retries = 5
        base_delay = 5.0  # Start with 5 seconds

        for attempt in range(max_retries):
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(token_url, params=params)

                if response.status_code == 200:
                    data = response.json()
                    self.access_token = data.get("access_token")
                    self._token_refreshed = True
                    self.logger.info("✅ Successfully obtained access token")
                    return

                # Check for rate limiting
                if self._is_rate_limit_error(response):
                    # Exponential backoff with jitter
                    delay = base_delay * (2 ** attempt) + random.uniform(0, 2)
                    self.logger.warning(
                        f"⏳ Zoho rate limit hit, waiting {delay:.1f}s before retry "
                        f"(attempt {attempt + 1}/{max_retries})"
                    )
                    await asyncio.sleep(delay)
                    continue

                # Non-rate-limit error
                self.logger.error(f"Token refresh failed: {response.status_code} - {response.text}")
                raise ValueError(f"Failed to refresh Zoho token: {response.text}")

        # Exhausted all retries
        raise ValueError(f"Failed to refresh Zoho token after {max_retries} attempts (rate limited)")

    def _get_base_url(self) -> str:
        """Get the base URL for Zoho CRM API calls."""
        return f"{self.api_domain}/crm/v8"

    def _hdrs(self) -> Dict[str, str]:
        return {
            "Authorization": f"Zoho-oauthtoken {self.access_token}",
            "Content-Type": "application/json",
        }

    async def _pace(self):
        """Respect API rate limits."""
        now = time.time()
        if (delta := now - self._last_req) < self.rate_limit_delay:
            await asyncio.sleep(self.rate_limit_delay - delta)
        self._last_req = time.time()

    async def _create_record(
        self, client: httpx.AsyncClient, module: str, payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Create a record in a Zoho CRM module with retry on rate limit."""
        max_retries = 5
        base_delay = 2.0

        for attempt in range(max_retries):
            await self._pace()
            r = await client.post(
                f"{self._get_base_url()}/{module}",
                headers=self._hdrs(),
                json={"data": [payload]},
            )

            # Check for rate limiting (429 or Zoho's 400 "too many requests")
            if self._is_rate_limit_error(r):
                delay = base_delay * (2 ** attempt) + random.uniform(0, 1)
                self.logger.warning(
                    f"⏳ Zoho rate limit on {module} create, waiting {delay:.1f}s "
                    f"(attempt {attempt + 1}/{max_retries})"
                )
                await asyncio.sleep(delay)
                continue

            if r.status_code not in (200, 201):
                self.logger.error(f"Zoho CRM create {module} failed {r.status_code}: {r.text}")
                return {}

            data = r.json()
            records = data.get("data", [])
            if records and records[0].get("status") == "success":
                return records[0]["details"]
            self.logger.error(f"Zoho CRM create {module} failed: {data}")
            return {}

        self.logger.error(f"Zoho CRM create {module} failed after {max_retries} retries (rate limited)")
        return {}

    async def _delete_record(
        self, client: httpx.AsyncClient, module: str, record_id: str
    ) -> bool:
        """Delete a record from a Zoho CRM module with retry on rate limit."""
        max_retries = 5
        base_delay = 2.0

        for attempt in range(max_retries):
            await self._pace()
            r = await client.delete(
                f"{self._get_base_url()}/{module}?ids={record_id}",
                headers=self._hdrs(),
            )

            # Check for rate limiting
            if self._is_rate_limit_error(r):
                delay = base_delay * (2 ** attempt) + random.uniform(0, 1)
                self.logger.warning(
                    f"⏳ Zoho rate limit on {module} delete, waiting {delay:.1f}s "
                    f"(attempt {attempt + 1}/{max_retries})"
                )
                await asyncio.sleep(delay)
                continue

            return r.status_code in (200, 204)

        self.logger.warning(f"Zoho CRM delete {module}/{record_id} failed after {max_retries} retries")
        return False

    async def create_entities(self) -> List[Dict[str, Any]]:
        """Create test entities in Zoho CRM (Contacts, Accounts, Deals, Leads)."""
        await self._ensure_access_token()
        self.logger.info(f"🥁 Creating {self.entity_count} entities of each type in Zoho CRM")
        out: List[Dict[str, Any]] = []

        # Generate tokens for each entity type
        contact_tokens = [str(uuid.uuid4())[:8] for _ in range(self.entity_count)]
        account_tokens = [str(uuid.uuid4())[:8] for _ in range(self.entity_count)]
        deal_tokens = [str(uuid.uuid4())[:8] for _ in range(self.entity_count)]
        lead_tokens = [str(uuid.uuid4())[:8] for _ in range(self.entity_count)]

        # Generate all content in parallel
        async def gen_contact(token: str):
            return ("contact", token, await generate_zoho_crm_contact(self.openai_model, token))

        async def gen_account(token: str):
            return ("account", token, await generate_zoho_crm_account(self.openai_model, token))

        async def gen_deal(token: str):
            return ("deal", token, await generate_zoho_crm_deal(self.openai_model, token))

        async def gen_lead(token: str):
            return ("lead", token, await generate_zoho_crm_lead(self.openai_model, token))

        gen_tasks = (
            [gen_contact(t) for t in contact_tokens]
            + [gen_account(t) for t in account_tokens]
            + [gen_deal(t) for t in deal_tokens]
            + [gen_lead(t) for t in lead_tokens]
        )
        gen_results = await asyncio.gather(*gen_tasks)

        async with httpx.AsyncClient(timeout=30) as client:
            for entity_type, token, data in gen_results:
                if entity_type == "contact":
                    ent = await self._create_contact(client, token, data)
                elif entity_type == "account":
                    ent = await self._create_account(client, token, data)
                elif entity_type == "deal":
                    ent = await self._create_deal(client, token, data)
                elif entity_type == "lead":
                    ent = await self._create_lead(client, token, data)
                else:
                    continue

                if ent:
                    out.append(ent)
                    # Include all fields needed for verification (token, path, etc.)
                    self.created_entities.append(ent)

        return out

    async def _create_contact(
        self, client: httpx.AsyncClient, token: str, c: Any
    ) -> Dict[str, Any]:
        """Create a contact in Zoho CRM."""
        payload = {
            "First_Name": c.first_name,
            "Last_Name": c.last_name,
            "Email": c.email,
            **({"Phone": c.phone} if c.phone else {}),
            **({"Mobile": c.mobile} if c.mobile else {}),
            **({"Title": c.title} if c.title else {}),
            **({"Department": c.department} if c.department else {}),
            **({"Description": c.description} if c.description else {}),
            **({"Mailing_Street": c.mailing_street} if c.mailing_street else {}),
            **({"Mailing_City": c.mailing_city} if c.mailing_city else {}),
            **({"Mailing_State": c.mailing_state} if c.mailing_state else {}),
            **({"Mailing_Zip": c.mailing_zip} if c.mailing_zip else {}),
            **({"Mailing_Country": c.mailing_country} if c.mailing_country else {}),
        }
        result = await self._create_record(client, "Contacts", payload)
        if result:
            contact_id = result["id"]
            ent = {
                "type": "contact",
                "id": f"contact_{contact_id}",
                "zoho_id": contact_id,
                "name": f"{c.first_name} {c.last_name}",
                "token": token,
                "expected_content": token,
                "path": f"zoho_crm/contact/{contact_id}",
            }
            self._contacts.append(ent)
            self.logger.info(f"✅ Created contact: {contact_id}")
            return ent
        return {}

    async def _create_account(
        self, client: httpx.AsyncClient, token: str, a: Any
    ) -> Dict[str, Any]:
        """Create an account in Zoho CRM."""
        payload = {
            "Account_Name": a.account_name,
            **({"Website": a.website} if a.website else {}),
            **({"Phone": a.phone} if a.phone else {}),
            **({"Industry": a.industry} if a.industry else {}),
            **({"Description": a.description} if a.description else {}),
            **({"Billing_Street": a.billing_street} if a.billing_street else {}),
            **({"Billing_City": a.billing_city} if a.billing_city else {}),
            **({"Billing_State": a.billing_state} if a.billing_state else {}),
            **({"Billing_Code": a.billing_code} if a.billing_code else {}),
            **({"Billing_Country": a.billing_country} if a.billing_country else {}),
        }
        result = await self._create_record(client, "Accounts", payload)
        if result:
            account_id = result["id"]
            ent = {
                "type": "account",
                "id": f"account_{account_id}",
                "zoho_id": account_id,
                "name": a.account_name,
                "token": token,
                "expected_content": token,
                "path": f"zoho_crm/account/{account_id}",
            }
            self._accounts.append(ent)
            self.logger.info(f"✅ Created account: {account_id}")
            return ent
        return {}

    async def _create_deal(
        self, client: httpx.AsyncClient, token: str, d: Any
    ) -> Dict[str, Any]:
        """Create a deal in Zoho CRM."""
        # Closing_Date is required
        closing_date = (datetime.utcnow() + timedelta(days=30)).strftime("%Y-%m-%d")
        payload = {
            "Deal_Name": d.deal_name,
            "Stage": d.stage or "Qualification",
            "Closing_Date": closing_date,
            **({"Amount": d.amount} if d.amount else {}),
            **({"Description": d.description} if d.description else {}),
            **({"Next_Step": d.next_step} if d.next_step else {}),
            **({"Lead_Source": d.lead_source} if d.lead_source else {}),
        }
        result = await self._create_record(client, "Deals", payload)
        if result:
            deal_id = result["id"]
            ent = {
                "type": "deal",
                "id": f"deal_{deal_id}",
                "zoho_id": deal_id,
                "name": d.deal_name,
                "token": token,
                "expected_content": token,
                "path": f"zoho_crm/deal/{deal_id}",
            }
            self._deals.append(ent)
            self.logger.info(f"✅ Created deal: {deal_id}")
            return ent
        return {}

    async def _create_lead(
        self, client: httpx.AsyncClient, token: str, l: Any
    ) -> Dict[str, Any]:
        """Create a lead in Zoho CRM."""
        payload = {
            "First_Name": l.first_name,
            "Last_Name": l.last_name,
            "Company": l.company,
            "Email": l.email,
            **({"Phone": l.phone} if l.phone else {}),
            **({"Mobile": l.mobile} if l.mobile else {}),
            **({"Title": l.title} if l.title else {}),
            **({"Industry": l.industry} if l.industry else {}),
            **({"Lead_Source": l.lead_source} if l.lead_source else {}),
            **({"Lead_Status": l.lead_status} if l.lead_status else {}),
            **({"Description": l.description} if l.description else {}),
            **({"Street": l.street} if l.street else {}),
            **({"City": l.city} if l.city else {}),
            **({"State": l.state} if l.state else {}),
            **({"Zip_Code": l.zip_code} if l.zip_code else {}),
            **({"Country": l.country} if l.country else {}),
        }
        result = await self._create_record(client, "Leads", payload)
        if result:
            lead_id = result["id"]
            ent = {
                "type": "lead",
                "id": f"lead_{lead_id}",
                "zoho_id": lead_id,
                "name": f"{l.first_name} {l.last_name}",
                "token": token,
                "expected_content": token,
                "path": f"zoho_crm/lead/{lead_id}",
            }
            self._leads.append(ent)
            self.logger.info(f"✅ Created lead: {lead_id}")
            return ent
        return {}

    async def update_entities(self) -> List[Dict[str, Any]]:
        """Update subset of entities for incremental sync testing."""
        await self._ensure_access_token()
        all_entities = self._contacts + self._accounts + self._deals + self._leads
        if not all_entities:
            return []

        self.logger.info("🥁 Updating some Zoho CRM entities")
        updated: List[Dict[str, Any]] = []

        async with httpx.AsyncClient(timeout=30) as client:
            # Update first few of each type
            for ent in all_entities[: min(4, len(all_entities))]:
                await self._pace()
                zoho_id = ent["zoho_id"]

                if ent["type"] == "contact":
                    payload = {
                        "data": [
                            {
                                "id": zoho_id,
                                "Title": "Senior Test Engineer",
                                "Department": "Monke QA",
                            }
                        ]
                    }
                    module = "Contacts"
                elif ent["type"] == "account":
                    payload = {
                        "data": [{"id": zoho_id, "Description": "Updated by Monke test"}]
                    }
                    module = "Accounts"
                elif ent["type"] == "deal":
                    payload = {
                        "data": [{"id": zoho_id, "Next_Step": "Follow up - Monke test"}]
                    }
                    module = "Deals"
                elif ent["type"] == "lead":
                    payload = {
                        "data": [{"id": zoho_id, "Title": "Updated Lead Title"}]
                    }
                    module = "Leads"
                else:
                    continue

                r = await client.put(
                    f"{self._get_base_url()}/{module}",
                    headers=self._hdrs(),
                    json=payload,
                )

                if r.status_code == 200:
                    updated.append({**ent, "updated": True})
                    self.logger.info(f"✅ Updated {ent['type']}: {zoho_id}")
                else:
                    self.logger.warning(f"Update failed {r.status_code}: {r.text}")

        return updated

    async def delete_entities(self) -> List[str]:
        """Delete all test entities."""
        await self._ensure_access_token()
        # Delete in reverse dependency order (deals first, then contacts/leads, then accounts)
        all_entities = self._deals + self._leads + self._contacts + self._accounts
        return await self.delete_specific_entities(all_entities)

    async def delete_specific_entities(self, entities: List[Dict[str, Any]]) -> List[str]:
        """Delete specific entities."""
        self.logger.info(f"🥁 Deleting {len(entities)} Zoho CRM entities")
        deleted: List[str] = []

        # Map type to module
        type_to_module = {
            "contact": "Contacts",
            "account": "Accounts",
            "deal": "Deals",
            "lead": "Leads",
        }

        async with httpx.AsyncClient(timeout=30) as client:
            for ent in entities:
                try:
                    module = type_to_module.get(ent["type"])
                    if not module:
                        continue
                    zoho_id = ent["zoho_id"]
                    if await self._delete_record(client, module, zoho_id):
                        deleted.append(ent["id"])
                        self.logger.info(f"✅ Deleted {ent['type']}: {zoho_id}")

                        # Remove from tracking lists
                        if ent["type"] == "contact":
                            self._contacts = [c for c in self._contacts if c["id"] != ent["id"]]
                        elif ent["type"] == "account":
                            self._accounts = [a for a in self._accounts if a["id"] != ent["id"]]
                        elif ent["type"] == "deal":
                            self._deals = [d for d in self._deals if d["id"] != ent["id"]]
                        elif ent["type"] == "lead":
                            self._leads = [l for l in self._leads if l["id"] != ent["id"]]
                    else:
                        self.logger.warning(f"Delete failed for {ent['type']}: {zoho_id}")
                except Exception as e:
                    self.logger.warning(f"Delete error {ent['id']}: {e}")

        return deleted

    async def cleanup(self):
        """Comprehensive cleanup of all test Zoho CRM entities."""
        await self._ensure_access_token()
        self.logger.info("🧹 Starting comprehensive Zoho CRM cleanup")

        cleanup_stats = {"deleted": 0, "errors": 0}

        try:
            # Delete all tracked entities
            all_entities = self._deals + self._leads + self._contacts + self._accounts
            if all_entities:
                self.logger.info(f"🗑️ Cleaning up {len(all_entities)} tracked entities")
                deleted = await self.delete_specific_entities(all_entities)
                cleanup_stats["deleted"] += len(deleted)

            # Search for orphaned test entities
            await self._cleanup_orphaned_entities(cleanup_stats)

            self.logger.info(
                f"🧹 Cleanup completed: {cleanup_stats['deleted']} entities deleted, "
                f"{cleanup_stats['errors']} errors"
            )
        except Exception as e:
            self.logger.error(f"❌ Error during comprehensive cleanup: {e}")

    async def _cleanup_orphaned_entities(self, stats: Dict[str, Any]):
        """Find and delete orphaned test entities from previous runs."""
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                search_url = f"{self._get_base_url()}/coql"

                # Search for test contacts
                contact_query = {
                    "select_query": (
                        "select id, Email from Contacts "
                        "where Email like '%example.test%' or Email like '%monke.test%' "
                        "limit 100"
                    )
                }
                await self._cleanup_by_query(client, search_url, contact_query, "Contacts", stats)

                # Search for test leads
                lead_query = {
                    "select_query": (
                        "select id, Email from Leads "
                        "where Email like '%example.test%' or Email like '%monke.test%' "
                        "limit 100"
                    )
                }
                await self._cleanup_by_query(client, search_url, lead_query, "Leads", stats)

                # Search for test accounts (by name pattern)
                account_query = {
                    "select_query": (
                        "select id, Account_Name from Accounts "
                        "where Account_Name like '%Test%' or Account_Name like '%Monke%' "
                        "limit 100"
                    )
                }
                await self._cleanup_by_query(client, search_url, account_query, "Accounts", stats)

                # Search for test deals (by name pattern)
                deal_query = {
                    "select_query": (
                        "select id, Deal_Name from Deals "
                        "where Deal_Name like '%Test%' or Deal_Name like '%Monke%' "
                        "limit 100"
                    )
                }
                await self._cleanup_by_query(client, search_url, deal_query, "Deals", stats)

        except Exception as e:
            self.logger.warning(f"⚠️ Could not search for orphaned entities: {e}")

    async def _cleanup_by_query(
        self,
        client: httpx.AsyncClient,
        search_url: str,
        query: Dict[str, str],
        module: str,
        stats: Dict[str, Any],
    ):
        """Execute a COQL query and delete matching records."""
        try:
            r = await client.post(search_url, headers=self._hdrs(), json=query)
            if r.status_code == 200:
                data = r.json()
                records = data.get("data", [])
                if records:
                    self.logger.info(f"🔍 Found {len(records)} orphaned {module} to clean")
                    for record in records:
                        try:
                            await self._pace()
                            if await self._delete_record(client, module, record["id"]):
                                stats["deleted"] += 1
                                self.logger.info(f"✅ Deleted orphaned {module}: {record['id']}")
                            else:
                                stats["errors"] += 1
                        except Exception as e:
                            stats["errors"] += 1
                            self.logger.warning(f"⚠️ Failed to delete {module} {record['id']}: {e}")
        except Exception as e:
            self.logger.warning(f"⚠️ COQL query for {module} failed: {e}")
