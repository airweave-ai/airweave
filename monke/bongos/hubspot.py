import asyncio, time, uuid
from typing import Any, Dict, List, Optional

import httpx
from monke.bongos.base_bongo import BaseBongo
from monke.generation.hubspot import generate_hubspot_contact
from monke.utils.logging import get_logger

HUBSPOT_API = "https://api.hubapi.com"


class HubSpotBongo(BaseBongo):
    """Creates/updates/deletes HubSpot Contacts using Private App token."""

    connector_type = "hubspot"

    def __init__(self, credentials: Dict[str, Any], **kwargs):
        super().__init__(credentials)
        self.access_token: str = credentials["access_token"]
        self.entity_count: int = int(kwargs.get("entity_count", 3))
        self.openai_model: str = kwargs.get("openai_model", "gpt-4.1")
        self.rate_limit_delay = float(kwargs.get("rate_limit_delay_ms", 800)) / 1000.0
        self.logger = get_logger("hubspot_bongo")
        self._contacts: List[Dict[str, Any]] = []
        self._last_req = 0.0

    async def create_entities(self) -> List[Dict[str, Any]]:
        self.logger.info(f"🥁 Creating {self.entity_count} HubSpot contacts")
        out: List[Dict[str, Any]] = []
        async with httpx.AsyncClient(base_url=HUBSPOT_API, timeout=30) as client:
            for _ in range(self.entity_count):
                await self._pace()
                token = str(uuid.uuid4())[:8]
                c = await generate_hubspot_contact(self.openai_model, token)
                payload = {
                    "properties": {
                        "email": c.email,
                        "firstname": c.firstname,
                        "lastname": c.lastname,
                        **({"phone": c.phone} if c.phone else {}),
                        **({"company": c.company} if c.company else {}),
                        **({"address": c.address} if c.address else {}),
                        **({"city": c.city} if c.city else {}),
                        **({"state": c.state} if c.state else {}),
                        **({"zip": c.zip} if c.zip else {}),
                    }
                }
                r = await client.post(
                    "/crm/v3/objects/contacts",
                    headers=self._hdrs(),
                    json=payload,
                )
                if r.status_code not in (200, 201):
                    self.logger.error(f"HubSpot create failed {r.status_code}: {r.text}")
                r.raise_for_status()
                data = r.json()
                contact_id = data.get("id")
                ent = {
                    "type": "contact",
                    "id": contact_id,
                    "name": f"{c.firstname} {c.lastname}",
                    "token": token,
                    "expected_content": token,
                    "path": f"hubspot/contact/{contact_id}",
                }
                out.append(ent)
                self._contacts.append(ent)
                self.created_entities.append({"id": contact_id, "name": ent["name"]})
        return out

    async def update_entities(self) -> List[Dict[str, Any]]:
        if not self._contacts:
            return []
        self.logger.info("🥁 Updating some HubSpot contacts")
        updated: List[Dict[str, Any]] = []
        async with httpx.AsyncClient(base_url=HUBSPOT_API, timeout=30) as client:
            for ent in self._contacts[: min(3, len(self._contacts))]:
                await self._pace()
                # tiny tweak: add a note-ish detail (mapped to 'company' or 'phone')
                r = await client.patch(
                    f"/crm/v3/objects/contacts/{ent['id']}",
                    headers=self._hdrs(),
                    json={"properties": {"company": "Monke QA", "phone": "+1-555-0100"}},
                )
                r.raise_for_status()
                updated.append({**ent, "updated": True})
        return updated

    async def delete_entities(self) -> List[str]:
        return await self.delete_specific_entities(self._contacts)

    async def delete_specific_entities(self, entities: List[Dict[str, Any]]) -> List[str]:
        self.logger.info(f"🥁 Deleting {len(entities)} HubSpot contacts")
        deleted: List[str] = []
        async with httpx.AsyncClient(base_url=HUBSPOT_API, timeout=30) as client:
            for ent in entities:
                try:
                    await self._pace()
                    r = await client.delete(
                        f"/crm/v3/objects/contacts/{ent['id']}", headers=self._hdrs()
                    )
                    if r.status_code in (200, 204):
                        deleted.append(ent["id"])
                    else:
                        self.logger.warning(f"Delete failed {r.status_code}: {r.text}")
                except Exception as e:
                    self.logger.warning(f"Delete error {ent['id']}: {e}")
        return deleted

    async def cleanup(self):
        try:
            await self.delete_specific_entities(self._contacts)
        except Exception:
            pass

    def _hdrs(self) -> Dict[str, str]:
        return {"Authorization": f"Bearer {self.access_token}", "Content-Type": "application/json"}

    async def _pace(self):
        now = time.time()
        if (delta := now - self._last_req) < self.rate_limit_delay:
            await asyncio.sleep(self.rate_limit_delay - delta)
        self._last_req = time.time()
