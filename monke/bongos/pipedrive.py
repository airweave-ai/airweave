"""Pipedrive bongo - creates, updates, and deletes test data in Pipedrive."""

import asyncio
import time
import uuid
from typing import Any, Dict, List, Optional

import httpx

from monke.bongos.base_bongo import BaseBongo
from monke.generation.pipedrive import (
    generate_pipedrive_activity,
    generate_pipedrive_deal,
    generate_pipedrive_lead,
    generate_pipedrive_note,
    generate_pipedrive_organization,
    generate_pipedrive_person,
    generate_pipedrive_product,
)
from monke.utils.logging import get_logger

PIPEDRIVE_API = "https://api.pipedrive.com/v1"


class PipedriveBongo(BaseBongo):
    """Creates/updates/deletes Pipedrive entities using API token.

    Supports: Organizations, Persons, Deals, Activities, Products, Leads, Notes
    """

    connector_type = "pipedrive"

    def __init__(self, credentials: Dict[str, Any], **kwargs):
        super().__init__(credentials)
        self.api_token: str = credentials["api_token"]
        self.entity_count: int = int(kwargs.get("entity_count", 3))
        self.openai_model: str = kwargs.get("openai_model", "gpt-4.1-mini")
        self.rate_limit_delay = float(kwargs.get("rate_limit_delay_ms", 500)) / 1000.0
        self.logger = get_logger("pipedrive_bongo")

        # Track entities by type for proper cleanup and management
        self._organizations: List[Dict[str, Any]] = []
        self._persons: List[Dict[str, Any]] = []
        self._deals: List[Dict[str, Any]] = []
        self._activities: List[Dict[str, Any]] = []
        self._products: List[Dict[str, Any]] = []
        self._leads: List[Dict[str, Any]] = []
        self._notes: List[Dict[str, Any]] = []

        # Cache for pipeline ID (needed for deals)
        self._pipeline_id: Optional[int] = None
        self._stage_id: Optional[int] = None

        self._last_req = 0.0

    @property
    def _auth_params(self) -> dict[str, str]:
        return {"api_token": self.api_token}

    async def _pace(self):
        """Rate limiting helper."""
        now = time.time()
        if (delta := now - self._last_req) < self.rate_limit_delay:
            await asyncio.sleep(self.rate_limit_delay - delta)
        self._last_req = time.time()

    async def _get_pipeline(self, client: httpx.AsyncClient) -> tuple[int, int]:
        """Get the first pipeline and stage for creating deals."""
        if self._pipeline_id and self._stage_id:
            return self._pipeline_id, self._stage_id

        await self._pace()
        r = await client.get(
            f"{PIPEDRIVE_API}/pipelines", params=self._auth_params
        )
        r.raise_for_status()

        data = r.json()
        if data.get("success") and data.get("data"):
            pipeline = data["data"][0]
            self._pipeline_id = pipeline["id"]

            # Get stages for this pipeline
            await self._pace()
            stages_r = await client.get(
                f"{PIPEDRIVE_API}/stages",
                params={**self._auth_params, "pipeline_id": self._pipeline_id},
            )
            stages_r.raise_for_status()
            stages_data = stages_r.json()

            if stages_data.get("success") and stages_data.get("data"):
                self._stage_id = stages_data["data"][0]["id"]

        if not self._pipeline_id or not self._stage_id:
            raise RuntimeError("No pipeline/stage found in Pipedrive")

        return self._pipeline_id, self._stage_id

    async def create_entities(self) -> List[Dict[str, Any]]:
        """Create test entities in Pipedrive across all entity types."""
        self.logger.info(
            f"🥁 Creating {self.entity_count} entities for each type in Pipedrive"
        )
        all_entities: List[Dict[str, Any]] = []

        async with httpx.AsyncClient(timeout=30) as client:
            # Get pipeline/stage for deals
            await self._get_pipeline(client)

            # Create organizations first (needed for linking)
            orgs = await self._create_organizations(client)
            all_entities.extend(orgs)

            # Create persons (can be linked to orgs)
            persons = await self._create_persons(client)
            all_entities.extend(persons)

            # Create deals (need pipeline, can link to person/org)
            deals = await self._create_deals(client)
            all_entities.extend(deals)

            # Create activities (can link to deals/persons/orgs)
            activities = await self._create_activities(client)
            all_entities.extend(activities)

            # Create products (standalone)
            products = await self._create_products(client)
            all_entities.extend(products)

            # Create leads (standalone)
            leads = await self._create_leads(client)
            all_entities.extend(leads)

            # Create notes (linked to persons)
            notes = await self._create_notes(client)
            all_entities.extend(notes)

        self.logger.info(f"✅ Created {len(all_entities)} Pipedrive entities total")

        # IMPORTANT: Reorder entities for partial_delete compatibility
        # Pipedrive doesn't allow deleting entities that have linked children
        # (e.g., can't delete an org if deals are linked to it)
        # Put "leaf" entities first so partial_delete can safely delete them
        # Order: notes, products, activities, leads, deals, persons, organizations
        deletion_safe_order = notes + products + activities + leads + deals + persons + orgs
        return deletion_safe_order

    async def _create_organizations(
        self, client: httpx.AsyncClient
    ) -> List[Dict[str, Any]]:
        """Create organization entities."""
        self.logger.info(f"🏢 Creating {self.entity_count} organizations")
        entities: List[Dict[str, Any]] = []

        tokens = [str(uuid.uuid4())[:8] for _ in range(self.entity_count)]

        # Generate all content in parallel
        gen_results = await asyncio.gather(
            *[generate_pipedrive_organization(self.openai_model, t) for t in tokens]
        )

        for token, org in zip(tokens, gen_results):
            await self._pace()

            payload = {"name": org.name}
            if org.address:
                payload["address"] = org.address

            r = await client.post(
                f"{PIPEDRIVE_API}/organizations",
                json=payload,
                params=self._auth_params,
            )

            if r.status_code not in (200, 201):
                self.logger.error(f"Organization create failed {r.status_code}: {r.text}")
                continue

            data = r.json()
            if not data.get("success"):
                self.logger.error(f"Organization API error: {data}")
                continue

            org_data = data.get("data", {})
            org_id = org_data.get("id")

            ent = {
                "type": "organization",
                "id": f"organization_{org_id}",
                "pipedrive_id": org_id,  # Raw ID for API calls
                "name": org.name,
                "token": token,
                "expected_content": token,
                "path": f"pipedrive/organization/organization_{org_id}",
            }
            entities.append(ent)
            self._organizations.append(ent)
            self.created_entities.append({"id": f"organization_{org_id}", "name": org.name})

        self.logger.info(f"✅ Created {len(entities)} organizations")
        return entities

    async def _create_persons(self, client: httpx.AsyncClient) -> List[Dict[str, Any]]:
        """Create person entities."""
        self.logger.info(f"👤 Creating {self.entity_count} persons")
        entities: List[Dict[str, Any]] = []

        tokens = [str(uuid.uuid4())[:8] for _ in range(self.entity_count)]

        gen_results = await asyncio.gather(
            *[generate_pipedrive_person(self.openai_model, t) for t in tokens]
        )

        for i, (token, person) in enumerate(zip(tokens, gen_results)):
            await self._pace()

            name_with_token = f"{person.name} [{token}]"
            payload = {
                "name": name_with_token,
                "email": [{"value": person.email, "primary": True, "label": "work"}],
            }
            if person.phone:
                payload["phone"] = [{"value": person.phone, "primary": True, "label": "work"}]

            # Link to organization if we have one
            if self._organizations and i < len(self._organizations):
                payload["org_id"] = self._organizations[i]["pipedrive_id"]

            r = await client.post(
                f"{PIPEDRIVE_API}/persons",
                json=payload,
                params=self._auth_params,
            )

            if r.status_code not in (200, 201):
                self.logger.error(f"Person create failed {r.status_code}: {r.text}")
                continue

            data = r.json()
            if not data.get("success"):
                self.logger.error(f"Person API error: {data}")
                continue

            person_data = data.get("data", {})
            person_id = person_data.get("id")

            ent = {
                "type": "person",
                "id": f"person_{person_id}",
                "pipedrive_id": person_id,  # Raw ID for API calls
                "name": person.name,
                "token": token,
                "expected_content": token,
                "path": f"pipedrive/person/person_{person_id}",
            }
            entities.append(ent)
            self._persons.append(ent)
            self.created_entities.append({"id": f"person_{person_id}", "name": person.name})

        self.logger.info(f"✅ Created {len(entities)} persons")
        return entities

    async def _create_deals(self, client: httpx.AsyncClient) -> List[Dict[str, Any]]:
        """Create deal entities."""
        self.logger.info(f"💰 Creating {self.entity_count} deals")
        entities: List[Dict[str, Any]] = []

        tokens = [str(uuid.uuid4())[:8] for _ in range(self.entity_count)]

        gen_results = await asyncio.gather(
            *[generate_pipedrive_deal(self.openai_model, t) for t in tokens]
        )

        for i, (token, deal) in enumerate(zip(tokens, gen_results)):
            await self._pace()

            # Explicitly ensure token is in title (generator may not always append it)
            title_with_token = (
                deal.title if f"[{token}]" in deal.title else f"{deal.title} [{token}]"
            )

            # Log the title being created for debugging
            self.logger.info(f"📝 Creating deal {i+1}/{len(tokens)} with title: {title_with_token}")

            payload = {
                "title": title_with_token,
                "pipeline_id": self._pipeline_id,
                "stage_id": self._stage_id,
            }
            if deal.value:
                payload["value"] = deal.value
                payload["currency"] = deal.currency

            # Link to person and org if available
            if self._persons and i < len(self._persons):
                payload["person_id"] = self._persons[i]["pipedrive_id"]
            if self._organizations and i < len(self._organizations):
                payload["org_id"] = self._organizations[i]["pipedrive_id"]

            r = await client.post(
                f"{PIPEDRIVE_API}/deals",
                json=payload,
                params=self._auth_params,
            )

            if r.status_code not in (200, 201):
                self.logger.error(f"Deal create failed {r.status_code}: {r.text}")
                continue

            data = r.json()
            if not data.get("success"):
                self.logger.error(f"Deal API error: {data}")
                continue

            deal_data = data.get("data", {})
            deal_id = deal_data.get("id")
            returned_title = deal_data.get("title", "")

            # Verify the title was stored correctly in Pipedrive
            if token not in returned_title:
                self.logger.warning(
                    f"⚠️ Deal {deal_id} title mismatch! "
                    f"Sent: {title_with_token}, Received: {returned_title}"
                )
            else:
                self.logger.info(f"✅ Deal {deal_id} created with title: {returned_title}")

            ent = {
                "type": "deal",
                "id": f"deal_{deal_id}",
                "pipedrive_id": deal_id,  # Raw ID for API calls
                "name": title_with_token,
                "token": token,
                "expected_content": token,
                "path": f"pipedrive/deal/deal_{deal_id}",
            }
            entities.append(ent)
            self._deals.append(ent)
            self.created_entities.append({"id": f"deal_{deal_id}", "name": title_with_token})

        self.logger.info(f"✅ Created {len(entities)} deals")
        return entities

    async def _create_activities(
        self, client: httpx.AsyncClient
    ) -> List[Dict[str, Any]]:
        """Create activity entities."""
        self.logger.info(f"📅 Creating {self.entity_count} activities")
        entities: List[Dict[str, Any]] = []

        tokens = [str(uuid.uuid4())[:8] for _ in range(self.entity_count)]

        gen_results = await asyncio.gather(
            *[generate_pipedrive_activity(self.openai_model, t) for t in tokens]
        )

        for i, (token, activity) in enumerate(zip(tokens, gen_results)):
            await self._pace()

            # Explicitly ensure token is in subject (generator may not always append it)
            subject_with_token = (
                activity.subject
                if f"[{token}]" in activity.subject
                else f"{activity.subject} [{token}]"
            )

            # Log the subject being created for debugging
            self.logger.info(
                f"📝 Creating activity {i+1}/{len(tokens)} with subject: {subject_with_token}"
            )

            payload = {
                "subject": subject_with_token,
                "type": activity.activity_type,
            }
            if activity.note:
                payload["note"] = activity.note
            if activity.due_date:
                payload["due_date"] = activity.due_date
            if activity.due_time:
                payload["due_time"] = activity.due_time
            if activity.duration:
                payload["duration"] = activity.duration

            # Link to deal, person, org if available
            if self._deals and i < len(self._deals):
                payload["deal_id"] = self._deals[i]["pipedrive_id"]
            if self._persons and i < len(self._persons):
                payload["person_id"] = self._persons[i]["pipedrive_id"]
            if self._organizations and i < len(self._organizations):
                payload["org_id"] = self._organizations[i]["pipedrive_id"]

            r = await client.post(
                f"{PIPEDRIVE_API}/activities",
                json=payload,
                params=self._auth_params,
            )

            if r.status_code not in (200, 201):
                self.logger.error(f"Activity create failed {r.status_code}: {r.text}")
                continue

            data = r.json()
            if not data.get("success"):
                self.logger.error(f"Activity API error: {data}")
                continue

            activity_data = data.get("data", {})
            activity_id = activity_data.get("id")
            returned_subject = activity_data.get("subject", "")

            # Verify the subject was stored correctly in Pipedrive
            if token not in returned_subject:
                self.logger.warning(
                    f"⚠️ Activity {activity_id} subject mismatch! "
                    f"Sent: {subject_with_token}, Received: {returned_subject}"
                )
            else:
                self.logger.info(f"✅ Activity {activity_id} created with subject: {returned_subject}")

            ent = {
                "type": "activity",
                "id": f"activity_{activity_id}",
                "pipedrive_id": activity_id,  # Raw ID for API calls
                "name": subject_with_token,
                "token": token,
                "expected_content": token,
                "path": f"pipedrive/activity/activity_{activity_id}",
            }
            entities.append(ent)
            self._activities.append(ent)
            self.created_entities.append({"id": f"activity_{activity_id}", "name": subject_with_token})

        self.logger.info(f"✅ Created {len(entities)} activities")
        return entities

    async def _create_products(self, client: httpx.AsyncClient) -> List[Dict[str, Any]]:
        """Create product entities."""
        self.logger.info(f"📦 Creating {self.entity_count} products")
        entities: List[Dict[str, Any]] = []

        tokens = [str(uuid.uuid4())[:8] for _ in range(self.entity_count)]

        gen_results = await asyncio.gather(
            *[generate_pipedrive_product(self.openai_model, t) for t in tokens]
        )

        for token, product in zip(tokens, gen_results):
            await self._pace()

            payload = {"name": product.name}
            if product.code:
                payload["code"] = product.code
            if product.description:
                payload["description"] = product.description
            if product.unit:
                payload["unit"] = product.unit
            if product.price:
                payload["prices"] = [
                    {
                        "price": product.price,
                        "currency": product.currency,
                        "cost": 0,
                        "overhead_cost": 0,
                    }
                ]

            r = await client.post(
                f"{PIPEDRIVE_API}/products",
                json=payload,
                params=self._auth_params,
            )

            if r.status_code not in (200, 201):
                self.logger.error(f"Product create failed {r.status_code}: {r.text}")
                continue

            data = r.json()
            if not data.get("success"):
                self.logger.error(f"Product API error: {data}")
                continue

            product_data = data.get("data", {})
            product_id = product_data.get("id")

            ent = {
                "type": "product",
                "id": f"product_{product_id}",
                "pipedrive_id": product_id,  # Raw ID for API calls
                "name": product.name,
                "token": token,
                "expected_content": token,
                "path": f"pipedrive/product/product_{product_id}",
            }
            entities.append(ent)
            self._products.append(ent)
            self.created_entities.append({"id": f"product_{product_id}", "name": product.name})

        self.logger.info(f"✅ Created {len(entities)} products")
        return entities

    async def _create_leads(self, client: httpx.AsyncClient) -> List[Dict[str, Any]]:
        """Create lead entities (must be linked to a person or organization)."""
        self.logger.info(f"🎯 Creating {self.entity_count} leads")
        entities: List[Dict[str, Any]] = []

        # Leads require a person_id or organization_id
        if not self._persons and not self._organizations:
            self.logger.warning(
                "No persons or organizations available to link leads to, skipping leads"
            )
            return entities

        tokens = [str(uuid.uuid4())[:8] for _ in range(self.entity_count)]

        gen_results = await asyncio.gather(
            *[generate_pipedrive_lead(self.openai_model, t) for t in tokens]
        )

        for i, (token, lead) in enumerate(zip(tokens, gen_results)):
            await self._pace()

            payload = {"title": lead.title}
            if lead.value:
                payload["value"] = {"amount": lead.value, "currency": lead.currency}

            # Link to person or organization (required by Pipedrive API)
            if self._persons and i < len(self._persons):
                payload["person_id"] = self._persons[i]["pipedrive_id"]
            elif self._organizations and i < len(self._organizations):
                payload["organization_id"] = self._organizations[i]["pipedrive_id"]
            elif self._persons:
                payload["person_id"] = self._persons[i % len(self._persons)]["pipedrive_id"]
            else:
                payload["organization_id"] = self._organizations[i % len(self._organizations)]["pipedrive_id"]

            r = await client.post(
                f"{PIPEDRIVE_API}/leads",
                json=payload,
                params=self._auth_params,
            )

            if r.status_code not in (200, 201):
                self.logger.error(f"Lead create failed {r.status_code}: {r.text}")
                continue

            data = r.json()
            if not data.get("success"):
                self.logger.error(f"Lead API error: {data}")
                continue

            lead_data = data.get("data", {})
            lead_id = lead_data.get("id")

            ent = {
                "type": "lead",
                "id": f"lead_{lead_id}",
                "pipedrive_id": lead_id,  # Raw ID for API calls
                "name": lead.title,
                "token": token,
                "expected_content": token,
                "path": f"pipedrive/lead/lead_{lead_id}",
            }
            entities.append(ent)
            self._leads.append(ent)
            self.created_entities.append({"id": f"lead_{lead_id}", "name": lead.title})

        self.logger.info(f"✅ Created {len(entities)} leads")
        return entities

    async def _create_notes(self, client: httpx.AsyncClient) -> List[Dict[str, Any]]:
        """Create note entities (linked to persons)."""
        self.logger.info(f"📝 Creating {self.entity_count} notes")
        entities: List[Dict[str, Any]] = []

        # Notes must be linked to something - use persons
        if not self._persons:
            self.logger.warning("No persons available to link notes to, skipping notes")
            return entities

        tokens = [str(uuid.uuid4())[:8] for _ in range(self.entity_count)]

        gen_results = await asyncio.gather(
            *[generate_pipedrive_note(self.openai_model, t) for t in tokens]
        )

        for i, (token, note) in enumerate(zip(tokens, gen_results)):
            await self._pace()

            # Link to a person (cycle through available persons)
            person_idx = i % len(self._persons)
            person_id = self._persons[person_idx]["pipedrive_id"]

            payload = {
                "content": note.content,
                "person_id": person_id,
            }

            r = await client.post(
                f"{PIPEDRIVE_API}/notes",
                json=payload,
                params=self._auth_params,
            )

            if r.status_code not in (200, 201):
                self.logger.error(f"Note create failed {r.status_code}: {r.text}")
                continue

            data = r.json()
            if not data.get("success"):
                self.logger.error(f"Note API error: {data}")
                continue

            note_data = data.get("data", {})
            note_id = note_data.get("id")

            ent = {
                "type": "note",
                "id": f"note_{note_id}",
                "pipedrive_id": note_id,  # Raw ID for API calls
                "name": f"Note {note_id}",
                "token": token,
                "expected_content": token,
                "path": f"pipedrive/note/note_{note_id}",
                "person_id": person_id,
            }
            entities.append(ent)
            self._notes.append(ent)
            self.created_entities.append({"id": f"note_{note_id}", "name": f"Note {note_id}"})

        self.logger.info(f"✅ Created {len(entities)} notes")
        return entities

    async def update_entities(self) -> List[Dict[str, Any]]:
        """Update some test entities in Pipedrive."""
        self.logger.info("🥁 Updating some Pipedrive entities")
        updated: List[Dict[str, Any]] = []

        async with httpx.AsyncClient(timeout=30) as client:
            # Update a few of each type
            updated.extend(await self._update_type(client, self._persons, "persons"))
            updated.extend(
                await self._update_type(client, self._organizations, "organizations")
            )
            updated.extend(await self._update_type(client, self._deals, "deals"))
            updated.extend(
                await self._update_type(client, self._activities, "activities")
            )
            updated.extend(await self._update_type(client, self._products, "products"))
            updated.extend(await self._update_type(client, self._leads, "leads"))
            updated.extend(await self._update_type(client, self._notes, "notes"))

        self.logger.info(f"✅ Updated {len(updated)} Pipedrive entities")
        return updated

    async def _update_type(
        self,
        client: httpx.AsyncClient,
        entities: List[Dict[str, Any]],
        endpoint: str,
    ) -> List[Dict[str, Any]]:
        """Update entities of a specific type."""
        if not entities:
            return []

        updated: List[Dict[str, Any]] = []
        # Update first entity of each type
        for ent in entities[:1]:
            await self._pace()

            token = ent.get("token", "")
            # Use pipedrive_id (raw numeric ID) for API calls
            pipedrive_id = ent.get("pipedrive_id", ent["id"])

            # Build update payload based on type
            if endpoint == "persons":
                payload = {"name": f"Updated Person [{token}]"}
            elif endpoint == "organizations":
                payload = {"name": f"Updated Organization [{token}]"}
            elif endpoint == "deals":
                payload = {"title": f"Updated Deal [{token}]"}
            elif endpoint == "activities":
                payload = {"subject": f"Updated Activity [{token}]"}
            elif endpoint == "products":
                payload = {"name": f"Updated Product [{token}]"}
            elif endpoint == "leads":
                payload = {"title": f"Updated Lead [{token}]"}
            elif endpoint == "notes":
                payload = {"content": f"Updated note content [{token}]"}
            else:
                continue

            r = await client.put(
                f"{PIPEDRIVE_API}/{endpoint}/{pipedrive_id}",
                json=payload,
                params=self._auth_params,
            )

            if r.status_code in (200, 201):
                updated.append({**ent, "updated": True})
            else:
                self.logger.warning(f"Update {endpoint}/{pipedrive_id} failed: {r.text}")

        return updated

    async def delete_entities(self) -> List[str]:
        """Delete all tracked test entities."""
        all_entities = (
            self._notes
            + self._activities
            + self._leads
            + self._deals
            + self._persons
            + self._organizations
            + self._products
        )
        return await self.delete_specific_entities(all_entities)

    async def delete_specific_entities(
        self, entities: List[Dict[str, Any]]
    ) -> List[str]:
        """Delete specific entities from Pipedrive."""
        self.logger.info(f"🥁 Deleting {len(entities)} Pipedrive entities")
        deleted: List[str] = []

        # Group entities by type for proper endpoint routing
        by_type: Dict[str, List[Dict[str, Any]]] = {}
        for ent in entities:
            ent_type = ent.get("type", "unknown")
            if ent_type not in by_type:
                by_type[ent_type] = []
            by_type[ent_type].append(ent)

        # Map types to API endpoints
        type_to_endpoint = {
            "person": "persons",
            "organization": "organizations",
            "deal": "deals",
            "activity": "activities",
            "product": "products",
            "lead": "leads",
            "note": "notes",
        }

        async with httpx.AsyncClient(timeout=30) as client:
            # Delete in reverse order of creation (notes first, then orgs last)
            delete_order = [
                "note",
                "activity",
                "lead",
                "deal",
                "person",
                "organization",
                "product",
            ]

            for ent_type in delete_order:
                if ent_type not in by_type:
                    continue

                endpoint = type_to_endpoint.get(ent_type)
                if not endpoint:
                    continue

                for ent in by_type[ent_type]:
                    try:
                        await self._pace()
                        # Use pipedrive_id (raw numeric ID) for API calls
                        pipedrive_id = ent.get("pipedrive_id", ent["id"])
                        r = await client.delete(
                            f"{PIPEDRIVE_API}/{endpoint}/{pipedrive_id}",
                            params=self._auth_params,
                        )

                        if r.status_code in (200, 204):
                            # Return the unique id (type-prefixed) for tracking
                            deleted.append(str(ent["id"]))
                        else:
                            self.logger.warning(
                                f"Delete {endpoint}/{pipedrive_id} failed {r.status_code}"
                            )
                    except Exception as e:
                        self.logger.warning(f"Delete error {ent['id']}: {e}")

        self.logger.info(f"✅ Deleted {len(deleted)} Pipedrive entities")
        return deleted

    async def cleanup(self):
        """Comprehensive cleanup of all test Pipedrive entities."""
        self.logger.info("🧹 Starting comprehensive Pipedrive cleanup")

        cleanup_stats = {
            "organizations": 0,
            "persons": 0,
            "deals": 0,
            "activities": 0,
            "products": 0,
            "leads": 0,
            "notes": 0,
            "errors": 0,
        }

        try:
            # First, delete current session entities
            all_current = (
                self._notes
                + self._activities
                + self._leads
                + self._deals
                + self._persons
                + self._organizations
                + self._products
            )

            if all_current:
                self.logger.info(f"🗑️ Cleaning up {len(all_current)} current session entities")
                deleted = await self.delete_specific_entities(all_current)
                for ent in all_current:
                    if str(ent["id"]) in deleted:
                        ent_type = ent.get("type", "unknown")
                        if ent_type in cleanup_stats:
                            cleanup_stats[ent_type] += 1

            # Clear tracking lists
            self._notes.clear()
            self._activities.clear()
            self._leads.clear()
            self._deals.clear()
            self._persons.clear()
            self._organizations.clear()
            self._products.clear()

            # Search for and delete orphaned test entities
            await self._cleanup_orphaned_entities(cleanup_stats)

            total_deleted = sum(
                v for k, v in cleanup_stats.items() if k != "errors"
            )
            self.logger.info(
                f"🧹 Cleanup completed: {total_deleted} entities deleted, "
                f"{cleanup_stats['errors']} errors"
            )
        except Exception as e:
            self.logger.error(f"❌ Error during comprehensive cleanup: {e}")

    async def _cleanup_orphaned_entities(self, stats: Dict[str, Any]):
        """Find and delete orphaned test entities from previous runs."""
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                # Clean up each type
                await self._cleanup_orphaned_type(
                    client, "notes", stats, self._is_test_note
                )
                await self._cleanup_orphaned_type(
                    client, "activities", stats, self._is_test_activity
                )
                await self._cleanup_orphaned_type(
                    client, "leads", stats, self._is_test_lead
                )
                await self._cleanup_orphaned_type(
                    client, "deals", stats, self._is_test_deal
                )
                await self._cleanup_orphaned_type(
                    client, "persons", stats, self._is_test_person
                )
                await self._cleanup_orphaned_type(
                    client, "organizations", stats, self._is_test_organization
                )
                await self._cleanup_orphaned_type(
                    client, "products", stats, self._is_test_product
                )
        except Exception as e:
            self.logger.warning(f"⚠️ Could not search for orphaned entities: {e}")

    async def _cleanup_orphaned_type(
        self,
        client: httpx.AsyncClient,
        endpoint: str,
        stats: Dict[str, Any],
        is_test_fn,
    ):
        """Clean up orphaned entities of a specific type."""
        try:
            await self._pace()
            r = await client.get(
                f"{PIPEDRIVE_API}/{endpoint}",
                params={**self._auth_params, "limit": 100},
            )

            if r.status_code != 200:
                return

            data = r.json()
            if not data.get("success"):
                return

            items = data.get("data") or []
            test_items = [item for item in items if is_test_fn(item)]

            if test_items:
                self.logger.info(f"🔍 Found {len(test_items)} orphaned {endpoint}")

            for item in test_items:
                try:
                    await self._pace()
                    del_r = await client.delete(
                        f"{PIPEDRIVE_API}/{endpoint}/{item['id']}",
                        params=self._auth_params,
                    )

                    if del_r.status_code in (200, 204):
                        # Map endpoint to stats key
                        stat_key = endpoint.rstrip("s") if endpoint != "activities" else "activities"
                        if endpoint == "persons":
                            stat_key = "persons"
                        elif endpoint == "organizations":
                            stat_key = "organizations"
                        elif endpoint == "products":
                            stat_key = "products"
                        elif endpoint == "leads":
                            stat_key = "leads"
                        elif endpoint == "notes":
                            stat_key = "notes"
                        elif endpoint == "deals":
                            stat_key = "deals"
                        elif endpoint == "activities":
                            stat_key = "activities"

                        stats[stat_key] = stats.get(stat_key, 0) + 1
                        self.logger.info(
                            f"✅ Deleted orphaned {endpoint}: {item.get('name', item.get('title', item.get('subject', 'unknown')))}"
                        )
                    else:
                        stats["errors"] += 1
                except Exception as e:
                    stats["errors"] += 1
                    self.logger.warning(f"⚠️ Failed to delete {endpoint} {item['id']}: {e}")
        except Exception as e:
            self.logger.warning(f"⚠️ Could not list {endpoint}: {e}")

    def _is_test_person(self, item: Dict[str, Any]) -> bool:
        """Check if a person is a test entity."""
        name = (item.get("name") or "").lower()
        email = ""
        if item.get("email"):
            emails = item["email"]
            if isinstance(emails, list) and emails:
                email = (emails[0].get("value") or "").lower()
        return "monke" in name or "monke-test.com" in email or "[" in (item.get("name") or "")

    def _is_test_organization(self, item: Dict[str, Any]) -> bool:
        """Check if an organization is a test entity."""
        name = (item.get("name") or "")
        return "monke" in name.lower() or "[" in name

    def _is_test_deal(self, item: Dict[str, Any]) -> bool:
        """Check if a deal is a test entity."""
        title = (item.get("title") or "")
        return "monke" in title.lower() or "[" in title

    def _is_test_activity(self, item: Dict[str, Any]) -> bool:
        """Check if an activity is a test entity."""
        subject = (item.get("subject") or "")
        return "monke" in subject.lower() or "[" in subject

    def _is_test_product(self, item: Dict[str, Any]) -> bool:
        """Check if a product is a test entity."""
        name = (item.get("name") or "")
        return "monke" in name.lower() or "[" in name

    def _is_test_lead(self, item: Dict[str, Any]) -> bool:
        """Check if a lead is a test entity."""
        title = (item.get("title") or "")
        return "monke" in title.lower() or "[" in title

    def _is_test_note(self, item: Dict[str, Any]) -> bool:
        """Check if a note is a test entity."""
        content = (item.get("content") or "")
        return "monke" in content.lower() or "[Reference:" in content
