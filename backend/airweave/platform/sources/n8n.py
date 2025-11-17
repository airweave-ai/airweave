"""n8n source implementation.

We retrieve data from the n8n REST API for the following resources:
- Workflows (workflow definitions with nodes, connections, and settings)
- Executions (workflow execution history and logs)

Then, we yield them as entities using the respective entity schemas defined in entities/n8n.py.

API Reference:
    https://docs.n8n.io/api/api-reference/
"""

from datetime import datetime
from typing import Any, AsyncGenerator, Dict, Optional

import httpx
from tenacity import retry, stop_after_attempt

from airweave.core.shared_models import RateLimitLevel
from airweave.platform.configs.auth import N8nAuthConfig
from airweave.platform.configs.config import N8nConfig
from airweave.platform.decorators import source
from airweave.platform.entities._base import BaseEntity, Breadcrumb
from airweave.platform.entities.n8n import N8nExecutionEntity, N8nWorkflowEntity
from airweave.platform.sources._base import BaseSource
from airweave.platform.sources.retry_helpers import (
    retry_if_rate_limit_or_timeout,
    wait_rate_limit_with_backoff,
)
from airweave.schemas.source_connection import AuthenticationMethod


@source(
    name="n8n",
    short_name="n8n",
    auth_methods=[AuthenticationMethod.DIRECT],
    oauth_type=None,
    auth_config_class="N8nAuthConfig",
    config_class="N8nConfig",
    labels=["Automation", "Workflow"],
    supports_continuous=False,
    rate_limit_level=RateLimitLevel.ORG,
)
class N8nSource(BaseSource):
    """n8n source connector integrates with the n8n REST API to extract workflow data.

    Synchronizes workflow definitions and execution history from your n8n instance.

    It provides access to all workflows (active and inactive) and their recent
    execution history, enabling search across workflow configurations and logs.
    """

    @classmethod
    async def create(
        cls, n8n_auth_config: N8nAuthConfig, config: Optional[Dict[str, Any]] = None
    ) -> "N8nSource":
        """Create a new n8n source instance.

        Args:
            n8n_auth_config: Authentication config with URL and API key
            config: Optional configuration parameters

        Returns:
            Configured N8nSource instance
        """
        instance = cls()
        instance.base_url = n8n_auth_config.url
        instance.api_key = n8n_auth_config.api_key

        # Parse config if provided
        if config:
            n8n_config = N8nConfig(**config)
            instance.include_executions = n8n_config.include_executions
            instance.max_executions_per_workflow = n8n_config.max_executions_per_workflow
        else:
            # Use defaults
            instance.include_executions = True
            instance.max_executions_per_workflow = 100

        return instance

    @retry(
        stop=stop_after_attempt(5),
        retry=retry_if_rate_limit_or_timeout,
        wait=wait_rate_limit_with_backoff,
        reraise=True,
    )
    async def _get_with_auth(
        self, client: httpx.AsyncClient, endpoint: str, params: Optional[Dict[str, Any]] = None
    ) -> dict:
        """Make an authenticated GET request to the n8n API.

        Args:
            client: HTTP client to use for the request
            endpoint: API endpoint path (e.g., '/workflows')
            params: Optional query parameters

        Returns:
            JSON response as dictionary

        Note:
            n8n uses the X-N8N-API-KEY header for authentication.
            API Reference: https://docs.n8n.io/api/api-reference/
        """
        # Construct full URL
        url = f"{self.base_url}/api/v1{endpoint}"

        # Set authentication header
        headers = {"X-N8N-API-KEY": self.api_key}

        # Make request with timeout
        response = await client.get(url, headers=headers, params=params, timeout=20.0)
        response.raise_for_status()
        return response.json()

    async def _generate_workflow_entities(
        self, client: httpx.AsyncClient
    ) -> AsyncGenerator[N8nWorkflowEntity, None]:
        """Retrieve and yield workflow entities from n8n.

        Fetches all workflows (both active and inactive) from the n8n instance.

        Args:
            client: HTTP client for making requests

        Yields:
            N8nWorkflowEntity objects for each workflow
        """
        # Fetch all workflows (active and inactive)
        # n8n API returns all workflows by default
        workflows_data = await self._get_with_auth(client, "/workflows")

        # The API returns {data: [...workflows...]}
        workflows = workflows_data.get("data", [])

        self.logger.info(f"Found {len(workflows)} workflows in n8n instance")

        for workflow in workflows:
            # Extract workflow data
            workflow_id = str(workflow["id"])
            workflow_name = workflow.get("name", f"Workflow {workflow_id}")

            # Parse timestamps if available
            created_at = None
            updated_at = None

            if workflow.get("createdAt"):
                try:
                    created_at = datetime.fromisoformat(
                        workflow["createdAt"].replace("Z", "+00:00")
                    )
                except (ValueError, AttributeError):
                    pass

            if workflow.get("updatedAt"):
                try:
                    updated_at = datetime.fromisoformat(
                        workflow["updatedAt"].replace("Z", "+00:00")
                    )
                except (ValueError, AttributeError):
                    pass

            # Extract tags (can be array of strings or array of objects)
            tags = []
            raw_tags = workflow.get("tags", [])
            for tag in raw_tags:
                if isinstance(tag, str):
                    tags.append(tag)
                elif isinstance(tag, dict) and "name" in tag:
                    tags.append(tag["name"])

            yield N8nWorkflowEntity(
                # Base fields
                entity_id=workflow_id,
                breadcrumbs=[],
                name=workflow_name,
                created_at=created_at,
                updated_at=updated_at,
                # API fields
                active=workflow.get("active", False),
                tags=tags,
                nodes=workflow.get("nodes", []),
                connections=workflow.get("connections", {}),
                settings=workflow.get("settings"),
                static_data=workflow.get("staticData"),
                version_id=str(workflow.get("versionId")) if workflow.get("versionId") else None,
            )

    async def _generate_execution_entities(
        self,
        client: httpx.AsyncClient,
        workflow_id: str,
        workflow_name: str,
        workflow_breadcrumb: Breadcrumb,
    ) -> AsyncGenerator[N8nExecutionEntity, None]:
        """Retrieve and yield execution entities for a specific workflow.

        Args:
            client: HTTP client for making requests
            workflow_id: ID of the workflow to fetch executions for
            workflow_name: Name of the workflow (for entity naming)
            workflow_breadcrumb: Breadcrumb to link executions to parent workflow

        Yields:
            N8nExecutionEntity objects for each execution
        """
        # Fetch executions for this workflow with limit
        params = {
            "workflowId": workflow_id,
            "limit": self.max_executions_per_workflow,
        }

        try:
            executions_data = await self._get_with_auth(client, "/executions", params=params)
        except httpx.HTTPStatusError as e:
            # If executions endpoint fails, log and skip
            self.logger.warning(
                f"Failed to fetch executions for workflow {workflow_id}: {e}. Skipping executions."
            )
            return

        # The API returns {data: [...executions...], nextCursor: ...}
        executions = executions_data.get("data", [])

        self.logger.debug(
            f"Found {len(executions)} executions for workflow '{workflow_name}' (ID: {workflow_id})"
        )

        for execution in executions:
            execution_id = str(execution["id"])

            # Parse timestamps
            started_at = None
            stopped_at = None

            if execution.get("startedAt"):
                try:
                    started_at = datetime.fromisoformat(
                        execution["startedAt"].replace("Z", "+00:00")
                    )
                except (ValueError, AttributeError):
                    pass

            if execution.get("stoppedAt"):
                try:
                    stopped_at = datetime.fromisoformat(
                        execution["stoppedAt"].replace("Z", "+00:00")
                    )
                except (ValueError, AttributeError):
                    pass

            # Extract error message if failed
            error_message = None
            if execution.get("status") == "error":
                # Error can be in data.resultData.error or data.resultData.lastNodeExecuted
                if execution.get("data"):
                    result_data = execution["data"].get("resultData", {})
                    if result_data.get("error"):
                        error_obj = result_data["error"]
                        if isinstance(error_obj, dict):
                            error_message = error_obj.get("message", str(error_obj))
                        else:
                            error_message = str(error_obj)

            # Create execution name from workflow name + timestamp
            execution_time = started_at.strftime("%Y-%m-%d %H:%M:%S") if started_at else "unknown"
            status = execution.get("status", "unknown")
            execution_name = f"{workflow_name} - {execution_time} ({status})"

            yield N8nExecutionEntity(
                # Base fields
                entity_id=execution_id,
                breadcrumbs=[workflow_breadcrumb],
                name=execution_name,
                created_at=started_at,
                updated_at=stopped_at,
                # API fields
                workflow_id=workflow_id,
                workflow_name=workflow_name,
                mode=execution.get("mode", "unknown"),
                status=status,
                started_at=started_at,
                stopped_at=stopped_at,
                finished=execution.get("finished", False),
                error_message=error_message,
                retry_of=str(execution["retryOf"]) if execution.get("retryOf") else None,
                retry_success_id=(
                    str(execution["retrySuccessId"]) if execution.get("retrySuccessId") else None
                ),
                waiting_execution=execution.get("waitingExecution"),
            )

    async def generate_entities(self) -> AsyncGenerator[BaseEntity, None]:
        """Generate all entities from n8n: Workflows and their Executions.

        For each workflow:
          - yield a N8nWorkflowEntity
          - if configured, yield N8nExecutionEntity objects for recent executions

        Yields:
            BaseEntity objects (N8nWorkflowEntity and N8nExecutionEntity)
        """
        async with self.http_client() as client:
            # Generate workflow entities
            async for workflow_entity in self._generate_workflow_entities(client):
                yield workflow_entity

                # If configured to include executions, fetch them
                if self.include_executions:
                    # Create breadcrumb for this workflow
                    workflow_breadcrumb = Breadcrumb(entity_id=workflow_entity.entity_id)

                    # Generate execution entities for this workflow
                    async for execution_entity in self._generate_execution_entities(
                        client,
                        workflow_entity.entity_id,
                        workflow_entity.name,
                        workflow_breadcrumb,
                    ):
                        yield execution_entity

    async def validate(self) -> bool:
        """Verify n8n instance is reachable and credentials are valid.

        Tests the connection by making a simple GET request to the workflows endpoint.

        Returns:
            True if connection is successful, False otherwise
        """
        try:
            async with self.http_client() as client:
                # Try to fetch workflows (lightweight test)
                await self._get_with_auth(client, "/workflows")
                self.logger.info("n8n connection validated successfully")
                return True
        except httpx.HTTPStatusError as e:
            self.logger.error(
                f"n8n validation failed with HTTP {e.response.status_code}: {e.response.text}"
            )
            return False
        except Exception as e:
            self.logger.error(f"n8n validation failed: {str(e)}")
            return False
