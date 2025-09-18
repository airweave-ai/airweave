"""Asana-specific bongo implementation.

Creates, updates, and deletes test tasks via the real Asana API.
"""

import asyncio
import time
import uuid
from typing import Any, Dict, List, Optional

import httpx
from monke.bongos.base_bongo import BaseBongo
from monke.utils.logging import get_logger


class AsanaBongo(BaseBongo):
    """Bongo for Asana that creates projects and tasks for end-to-end testing.

    - Uses a Personal Access Token (PAT) as a bearer access token
    - Embeds a short token in task notes for verification
    - Creates a temporary project to keep test data scoped and easy to clean up
    """

    connector_type = "asana"

    API_BASE = "https://app.asana.com/api/1.0"

    def __init__(self, credentials: Dict[str, Any], **kwargs):
        """Initialize the Asana bongo.

        Args:
            credentials: Dict with at least "access_token" (Asana PAT)
            **kwargs: Optional configuration such as entity_count, openai_model,
                max_concurrency, rate_limit_delay
        """
        super().__init__(credentials)
        self.access_token: str = credentials["access_token"]
        self.entity_count: int = int(kwargs.get("entity_count", 5))
        self.openai_model: str = kwargs.get("openai_model", "gpt-4o-mini")
        self.max_concurrency: int = int(kwargs.get("max_concurrency", 1))
        # Use rate_limit_delay_ms from config if provided, otherwise default to 500ms
        rate_limit_ms = int(kwargs.get("rate_limit_delay_ms", 500))
        self.rate_limit_delay: float = rate_limit_ms / 1000.0

        # Runtime state
        self._workspace_gid: Optional[str] = None
        self._project_gid: Optional[str] = None
        self._tasks: List[Dict[str, Any]] = []

        # Pacing
        self.last_request_time = 0.0

        self.logger = get_logger("asana_bongo")

    async def create_entities(self) -> List[Dict[str, Any]]:
        """Create tasks in a temporary Asana project.

        Returns a list of created entity descriptors used by the test flow.
        """
        self.logger.info(f"🥁 Creating {self.entity_count} Asana tasks")
        await self._ensure_workspace()
        await self._ensure_project()

        from monke.generation.asana import generate_asana_task

        entities: List[Dict[str, Any]] = []
        semaphore = asyncio.Semaphore(self.max_concurrency)

        async with httpx.AsyncClient() as client:

            async def create_one() -> Optional[Dict[str, Any]]:
                async with semaphore:
                    try:
                        await self._rate_limit()
                        token = str(uuid.uuid4())[:8]
                        self.logger.info(
                            f"🔨 Generating content for task with token: {token}"
                        )
                        title, notes, comments = await generate_asana_task(
                            self.openai_model, token
                        )
                        self.logger.info(f"📝 Generated task: '{title[:50]}...'")

                        # Create task
                        resp = await client.post(
                            f"{self.API_BASE}/tasks",
                            headers=self._headers(),
                            json={
                                "data": {
                                    "name": title,
                                    "notes": notes,
                                    "projects": [self._project_gid],
                                }
                            },
                        )

                        # Better error handling - Asana returns 201 for successful creation
                        if resp.status_code not in (200, 201):
                            error_data = resp.text
                            try:
                                error_json = resp.json()
                                error_data = error_json
                            except Exception:
                                pass
                            self.logger.error(
                                f"Failed to create task: {resp.status_code} - {error_data}"
                            )
                            self.logger.error(
                                f"Request data: name='{title[:50]}...', notes='{notes[:50]}...', project={self._project_gid}"
                            )

                        resp.raise_for_status()
                        task = resp.json()["data"]
                        task_gid = task["gid"]

                        # Add up to 2 comments (non-fatal)
                        for c in comments[:2]:
                            try:
                                await self._rate_limit()
                                _ = await client.post(
                                    f"{self.API_BASE}/tasks/{task_gid}/stories",
                                    headers=self._headers(),
                                    json={"data": {"text": c}},
                                )
                            except Exception as ex:
                                self.logger.warning(
                                    f"Failed to add comment to {task_gid}: {ex}"
                                )

                        # Entity descriptor used by generic verification
                        return {
                            "type": "task",
                            "id": task_gid,
                            "name": title,
                            "token": token,
                            "expected_content": token,
                            # Synthetic path for logging/verification helpers
                            "path": f"asana/task/{task_gid}",
                        }
                    except Exception as e:
                        self.logger.error(
                            f"❌ Error in create_one: {type(e).__name__}: {str(e)}"
                        )
                        # Re-raise to be caught by gather
                        raise

            # Create tasks with better error handling
            tasks = [create_one() for _ in range(self.entity_count)]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Process results and handle any exceptions
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    self.logger.error(f"Failed to create task {i + 1}: {result}")
                    # Re-raise the first exception we encounter
                    raise result
                elif result:
                    entities.append(result)
                    self._tasks.append(result)
                    self.logger.info(
                        f"✅ Created task {i + 1}/{self.entity_count}: {result['name'][:50]}..."
                    )

        self.created_entities = entities
        return entities

    async def update_entities(self) -> List[Dict[str, Any]]:
        """Update a small subset of tasks by regenerating title/notes with same token."""
        self.logger.info("🥁 Updating some Asana tasks")
        if not self._tasks:
            return []

        from monke.generation.asana import generate_asana_task

        updated_entities: List[Dict[str, Any]] = []
        count = min(3, len(self._tasks))

        async with httpx.AsyncClient() as client:
            for i in range(count):
                await self._rate_limit()
                t = self._tasks[i]
                title, notes, _ = await generate_asana_task(
                    self.openai_model, t["token"]
                )
                resp = await client.put(
                    f"{self.API_BASE}/tasks/{t['id']}",
                    headers=self._headers(),
                    json={"data": {"name": title, "notes": notes}},
                )
                resp.raise_for_status()
                updated_entities.append(
                    {**t, "name": title, "expected_content": t["token"]}
                )

        return updated_entities

    async def delete_entities(self) -> List[str]:
        """Delete all created tasks and the temporary project."""
        self.logger.info("🥁 Deleting all Asana test entities")
        deleted_ids = await self.delete_specific_entities(self.created_entities)
        await self._delete_project()
        return deleted_ids

    async def delete_specific_entities(
        self, entities: List[Dict[str, Any]]
    ) -> List[str]:
        """Delete provided list of tasks by id."""
        self.logger.info(f"🥁 Deleting {len(entities)} Asana tasks")
        deleted: List[str] = []
        async with httpx.AsyncClient() as client:
            for e in entities:
                try:
                    await self._rate_limit()
                    r = await client.delete(
                        f"{self.API_BASE}/tasks/{e['id']}", headers=self._headers()
                    )
                    if r.status_code in (200, 204):
                        deleted.append(e["id"])
                    else:
                        self.logger.warning(
                            f"Delete failed for {e.get('id')}: {r.status_code} - {r.text}"
                        )
                except Exception as ex:
                    self.logger.warning(f"Delete error for {e.get('id')}: {ex}")
        return deleted

    async def cleanup(self):
        """Comprehensive cleanup of all monke test data from the workspace."""
        self.logger.info("🧹 Starting comprehensive Asana workspace cleanup")

        # Ensure we have workspace access
        await self._ensure_workspace()

        cleanup_stats = {"projects_deleted": 0, "tasks_deleted": 0, "errors": 0}

        try:
            # Clean up current session data first
            if self._tasks:
                self.logger.info(
                    f"🗑️ Cleaning up {len(self._tasks)} current session tasks"
                )
                await self.delete_specific_entities(self._tasks)
                cleanup_stats["tasks_deleted"] += len(self._tasks)

            if self._project_gid:
                self.logger.info(
                    f"🗑️ Cleaning up current session project {self._project_gid}"
                )
                await self._delete_project()
                cleanup_stats["projects_deleted"] += 1

            # Find and clean up all monke test projects
            monke_projects = await self._find_monke_test_projects()
            if monke_projects:
                self.logger.info(
                    f"🔍 Found {len(monke_projects)} monke test projects to clean up"
                )
                for project in monke_projects:
                    try:
                        await self._delete_project_by_gid(project["gid"])
                        cleanup_stats["projects_deleted"] += 1
                        self.logger.info(
                            f"✅ Deleted project: {project['name']} ({project['gid']})"
                        )
                    except Exception as e:
                        cleanup_stats["errors"] += 1
                        self.logger.warning(
                            f"⚠️ Failed to delete project {project['gid']}: {e}"
                        )

            # Find and clean up orphaned monke test tasks
            orphaned_tasks = await self._find_orphaned_monke_tasks()
            if orphaned_tasks:
                self.logger.info(
                    f"🔍 Found {len(orphaned_tasks)} orphaned monke test tasks to clean up"
                )
                for task in orphaned_tasks:
                    try:
                        await self._delete_task_by_gid(task["gid"])
                        cleanup_stats["tasks_deleted"] += 1
                        self.logger.info(
                            f"✅ Deleted orphaned task: {task['name']} ({task['gid']})"
                        )
                    except Exception as e:
                        cleanup_stats["errors"] += 1
                        self.logger.warning(
                            f"⚠️ Failed to delete task {task['gid']}: {e}"
                        )

            # Log cleanup summary
            self.logger.info(
                f"🧹 Cleanup completed: {cleanup_stats['projects_deleted']} projects, "
                f"{cleanup_stats['tasks_deleted']} tasks deleted, {cleanup_stats['errors']} errors"
            )

        except Exception as e:
            self.logger.error(f"❌ Error during comprehensive cleanup: {e}")
            # Don't re-raise - cleanup should be best-effort

    async def _ensure_workspace(self):
        if self._workspace_gid:
            return
        async with httpx.AsyncClient() as client:
            r = await client.get(f"{self.API_BASE}/workspaces", headers=self._headers())
            r.raise_for_status()
            workspaces = r.json().get("data", [])
            if not workspaces:
                raise RuntimeError("No Asana workspaces accessible via this PAT")
            self._workspace_gid = workspaces[0]["gid"]
            self.logger.info(f"Using workspace {self._workspace_gid}")

    async def _ensure_project(self):
        if self._project_gid:
            return

        name = f"monke-asana-test-{str(uuid.uuid4())[:6]}"
        async with httpx.AsyncClient() as client:
            # Try to find a team in the chosen workspace (orgs require this)
            team_gid = None
            try:
                tr = await client.get(
                    f"{self.API_BASE}/workspaces/{self._workspace_gid}/teams",
                    headers=self._headers(),
                )
                tr.raise_for_status()
                teams = tr.json().get("data", [])
                if teams:
                    team_gid = teams[0]["gid"]
            except Exception as e:
                self.logger.warning(
                    f"Could not list teams for workspace {self._workspace_gid}: {e}"
                )

            # Prefer the team endpoint if we found one; otherwise fall back to workspace create
            if team_gid:
                url = f"{self.API_BASE}/teams/{team_gid}/projects"
                payload = {"data": {"name": name}}
            else:
                url = f"{self.API_BASE}/projects"
                payload = {"data": {"name": name, "workspace": self._workspace_gid}}

            r = await client.post(url, headers=self._headers(), json=payload)

            if r.status_code not in (200, 201):
                # Log server's error body so failures are self-explanatory
                self.logger.error(f"Project create failed {r.status_code}: {r.text}")
            r.raise_for_status()

            self._project_gid = r.json()["data"]["gid"]
            self.logger.info(f"Created project {name} ({self._project_gid})")

    async def _delete_project(self):
        if not self._project_gid:
            return
        await self._delete_project_by_gid(self._project_gid)
        self._project_gid = None

    async def _delete_project_by_gid(self, project_gid: str):
        """Delete a project by its GID."""
        async with httpx.AsyncClient() as client:
            await self._rate_limit()
            r = await client.delete(
                f"{self.API_BASE}/projects/{project_gid}", headers=self._headers()
            )
            if r.status_code in (200, 204):
                self.logger.debug(f"Deleted project {project_gid}")
            else:
                self.logger.warning(
                    f"Failed to delete project {project_gid}: {r.status_code} - {r.text}"
                )
                r.raise_for_status()

    async def _delete_task_by_gid(self, task_gid: str):
        """Delete a task by its GID."""
        async with httpx.AsyncClient() as client:
            await self._rate_limit()
            r = await client.delete(
                f"{self.API_BASE}/tasks/{task_gid}", headers=self._headers()
            )
            if r.status_code in (200, 204):
                self.logger.debug(f"Deleted task {task_gid}")
            else:
                self.logger.warning(
                    f"Failed to delete task {task_gid}: {r.status_code} - {r.text}"
                )
                r.raise_for_status()

    async def _find_monke_test_projects(self) -> List[Dict[str, Any]]:
        """Find all monke test projects in the workspace."""
        monke_projects = []

        async with httpx.AsyncClient() as client:
            await self._rate_limit()
            r = await client.get(
                f"{self.API_BASE}/projects",
                headers=self._headers(),
                params={
                    "workspace": self._workspace_gid,
                    "opt_fields": "name,gid,created_at",
                },
            )
            r.raise_for_status()

            projects = r.json().get("data", [])
            for project in projects:
                name = project.get("name", "")
                if name.startswith("monke-asana-test-") or "monke" in name.lower():
                    monke_projects.append(project)

        return monke_projects

    async def _find_orphaned_monke_tasks(self) -> List[Dict[str, Any]]:
        """Find orphaned monke test tasks (tasks not in projects but containing monke identifiers)."""
        orphaned_tasks = []

        async with httpx.AsyncClient() as client:
            # Search for tasks assigned to the authenticated user that might be monke tests
            await self._rate_limit()
            r = await client.get(
                f"{self.API_BASE}/tasks",
                headers=self._headers(),
                params={
                    "assignee": "me",
                    "workspace": self._workspace_gid,
                    "opt_fields": "name,gid,notes,projects.name",
                    "completed_since": "now",  # Only get incomplete tasks
                },
            )

            if r.status_code == 200:
                tasks = r.json().get("data", [])
                for task in tasks:
                    name = task.get("name", "")
                    notes = task.get("notes", "")
                    projects = task.get("projects", [])

                    # Check if this looks like a monke test task
                    is_monke_task = (
                        "monke" in name.lower()
                        or "monke test" in notes.lower()
                        or any(
                            uuid_pattern in notes
                            for uuid_pattern in ["-", "test-token"]
                        )
                        or (
                            not projects and "test" in name.lower()
                        )  # Orphaned test tasks
                    )

                    if is_monke_task:
                        orphaned_tasks.append(task)
            else:
                self.logger.warning(
                    f"Failed to search for orphaned tasks: {r.status_code} - {r.text}"
                )

        return orphaned_tasks

    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    async def _rate_limit(self):
        now = time.time()
        delta = now - self.last_request_time
        if delta < self.rate_limit_delay:
            await asyncio.sleep(self.rate_limit_delay - delta)
        self.last_request_time = time.time()
