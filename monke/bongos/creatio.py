"""Creatio CRM bongo implementation using OAuth 2.0 Client Credentials Grant.

Creates, updates, and deletes test entities via the Creatio OData 4 API.
Uses OAuth 2.0 client credentials grant to exchange client_id/client_secret
for an access token via the Creatio Identity Service.

Covers entity types: Account, Contact, Campaign, Opportunity, Order.

Note: Lead entity type was removed because Creatio's internal business
processes lock Leads and prevent deletion (returns 500).
"""

import asyncio
import time
import uuid
from typing import Any, Dict, List, Optional

import httpx
from monke.bongos.base_bongo import BaseBongo
from monke.utils.logging import get_logger


class CreatioBongo(BaseBongo):
    """Creatio CRM bongo implementation.

    Creates, updates, and deletes test entities via the Creatio OData 4 API.
    Uses client credentials grant for authentication.

    Tests the following entity types (in dependency order):
    - Account (standalone)
    - Contact (links to Account)
    - Campaign (standalone)
    - Opportunity (links to Account + Contact)
    - Order (links to Account + Contact)
    """

    connector_type = "creatio"

    def __init__(self, credentials: Dict[str, Any], **kwargs):
        """Initialize the Creatio bongo.

        Args:
            credentials: Creatio credentials with client_id and client_secret
            **kwargs: Configuration from config file (instance_url, entity_count, etc.)
        """
        super().__init__(credentials)
        self.client_id = credentials.get("client_id", "")
        self.client_secret = credentials.get("client_secret", "")
        self.instance_url = kwargs.get("instance_url", "")
        self.access_token: Optional[str] = None

        # Derive identity service URL from instance URL
        # Creatio Identity Service lives at {instance}-is.creatio.com
        self.identity_service_url = self._derive_identity_service_url(self.instance_url)

        # Normalize instance URL (strip protocol and trailing slash)
        self.instance_url = self._normalize_url(self.instance_url)

        # Configuration from config file
        self.entity_count = int(kwargs.get("entity_count", 3))
        self.openai_model = kwargs.get("openai_model", "gpt-4.1-mini")

        # Test data tracking — ALL entity types
        self._accounts: List[Dict[str, Any]] = []
        self._contacts: List[Dict[str, Any]] = []
        self._campaigns: List[Dict[str, Any]] = []
        self._opportunities: List[Dict[str, Any]] = []
        self._orders: List[Dict[str, Any]] = []

        # Rate limiting (0.5s between requests)
        self.last_request_time = 0.0
        self.rate_limit_delay = 0.5

        # Logger
        self.logger = get_logger("creatio_bongo")

    @staticmethod
    def _normalize_url(url: str) -> str:
        """Strip protocol and trailing slash from URL."""
        url = url.replace("https://", "").replace("http://", "")
        return url.rstrip("/").lower()

    @staticmethod
    def _derive_identity_service_url(instance_url: str) -> str:
        """Derive the Identity Service URL from instance URL.

        Creatio Identity Service lives at {instance}-is.creatio.com.
        """
        normalized = instance_url.replace("https://", "").replace("http://", "").rstrip("/").lower()
        return normalized.replace(".creatio.com", "-is.creatio.com", 1)

    async def _get_access_token(self) -> str:
        """Exchange client credentials for an access token.

        Returns:
            Access token string
        """
        if self.access_token:
            return self.access_token

        url = f"https://{self.identity_service_url}/connect/token"

        async with httpx.AsyncClient() as client:
            response = await client.post(
                url,
                data={
                    "grant_type": "client_credentials",
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=30.0,
            )

            if response.status_code != 200:
                raise ValueError(
                    f"Failed to get Creatio access token: {response.status_code} - {response.text}"
                )

            data = response.json()
            self.access_token = data["access_token"]
            self.logger.info("Obtained Creatio access token via client credentials")
            return self.access_token

    def _build_odata_url(self, entity_name: str) -> str:
        """Build Creatio OData 4 URL for an entity collection."""
        return f"https://{self.instance_url}/0/odata/{entity_name}"

    async def _headers(self) -> Dict[str, str]:
        """Return headers for Creatio OData API requests."""
        token = await self._get_access_token()
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "ForceUseSession": "true",
        }

    async def _rate_limit(self):
        """Implement rate limiting for Creatio API."""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time

        if time_since_last < self.rate_limit_delay:
            sleep_time = self.rate_limit_delay - time_since_last
            await asyncio.sleep(sleep_time)

        self.last_request_time = time.time()

    # ==================== Public API ====================

    async def create_entities(self) -> List[Dict[str, Any]]:
        """Create ALL types of test entities in Creatio.

        Creates in dependency order:
        1. Accounts (standalone)
        2. Contacts (linked to Accounts)
        3. Campaigns (standalone)
        4. Opportunities (linked to Account + Contact)
        5. Orders (linked to Account + Contact)

        Returns:
            List of entity descriptors with verification tokens
        """
        self.logger.info(
            f"Creating {self.entity_count} of each entity type in Creatio"
        )
        all_entities: List[Dict[str, Any]] = []

        from monke.generation.creatio import (
            generate_creatio_account,
            generate_creatio_contact,
            generate_creatio_campaign,
            generate_creatio_opportunity,
            generate_creatio_order,
        )

        async with httpx.AsyncClient(timeout=30.0) as client:
            headers = await self._headers()

            # 1. Create Accounts
            self.logger.info(f"Creating {self.entity_count} accounts...")
            for i in range(self.entity_count):
                token = str(uuid.uuid4())[:8]
                account_data = await generate_creatio_account(self.openai_model, token)

                await self._rate_limit()
                account = await self._create_account(client, headers, account_data, token)

                if account:
                    account_desc = {
                        "type": "account",
                        "id": f"account_{account['Id']}",
                        "creatio_id": account["Id"],
                        "name": account_data["Name"],
                        "token": token,
                        "expected_content": token,
                    }
                    self._accounts.append(account_desc)
                    all_entities.append(account_desc)
                    self.logger.info(f"Created account: {account['Id']}")

            # 2. Create Contacts (linked to Accounts)
            self.logger.info(f"Creating {self.entity_count} contacts...")
            for i in range(self.entity_count):
                token = str(uuid.uuid4())[:8]
                contact_data = await generate_creatio_contact(self.openai_model, token)

                # Link to account in round-robin
                if self._accounts:
                    account = self._accounts[i % len(self._accounts)]
                    contact_data["AccountId"] = account["creatio_id"]

                await self._rate_limit()
                contact = await self._create_contact(client, headers, contact_data, token)

                if contact:
                    contact_desc = {
                        "type": "contact",
                        "id": f"contact_{contact['Id']}",
                        "creatio_id": contact["Id"],
                        "name": contact_data["Name"],
                        "token": token,
                        "expected_content": token,
                        "account_id": contact_data.get("AccountId"),
                    }
                    self._contacts.append(contact_desc)
                    all_entities.append(contact_desc)
                    self.logger.info(f"Created contact: {contact['Id']}")

            # 3. Create Campaigns (standalone)
            self.logger.info(f"Creating {self.entity_count} campaigns...")
            for i in range(self.entity_count):
                token = str(uuid.uuid4())[:8]
                campaign_data = await generate_creatio_campaign(self.openai_model, token)

                await self._rate_limit()
                campaign = await self._create_campaign(client, headers, campaign_data, token)

                if campaign:
                    campaign_desc = {
                        "type": "campaign",
                        "id": f"campaign_{campaign['Id']}",
                        "creatio_id": campaign["Id"],
                        "name": campaign_data["Name"],
                        "token": token,
                        "expected_content": token,
                    }
                    self._campaigns.append(campaign_desc)
                    all_entities.append(campaign_desc)
                    self.logger.info(f"Created campaign: {campaign['Id']}")

            # 5. Create Opportunities (linked to Account + Contact)
            self.logger.info(f"Creating {self.entity_count} opportunities...")
            for i in range(self.entity_count):
                token = str(uuid.uuid4())[:8]
                opp_data = await generate_creatio_opportunity(self.openai_model, token)

                # Link to account and contact in round-robin
                if self._accounts:
                    opp_data["AccountId"] = self._accounts[i % len(self._accounts)]["creatio_id"]
                if self._contacts:
                    opp_data["ContactId"] = self._contacts[i % len(self._contacts)]["creatio_id"]

                await self._rate_limit()
                opportunity = await self._create_opportunity(client, headers, opp_data, token)

                if opportunity:
                    opp_desc = {
                        "type": "opportunity",
                        "id": f"opportunity_{opportunity['Id']}",
                        "creatio_id": opportunity["Id"],
                        "name": opp_data["Title"],
                        "token": token,
                        "expected_content": token,
                        "account_id": opp_data.get("AccountId"),
                    }
                    self._opportunities.append(opp_desc)
                    all_entities.append(opp_desc)
                    self.logger.info(f"Created opportunity: {opportunity['Id']}")

            # 6. Create Orders (linked to Account + Contact)
            self.logger.info(f"Creating {self.entity_count} orders...")
            for i in range(self.entity_count):
                token = str(uuid.uuid4())[:8]
                order_data = await generate_creatio_order(self.openai_model, token)

                # Link to account and contact in round-robin
                if self._accounts:
                    order_data["AccountId"] = self._accounts[i % len(self._accounts)]["creatio_id"]
                if self._contacts:
                    order_data["ContactId"] = self._contacts[i % len(self._contacts)]["creatio_id"]

                await self._rate_limit()
                order = await self._create_order(client, headers, order_data, token)

                if order:
                    order_desc = {
                        "type": "order",
                        "id": f"order_{order['Id']}",
                        "creatio_id": order["Id"],
                        "name": order_data.get("Number", f"Order {order['Id']}"),
                        "token": token,
                        "expected_content": token,
                        "account_id": order_data.get("AccountId"),
                    }
                    self._orders.append(order_desc)
                    all_entities.append(order_desc)
                    self.logger.info(f"Created order: {order['Id']}")

        self.logger.info(
            f"Created {len(self._accounts)} accounts, "
            f"{len(self._contacts)} contacts, "
            f"{len(self._campaigns)} campaigns, "
            f"{len(self._opportunities)} opportunities, "
            f"{len(self._orders)} orders"
        )

        self.created_entities = all_entities
        return all_entities

    async def update_entities(self) -> List[Dict[str, Any]]:
        """Update a subset of entities to test incremental sync.

        Updates first 2 Contacts (PATCH JobTitle) and first 2 Accounts (PATCH Name).
        """
        self.logger.info("Updating test entities in Creatio")
        updated_entities: List[Dict[str, Any]] = []

        from monke.generation.creatio import (
            generate_creatio_account,
            generate_creatio_contact,
        )

        async with httpx.AsyncClient(timeout=30.0) as client:
            headers = await self._headers()

            # Update first 2 contacts
            contacts_to_update = min(2, len(self._contacts))
            for i in range(contacts_to_update):
                contact = self._contacts[i]
                token = contact["token"]

                contact_data = await generate_creatio_contact(
                    self.openai_model, token, is_update=True
                )

                await self._rate_limit()
                updated = await self._update_contact(
                    client, headers, contact["creatio_id"], contact_data
                )

                if updated:
                    updated_entities.append({
                        **contact,
                        "updated": True,
                    })
                    self.logger.info(f"Updated contact: {contact['creatio_id']}")

            # Update first 2 accounts
            accounts_to_update = min(2, len(self._accounts))
            for i in range(accounts_to_update):
                account = self._accounts[i]
                token = account["token"]

                account_data = await generate_creatio_account(
                    self.openai_model, token, is_update=True
                )

                await self._rate_limit()
                updated = await self._update_account(
                    client, headers, account["creatio_id"], account_data
                )

                if updated:
                    updated_entities.append({
                        **account,
                        "name": account_data["Name"],
                        "updated": True,
                    })
                    self.logger.info(f"Updated account: {account['creatio_id']}")

        self.logger.info(f"Updated {len(updated_entities)} entities")
        return updated_entities

    async def delete_entities(self) -> List[str]:
        """Delete ALL test entities from Creatio.

        Deletes in reverse dependency order:
        Order -> Opportunity -> Campaign -> Contact -> Account
        """
        self.logger.info("Deleting ALL test entities from Creatio")
        deleted_ids: List[str] = []

        async with httpx.AsyncClient(timeout=30.0) as client:
            headers = await self._headers()

            # 1. Delete orders
            for order in self._orders:
                try:
                    await self._rate_limit()
                    await self._delete_entity(client, headers, "Order", order["creatio_id"])
                    deleted_ids.append(order["id"])
                    self.logger.info(f"Deleted order: {order['creatio_id']}")
                except Exception as e:
                    self.logger.warning(f"Could not delete order {order['id']}: {e}")

            # 2. Delete opportunities
            for opp in self._opportunities:
                try:
                    await self._rate_limit()
                    await self._delete_entity(client, headers, "Opportunity", opp["creatio_id"])
                    deleted_ids.append(opp["id"])
                    self.logger.info(f"Deleted opportunity: {opp['creatio_id']}")
                except Exception as e:
                    self.logger.warning(f"Could not delete opportunity {opp['id']}: {e}")

            # 3. Delete campaigns
            for campaign in self._campaigns:
                try:
                    await self._rate_limit()
                    await self._delete_entity(client, headers, "Campaign", campaign["creatio_id"])
                    deleted_ids.append(campaign["id"])
                    self.logger.info(f"Deleted campaign: {campaign['creatio_id']}")
                except Exception as e:
                    self.logger.warning(f"Could not delete campaign {campaign['id']}: {e}")

            # 5. Delete contacts
            for contact in self._contacts:
                try:
                    await self._rate_limit()
                    await self._delete_entity(client, headers, "Contact", contact["creatio_id"])
                    deleted_ids.append(contact["id"])
                    self.logger.info(f"Deleted contact: {contact['creatio_id']}")
                except Exception as e:
                    self.logger.warning(f"Could not delete contact {contact['id']}: {e}")

            # 6. Delete accounts
            for account in self._accounts:
                try:
                    await self._rate_limit()
                    await self._delete_entity(client, headers, "Account", account["creatio_id"])
                    deleted_ids.append(account["id"])
                    self.logger.info(f"Deleted account: {account['creatio_id']}")
                except Exception as e:
                    self.logger.warning(f"Could not delete account {account['id']}: {e}")

        # Clear tracking
        self._orders = []
        self._opportunities = []
        self._campaigns = []
        self._contacts = []
        self._accounts = []

        self.logger.info(f"Deleted {len(deleted_ids)} entities")
        return deleted_ids

    async def delete_specific_entities(
        self, entities: List[Dict[str, Any]]
    ) -> List[str]:
        """Delete specific entities from Creatio."""
        self.logger.info(f"Deleting {len(entities)} specific entities from Creatio")
        deleted_ids: List[str] = []

        # Categorize by type for proper deletion order
        orders = [e for e in entities if e.get("type") == "order"]
        opportunities = [e for e in entities if e.get("type") == "opportunity"]
        campaigns = [e for e in entities if e.get("type") == "campaign"]
        contacts = [e for e in entities if e.get("type") == "contact"]
        accounts = [e for e in entities if e.get("type") == "account"]

        # Map type to OData entity name
        type_to_odata = {
            "order": "Order",
            "opportunity": "Opportunity",
            "campaign": "Campaign",
            "contact": "Contact",
            "account": "Account",
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            headers = await self._headers()

            # For each account being deleted, cascade-delete tracked dependents
            # (orders, opportunities, contacts) that reference it first.
            account_ids_to_delete = {a["creatio_id"] for a in accounts}
            if account_ids_to_delete:
                for dep_list, dep_attr, odata_name in [
                    (self._orders, "_orders", "Order"),
                    (self._opportunities, "_opportunities", "Opportunity"),
                    (self._contacts, "_contacts", "Contact"),
                ]:
                    dependents = [
                        e for e in dep_list
                        if e.get("account_id") in account_ids_to_delete
                    ]
                    for dep in dependents:
                        try:
                            await self._rate_limit()
                            await self._delete_entity(
                                client, headers, odata_name, dep["creatio_id"]
                            )
                            deleted_ids.append(dep["id"])
                            self.logger.info(
                                f"Cascade-deleted {dep['type']}: {dep['creatio_id']}"
                            )
                        except Exception as e:
                            self.logger.warning(
                                f"Could not cascade-delete {dep['type']} {dep['id']}: {e}"
                            )
                    # Remove cascade-deleted entities from tracking
                    dep_ids = {d["id"] for d in dependents}
                    setattr(
                        self, dep_attr,
                        [e for e in getattr(self, dep_attr) if e["id"] not in dep_ids],
                    )

            # Delete in reverse dependency order
            for group, group_name in [
                (orders, "order"),
                (opportunities, "opportunity"),
                (campaigns, "campaign"),
                (contacts, "contact"),
                (accounts, "account"),
            ]:
                for entity in group:
                    # Skip if already cascade-deleted above
                    if entity["id"] in deleted_ids:
                        continue
                    try:
                        await self._rate_limit()
                        await self._delete_entity(
                            client, headers, type_to_odata[group_name], entity["creatio_id"]
                        )
                        deleted_ids.append(entity["id"])

                        # Remove from tracking
                        # Fix pluralization issue for opportunity
                        attr = f"_{group_name}s".replace("opportunitys", "opportunities")
                        tracking = getattr(self, attr)
                        setattr(
                            self,
                            f"_{group_name}s",
                            [e for e in tracking if e["id"] != entity["id"]],
                        )
                        self.logger.info(
                            f"Deleted {group_name}: {entity['creatio_id']}"
                        )
                    except Exception as e:
                        self.logger.warning(
                            f"Could not delete {group_name} {entity['id']}: {e}"
                        )

        return deleted_ids

    async def cleanup(self):
        """Clean up any remaining test data."""
        self.logger.info("Cleaning up remaining test entities in Creatio")

        async with httpx.AsyncClient(timeout=30.0) as client:
            headers = await self._headers()

            # Delete in reverse dependency order, swallowing all exceptions
            for entity_list, odata_name in [
                (self._orders, "Order"),
                (self._opportunities, "Opportunity"),
                (self._campaigns, "Campaign"),
                (self._contacts, "Contact"),
                (self._accounts, "Account"),
            ]:
                for entity in entity_list:
                    try:
                        await self._rate_limit()
                        await self._delete_entity(client, headers, odata_name, entity["creatio_id"])
                    except Exception:
                        pass

        self._orders = []
        self._opportunities = []
        self._campaigns = []
        self._contacts = []
        self._accounts = []
        self.logger.info("Cleanup completed")

    # ==================== Private API Helpers ====================

    async def _create_account(
        self,
        client: httpx.AsyncClient,
        headers: Dict[str, str],
        account_data: Dict[str, Any],
        token: str,
    ) -> Optional[Dict[str, Any]]:
        """Create an account via Creatio OData API."""
        name = account_data.get("Name", "Test Account")
        if token not in name:
            name = f"{name} [{token}]"

        payload = {
            "Name": name,
            "Phone": account_data.get("Phone", ""),
            "Web": account_data.get("Web", ""),
            "Address": account_data.get("Address", ""),
        }

        response = await client.post(
            self._build_odata_url("Account"),
            headers=headers,
            json=payload,
        )

        if response.status_code in (200, 201):
            return response.json()
        else:
            self.logger.error(f"Failed to create account: {response.status_code} - {response.text}")
            return None

    async def _create_contact(
        self,
        client: httpx.AsyncClient,
        headers: Dict[str, str],
        contact_data: Dict[str, Any],
        token: str,
    ) -> Optional[Dict[str, Any]]:
        """Create a contact via Creatio OData API."""
        job_title = contact_data.get("JobTitle", "")
        if token not in job_title:
            job_title = f"{job_title} [{token}]"

        payload: Dict[str, Any] = {
            "Name": contact_data.get("Name", "Test Contact"),
            "Email": contact_data.get("Email", ""),
            "Phone": contact_data.get("Phone", ""),
            "JobTitle": job_title,
        }

        if "AccountId" in contact_data:
            payload["AccountId"] = contact_data["AccountId"]

        response = await client.post(
            self._build_odata_url("Contact"),
            headers=headers,
            json=payload,
        )

        if response.status_code in (200, 201):
            return response.json()
        else:
            self.logger.error(f"Failed to create contact: {response.status_code} - {response.text}")
            return None

    async def _create_campaign(
        self,
        client: httpx.AsyncClient,
        headers: Dict[str, str],
        campaign_data: Dict[str, Any],
        token: str,
    ) -> Optional[Dict[str, Any]]:
        """Create a campaign via Creatio OData API."""
        name = campaign_data.get("Name", "Test Campaign")
        if token not in name:
            name = f"{name} [{token}]"

        payload = {
            "Name": name,
            "TargetDescription": campaign_data.get("TargetDescription", ""),
            "StartDate": campaign_data.get("StartDate", "2025-01-01T00:00:00Z"),
            "EndDate": campaign_data.get("EndDate", "2025-12-31T23:59:59Z"),
        }

        response = await client.post(
            self._build_odata_url("Campaign"),
            headers=headers,
            json=payload,
        )

        if response.status_code in (200, 201):
            return response.json()
        else:
            self.logger.error(f"Failed to create campaign: {response.status_code} - {response.text}")
            return None

    async def _create_opportunity(
        self,
        client: httpx.AsyncClient,
        headers: Dict[str, str],
        opp_data: Dict[str, Any],
        token: str,
    ) -> Optional[Dict[str, Any]]:
        """Create an opportunity via Creatio OData API."""
        title = opp_data.get("Title", "Test Opportunity")
        if token not in title:
            title = f"{title} [{token}]"

        payload: Dict[str, Any] = {
            "Title": title,
            "Description": opp_data.get("Description", ""),
            "Budget": opp_data.get("Budget", 0),
            "Amount": opp_data.get("Amount", 0),
        }

        if "AccountId" in opp_data:
            payload["AccountId"] = opp_data["AccountId"]
        if "ContactId" in opp_data:
            payload["ContactId"] = opp_data["ContactId"]

        response = await client.post(
            self._build_odata_url("Opportunity"),
            headers=headers,
            json=payload,
        )

        if response.status_code in (200, 201):
            return response.json()
        else:
            self.logger.error(f"Failed to create opportunity: {response.status_code} - {response.text}")
            return None

    async def _create_order(
        self,
        client: httpx.AsyncClient,
        headers: Dict[str, str],
        order_data: Dict[str, Any],
        token: str,
    ) -> Optional[Dict[str, Any]]:
        """Create an order via Creatio OData API."""
        notes = order_data.get("Notes", "")
        if token not in notes:
            notes = f"{notes} (Order Token: {token})"

        payload: Dict[str, Any] = {
            "Number": f"MONKE-{token}",
            "Notes": notes,
            "Comment": order_data.get("Comment", ""),
            "ReceiverName": order_data.get("ReceiverName", ""),
            "DeliveryAddress": order_data.get("DeliveryAddress", ""),
            "Amount": order_data.get("Amount", 0),
        }

        if "AccountId" in order_data:
            payload["AccountId"] = order_data["AccountId"]
        if "ContactId" in order_data:
            payload["ContactId"] = order_data["ContactId"]

        response = await client.post(
            self._build_odata_url("Order"),
            headers=headers,
            json=payload,
        )

        if response.status_code in (200, 201):
            return response.json()
        else:
            self.logger.error(f"Failed to create order: {response.status_code} - {response.text}")
            return None

    async def _update_contact(
        self,
        client: httpx.AsyncClient,
        headers: Dict[str, str],
        contact_id: str,
        contact_data: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """Update a contact via Creatio OData PATCH."""
        payload = {
            "JobTitle": contact_data.get("JobTitle", "Updated Title"),
        }

        response = await client.patch(
            f"{self._build_odata_url('Contact')}({contact_id})",
            headers=headers,
            json=payload,
        )

        if response.status_code in (200, 204):
            return payload
        else:
            self.logger.error(f"Failed to update contact: {response.status_code} - {response.text}")
            return None

    async def _update_account(
        self,
        client: httpx.AsyncClient,
        headers: Dict[str, str],
        account_id: str,
        account_data: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """Update an account via Creatio OData PATCH."""
        payload = {
            "Name": account_data.get("Name", "Updated Account"),
        }

        response = await client.patch(
            f"{self._build_odata_url('Account')}({account_id})",
            headers=headers,
            json=payload,
        )

        if response.status_code in (200, 204):
            return payload
        else:
            self.logger.error(f"Failed to update account: {response.status_code} - {response.text}")
            return None

    async def _delete_entity(
        self,
        client: httpx.AsyncClient,
        headers: Dict[str, str],
        entity_name: str,
        entity_id: str,
    ):
        """Delete an entity via Creatio OData DELETE.

        DELETE /0/odata/{EntityName}({guid})
        """
        response = await client.delete(
            f"{self._build_odata_url(entity_name)}({entity_id})",
            headers=headers,
        )
        if response.status_code not in (200, 204):
            raise Exception(
                f"Failed to delete {entity_name} {entity_id}: "
                f"{response.status_code} - {response.text}"
            )
