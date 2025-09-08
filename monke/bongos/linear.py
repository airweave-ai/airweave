import asyncio, time, uuid, json
from typing import Any, Dict, List, Optional

import httpx
from monke.bongos.base_bongo import BaseBongo
from monke.generation.linear import generate_linear_issue
from monke.utils.logging import get_logger

LINEAR_GQL = "https://api.linear.app/graphql"


class LinearBongo(BaseBongo):
    connector_type = "linear"

    def __init__(self, credentials: Dict[str, Any], **kwargs):
        super().__init__(credentials)
        self.access_token: str = credentials["access_token"]  # Personal API key or OAuth token
        self.entity_count: int = int(kwargs.get("entity_count", 3))
        self.openai_model: str = kwargs.get("openai_model", "gpt-4.1-mini")
        self.rate_limit_delay = float(kwargs.get("rate_limit_delay_ms", 500)) / 1000.0
        self.logger = get_logger("linear_bongo")
        self._issues: List[Dict[str, Any]] = []
        self._last_req = 0.0

    async def create_entities(self) -> List[Dict[str, Any]]:
        self.logger.info(f"🥁 Creating {self.entity_count} Linear issues")
        async with httpx.AsyncClient(timeout=30) as client:
            team_id = await self._first_team_id(client)
            out: List[Dict[str, Any]] = []
            for _ in range(self.entity_count):
                await self._pace()
                token = str(uuid.uuid4())[:8]
                data = await generate_linear_issue(self.openai_model, token)
                q = """
                mutation IssueCreate($input: IssueCreateInput!) {
                  issueCreate(input: $input) {
                    success
                    issue { id identifier title url }
                  }
                }"""
                variables = {
                    "input": {
                        "teamId": team_id,
                        "title": data.spec.title,
                        "description": data.content.description,
                    }
                }
                resp = await self._gql(client, q, variables)
                issue = ((resp.get("data") or {}).get("issueCreate") or {}).get("issue")
                if not issue:
                    raise RuntimeError(f"Linear issueCreate failed: {resp}")
                ent = {
                    "type": "issue",
                    "id": issue["id"],
                    "name": issue["title"],
                    "token": token,
                    "expected_content": token,
                    "path": f"linear/issue/{issue['identifier']}",
                }
                out.append(ent)
                self._issues.append(ent)
                self.created_entities.append({"id": issue["id"], "name": issue["title"]})

                # add 1-2 comments (best effort)
                for c in data.content.comments[:2]:
                    await self._pace()
                    qc = """
                    mutation CommentCreate($input: CommentCreateInput!) {
                      commentCreate(input: $input) { success comment { id } }
                    }"""
                    _ = await self._gql(client, qc, {"input": {"issueId": issue["id"], "body": c}})
            return out

    async def update_entities(self) -> List[Dict[str, Any]]:
        if not self._issues:
            return []
        self.logger.info("🥁 Updating some Linear issues (title tweak)")
        async with httpx.AsyncClient(timeout=30) as client:
            updated = []
            for ent in self._issues[: min(3, len(self._issues))]:
                await self._pace()
                q = """
                mutation IssueUpdate($id: String!, $input: IssueUpdateInput!) {
                  issueUpdate(id: $id, input: $input) { success issue { id title } }
                }"""
                resp = await self._gql(
                    client, q, {"id": ent["id"], "input": {"title": ent["name"] + " [updated]"}}
                )
                updated.append({**ent, "updated": True})
            return updated

    async def delete_entities(self) -> List[str]:
        return await self.delete_specific_entities(self._issues)

    async def delete_specific_entities(self, entities: List[Dict[str, Any]]) -> List[str]:
        self.logger.info(f"🥁 Deleting/archiving {len(entities)} Linear issues")
        deleted: List[str] = []
        async with httpx.AsyncClient(timeout=30) as client:
            for ent in entities:
                try:
                    await self._pace()
                    q = """mutation IssueArchive($id: String!) { issueArchive(id: $id) { success } }"""
                    r = await self._gql(client, q, {"id": ent["id"]})
                    deleted.append(ent["id"])
                except Exception as e:
                    self.logger.warning(f"archive failed for {ent['id']}: {e}")
        return deleted

    async def cleanup(self):
        try:
            await self.delete_specific_entities(self._issues)
        except Exception:
            pass

    async def _first_team_id(self, client: httpx.AsyncClient) -> str:
        q = "query { teams(first: 1) { nodes { id name key } } }"
        resp = await self._gql(client, q, {})
        nodes = ((resp.get("data") or {}).get("teams") or {}).get("nodes") or []
        if not nodes:
            raise RuntimeError("No Linear teams available for API key")
        return nodes[0]["id"]

    async def _gql(
        self, client: httpx.AsyncClient, query: str, variables: Dict[str, Any]
    ) -> Dict[str, Any]:
        r = await client.post(
            LINEAR_GQL,
            headers={"Content-Type": "application/json", "Authorization": self.access_token},
            json={"query": query, "variables": variables},
        )
        if r.status_code != 200:
            raise RuntimeError(f"Linear GraphQL error {r.status_code}: {r.text}")
        return r.json()

    async def _pace(self):
        now = time.time()
        if (delta := now - self._last_req) < self.rate_limit_delay:
            await asyncio.sleep(self.rate_limit_delay - delta)
        self._last_req = time.time()
