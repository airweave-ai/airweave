"""ServiceNow bongo implementation.

Creates, updates, and deletes test incidents (and optionally other entities)
via the ServiceNow Table API for E2E testing.
"""

import asyncio
import base64
import time
import uuid
from typing import Any, Dict, List, Optional

import httpx
from monke.bongos.base_bongo import BaseBongo
from monke.utils.logging import get_logger


class ServiceNowBongo(BaseBongo):
    """Bongo for ServiceNow that creates incidents for end-to-end testing.

    Uses Basic Auth (url, username, password). Creates incidents with
    short_description and description containing a verification token.
    """

    connector_type = "servicenow"

    def __init__(self, credentials: Dict[str, Any], **kwargs):
        """Initialize the ServiceNow bongo.

        Args:
            credentials: Dict with url, username, password (ServiceNowAuthConfig)
            **kwargs: entity_count, openai_model, rate_limit_delay_ms, etc.
        """
        super().__init__(credentials)
        self.url: str = (credentials.get("url") or "").rstrip("/")
        self.username: str = credentials.get("username") or ""
        self.password: str = credentials.get("password") or ""
        if not self.url or not self.username or not self.password:
            raise ValueError(
                "ServiceNow credentials must include url, username, and password"
            )
        token = base64.b64encode(
            f"{self.username}:{self.password}".encode()
        ).decode()
        self._auth_header = f"Basic {token}"

        self.entity_count: int = int(kwargs.get("entity_count", 3))
        self.openai_model: str = kwargs.get("openai_model", "gpt-4o-mini")
        rate_limit_ms = int(kwargs.get("rate_limit_delay_ms", 500))
        self.rate_limit_delay: float = rate_limit_ms / 1000.0

        self._incidents: List[Dict[str, Any]] = []
        self.last_request_time = 0.0
        self.logger = get_logger("servicenow_bongo")

    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": self._auth_header,
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    def _table_url(self, table: str) -> str:
        return f"{self.url}/api/now/table/{table}"

    async def _rate_limit(self) -> None:
        now = time.time()
        elapsed = now - self.last_request_time
        if elapsed < self.rate_limit_delay:
            await asyncio.sleep(self.rate_limit_delay - elapsed)
        self.last_request_time = time.time()

    async def create_entities(self) -> List[Dict[str, Any]]:
        """Create incidents in ServiceNow with embedded verification tokens."""
        self.logger.info(f"Creating {self.entity_count} ServiceNow incidents")
        from monke.generation.servicenow import generate_servicenow_incident

        entities: List[Dict[str, Any]] = []
        async with httpx.AsyncClient(timeout=60.0) as client:
            for i in range(self.entity_count):
                await self._rate_limit()
                token = str(uuid.uuid4())[:8]
                self.logger.info(f"Generating incident content with token: {token}")
                subject, description = await generate_servicenow_incident(
                    self.openai_model, token
                )
                payload = {
                    "short_description": subject,
                    "description": description,
                }
                try:
                    resp = await client.post(
                        self._table_url("incident"),
                        headers=self._headers(),
                        json=payload,
                    )
                    resp.raise_for_status()
                    data = resp.json()
                    result = data.get("result") or {}
                    sys_id = result.get("sys_id", "")
                    number = result.get("number", sys_id)
                    ent = {
                        "type": "incident",
                        "id": sys_id,
                        "name": subject,
                        "token": token,
                        "expected_content": token,
                        "path": f"servicenow/incident/{sys_id}",
                    }
                    entities.append(ent)
                    self._incidents.append(ent)
                    self.logger.info(f"Created incident {number}: {sys_id}")
                except Exception as e:
                    self.logger.error(f"Failed to create incident: {e}")
                    raise

        self.created_entities = entities
        return entities

    async def update_entities(self) -> List[Dict[str, Any]]:
        """Update a subset of incidents with new description (same token)."""
        self.logger.info("Updating some ServiceNow incidents")
        if not self._incidents:
            return []

        from monke.generation.servicenow import generate_servicenow_incident

        updated: List[Dict[str, Any]] = []
        count = min(2, len(self._incidents))
        async with httpx.AsyncClient(timeout=60.0) as client:
            for i in range(count):
                ent = self._incidents[i]
                await self._rate_limit()
                _, description = await generate_servicenow_incident(
                    self.openai_model, ent["token"]
                )
                try:
                    resp = await client.patch(
                        f"{self._table_url('incident')}/{ent['id']}",
                        headers=self._headers(),
                        json={"description": description},
                    )
                    resp.raise_for_status()
                    updated.append({**ent, "expected_content": ent["token"]})
                except Exception as e:
                    self.logger.error(f"Failed to update incident {ent['id']}: {e}")
        return updated

    async def delete_entities(self) -> List[str]:
        """Delete all created incidents."""
        self.logger.info("Deleting all ServiceNow test incidents")
        return await self.delete_specific_entities(self.created_entities)

    async def delete_specific_entities(
        self, entities: List[Dict[str, Any]]
    ) -> List[str]:
        """Delete given incidents by sys_id."""
        deleted: List[str] = []
        async with httpx.AsyncClient(timeout=30.0) as client:
            for ent in entities:
                if ent.get("type") != "incident":
                    continue
                await self._rate_limit()
                try:
                    resp = await client.delete(
                        f"{self._table_url('incident')}/{ent['id']}",
                        headers=self._headers(),
                    )
                    if resp.status_code in (200, 204):
                        deleted.append(ent["id"])
                    else:
                        self.logger.warning(
                            f"Delete incident {ent['id']}: {resp.status_code}"
                        )
                except Exception as e:
                    self.logger.error(f"Failed to delete {ent['id']}: {e}")
        return deleted

    async def cleanup(self) -> None:
        """Remove all test incidents created by this bongo."""
        if self.created_entities:
            await self.delete_entities()
