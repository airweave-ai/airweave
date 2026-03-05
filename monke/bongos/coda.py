"""Coda bongo: create, update, and delete test docs via Coda API v1."""

import asyncio
import time
import uuid
from typing import Any, Dict, List, Optional

import httpx
from monke.bongos.base_bongo import BaseBongo
from monke.utils.logging import get_logger

CODA_API_BASE = "https://coda.io/apis/v1"

# Rate limits: 10 write/6s, 5 doc content/10s — be conservative
RATE_LIMIT_DELAY = 0.7


class CodaBongo(BaseBongo):
    """Bongo for Coda: creates test docs with a page for Monke E2E tests."""

    connector_type = "coda"

    def __init__(self, credentials: Dict[str, Any], **kwargs):
        super().__init__(credentials)
        # Coda DIRECT auth uses api_key (Personal API Token)
        self.token: str = credentials.get("api_key") or credentials.get("access_token", "")
        self.entity_count: int = int(kwargs.get("entity_count", 3))
        self.openai_model: str = kwargs.get("openai_model", "gpt-4.1-mini")
        self._docs: List[Dict[str, Any]] = []
        self._last_request_time = 0.0
        self.logger = get_logger("coda_bongo")

    async def _rate_limit(self) -> None:
        now = time.time()
        elapsed = now - self._last_request_time
        if elapsed < RATE_LIMIT_DELAY:
            await asyncio.sleep(RATE_LIMIT_DELAY - elapsed)
        self._last_request_time = time.time()

    async def _request(
        self,
        method: str,
        path: str,
        json_data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        await self._rate_limit()
        url = f"{CODA_API_BASE}{path}" if path.startswith("/") else f"{CODA_API_BASE}/{path}"
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }
        async with httpx.AsyncClient(timeout=30.0) as client:
            if method == "GET":
                resp = await client.get(url, headers=headers)
            elif method == "POST":
                resp = await client.post(url, headers=headers, json=json_data or {})
            elif method == "PATCH":
                resp = await client.patch(url, headers=headers, json=json_data or {})
            elif method == "DELETE":
                resp = await client.delete(url, headers=headers)
            else:
                raise ValueError(f"Unsupported method: {method}")
            if resp.status_code >= 400:
                self.logger.error(f"Coda API error {resp.status_code}: {resp.text[:300]}")
            resp.raise_for_status()
            if resp.status_code == 204 or not resp.text:
                return {}
            return resp.json()

    async def create_entities(self) -> List[Dict[str, Any]]:
        """Create test docs (each with one page) via Coda API."""
        self.logger.info("Creating %s Coda test docs", self.entity_count)
        from monke.generation.coda import generate_coda_doc

        created = []
        for i in range(self.entity_count):
            token = str(uuid.uuid4())[:8]
            title, intro_html = await generate_coda_doc(self.openai_model, token)
            title_with_token = f"{token} {title}"
            body = {
                "title": title_with_token,
                "initialPage": {
                    "name": "Page 1",
                    "pageContent": {
                        "type": "canvas",
                        "canvasContent": {"format": "html", "content": intro_html},
                    },
                },
            }
            try:
                doc = await self._request("POST", "/docs", json_data=body)
            except Exception as e:
                self.logger.error("Failed to create Coda doc: %s", e)
                raise
            doc_id = doc.get("id")
            browser_link = doc.get("browserLink", "")
            created.append(
                {
                    "id": doc_id,
                    "title": title_with_token,
                    "token": token,
                    "url": browser_link,
                    "expected_content": f"Monke verification token {token}",
                }
            )
            self.logger.info("Created doc %s: %s", doc_id, title_with_token)
        self._docs = created
        self.created_entities = created
        return created

    async def update_entities(self) -> List[Dict[str, Any]]:
        """Update first few test docs (title) via PATCH."""
        if not self._docs:
            self.logger.warning("No docs to update")
            return []
        from monke.generation.coda import generate_coda_doc

        updated = []
        for i, doc in enumerate(self._docs[: min(3, len(self._docs))]):
            token = doc["token"]
            title, _ = await generate_coda_doc(self.openai_model, token, update=True)
            new_title = f"{token} {title} (Updated)"
            try:
                await self._request(
                    "PATCH",
                    f"/docs/{doc['id']}",
                    json_data={"title": new_title},
                )
            except Exception as e:
                self.logger.warning("Failed to update doc %s: %s", doc["id"], e)
                continue
            updated.append({**doc, "title": new_title, "expected_content": f"Monke verification token {token}"})
        return updated

    async def delete_entities(self) -> List[str]:
        """Delete all created docs via DELETE /docs/{docId}."""
        if not self._docs:
            return []
        deleted = []
        for doc in self._docs:
            try:
                await self._request("DELETE", f"/docs/{doc['id']}")
                deleted.append(doc["id"])
            except Exception as e:
                self.logger.warning("Failed to delete doc %s: %s", doc["id"], e)
        self._docs = []
        return deleted

    async def delete_specific_entities(self, entities: List[Dict[str, Any]]) -> List[str]:
        """Delete given docs by id."""
        deleted = []
        for ent in entities:
            doc_id = ent.get("id")
            if not doc_id:
                continue
            try:
                await self._request("DELETE", f"/docs/{doc_id}")
                deleted.append(doc_id)
            except Exception as e:
                self.logger.warning("Failed to delete doc %s: %s", doc_id, e)
        id_set = set(deleted)
        self._docs = [d for d in self._docs if d["id"] not in id_set]
        return deleted

    async def cleanup(self) -> None:
        """Clean up created docs and any orphaned Monke docs (by listing and filtering)."""
        self.logger.info("Coda cleanup: deleting %s session docs", len(self._docs))
        await self.delete_entities()
        # Optional: list docs with query "Monke" or token pattern and delete — Coda list doesn't
        # guarantee we can find all; rely on delete_entities for this run.
        self.logger.info("Coda cleanup complete")
