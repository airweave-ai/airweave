import asyncio, time, uuid
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
        self.llm_model = kwargs.get("llm_model", None)
        self.rate_limit_delay = float(kwargs.get("rate_limit_delay_ms", 500)) / 1000.0
        self.logger = get_logger("outlook_mail_bongo")
        self._messages: List[Dict[str, Any]] = []
        self._last_req = 0.0

    async def create_entities(self) -> List[Dict[str, Any]]:
        self.logger.info(f"🥁 Creating {self.entity_count} Outlook draft messages")
        out: List[Dict[str, Any]] = []
        async with httpx.AsyncClient(base_url=GRAPH, timeout=30) as client:
            for _ in range(self.entity_count):
                await self._pace()
                token = uuid.uuid4().hex[:8]
                msg = await generate_outlook_message(self.llm_model, token)
                payload = {
                    "subject": msg.subject,
                    "body": {"contentType": "HTML", "content": msg.body_html},
                    "toRecipients": [{"emailAddress": {"address": a}} for a in msg.to],
                }
                r = await client.post(
                    "/me/messages", headers=self._hdrs(), json=payload
                )  # create DRAFT
                if r.status_code not in (200, 201):
                    self.logger.error(f"Draft create failed {r.status_code}: {r.text}")
                r.raise_for_status()
                data = r.json()
                ent = {
                    "type": "message",
                    "id": data["id"],
                    "name": msg.subject,
                    "token": token,
                    "expected_content": token,
                    "path": f"graph/messages/{data['id']}",
                }
                out.append(ent)
                self._messages.append(ent)
                self.created_entities.append({"id": data["id"], "name": msg.subject})
        return out

    async def update_entities(self) -> List[Dict[str, Any]]:
        if not self._messages:
            return []
        self.logger.info("🥁 Updating some drafts (append '[updated]' to subject)")
        async with httpx.AsyncClient(base_url=GRAPH, timeout=30) as client:
            updated = []
            for ent in self._messages[: min(3, len(self._messages))]:
                await self._pace()
                r = await client.patch(
                    f"/me/messages/{ent['id']}",
                    headers=self._hdrs(),
                    json={"subject": ent["name"] + " [updated]"},
                )
                r.raise_for_status()
                updated.append({**ent, "updated": True})
            return updated

    async def delete_entities(self) -> List[str]:
        return await self.delete_specific_entities(self._messages)

    async def delete_specific_entities(self, entities: List[Dict[str, Any]]) -> List[str]:
        self.logger.info(f"🥁 Deleting {len(entities)} Outlook drafts")
        deleted: List[str] = []
        async with httpx.AsyncClient(base_url=GRAPH, timeout=30) as client:
            for ent in entities:
                try:
                    await self._pace()
                    r = await client.delete(f"/me/messages/{ent['id']}", headers=self._hdrs())
                    if r.status_code == 204:
                        deleted.append(ent["id"])
                    else:
                        self.logger.warning(f"Delete {ent['id']} -> {r.status_code}: {r.text}")
                except Exception as e:
                    self.logger.warning(f"Delete error {ent['id']}: {e}")
        return deleted

    async def cleanup(self):
        try:
            await self.delete_specific_entities(self._messages)
        except Exception:
            pass

    def _hdrs(self) -> Dict[str, str]:
        return {"Authorization": f"Bearer {self.access_token}", "Content-Type": "application/json"}

    async def _pace(self):
        now = time.time()
        if (delta := now - self._last_req) < self.rate_limit_delay:
            await asyncio.sleep(self.rate_limit_delay - delta)
        self._last_req = time.time()
