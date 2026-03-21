"""Jira source implementation.

Connector that retrieves Projects and Issues from a Jira Cloud instance,
with optional Zephyr Scale test management integration.

References:
    Jira REST API: https://developer.atlassian.com/cloud/jira/platform/rest/v3/intro/
    Zephyr Scale API: https://support.smartbear.com/zephyr-scale-cloud/api-docs/
"""

from __future__ import annotations

from typing import Any, AsyncGenerator, Dict, List, Optional

from tenacity import retry, stop_after_attempt

from airweave.core.logging import ContextualLogger
from airweave.core.shared_models import RateLimitLevel
from airweave.domains.browse_tree.types import NodeSelectionData
from airweave.domains.sources.exceptions import SourceAuthError
from airweave.domains.sources.token_providers.protocol import TokenProviderProtocol
from airweave.domains.storage.file_service import FileService
from airweave.domains.syncs.cursors.cursor import SyncCursor
from airweave.platform.configs.auth import JiraAuthConfig
from airweave.platform.configs.config import JiraConfig
from airweave.platform.decorators import source
from airweave.platform.entities._base import BaseEntity, Breadcrumb
from airweave.platform.entities.jira import (
    JiraIssueEntity,
    JiraProjectEntity,
    ZephyrTestCaseEntity,
    ZephyrTestCycleEntity,
    ZephyrTestPlanEntity,
)
from airweave.platform.http_client.airweave_client import AirweaveHttpClient
from airweave.platform.sources._base import BaseSource
from airweave.platform.sources.http_helpers import raise_for_status
from airweave.platform.sources.retry_helpers import (
    retry_if_rate_limit_or_timeout,
    wait_rate_limit_with_backoff,
)
from airweave.schemas.source_connection import AuthenticationMethod, OAuthType

ATLASSIAN_ACCESSIBLE_RESOURCES_URL = "https://api.atlassian.com/oauth/token/accessible-resources"
ZEPHYR_SCALE_BASE_URL = "https://api.zephyrscale.smartbear.com/v2"


@source(
    name="Jira",
    short_name="jira",
    auth_methods=[
        AuthenticationMethod.OAUTH_BROWSER,
        AuthenticationMethod.OAUTH_TOKEN,
        AuthenticationMethod.AUTH_PROVIDER,
    ],
    oauth_type=OAuthType.WITH_ROTATING_REFRESH,
    auth_config_class=JiraAuthConfig,
    config_class=JiraConfig,
    labels=["Project Management", "Issue Tracking", "Test Management"],
    supports_continuous=False,
    rate_limit_level=RateLimitLevel.ORG,
)
class JiraSource(BaseSource):
    """Jira source connector integrates with the Jira REST API to extract project management data.

    Connects to your Jira Cloud instance. Optionally integrates with Zephyr Scale
    for test management entities (test cases, test cycles, test plans) when a
    Zephyr Scale API token is provided.

    It provides comprehensive access to projects, issues, and their
    relationships for agile development and issue tracking workflows.
    """

    @classmethod
    async def create(
        cls,
        *,
        auth: TokenProviderProtocol,
        logger: ContextualLogger,
        http_client: AirweaveHttpClient,
        config: JiraConfig,
    ) -> JiraSource:
        """Create a new Jira source instance."""
        instance = cls(auth=auth, logger=logger, http_client=http_client)
        instance.site_url: Optional[str] = None
        instance._project_keys: list[str] = config.project_keys if config else []
        instance.zephyr_api_token: Optional[str] = config.zephyr_scale_api_token if config else None
        return instance

    # ------------------------------------------------------------------
    # HTTP helpers
    # ------------------------------------------------------------------

    async def _authed_headers(self) -> Dict[str, str]:
        """Build Authorization + Accept + CSRF headers with a fresh token."""
        token = await self.auth.get_token()
        return {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "X-Atlassian-Token": "no-check",
        }

    async def _refresh_and_get_headers(self) -> Dict[str, str]:
        """Force-refresh the token and return updated headers."""
        new_token = await self.auth.force_refresh()
        return {
            "Authorization": f"Bearer {new_token}",
            "Accept": "application/json",
            "X-Atlassian-Token": "no-check",
        }

    async def _get_accessible_resources(self) -> list[dict]:
        """Get the list of accessible Atlassian resources for this token."""
        self.logger.debug("Retrieving accessible Atlassian resources")
        resources = await self._get(ATLASSIAN_ACCESSIBLE_RESOURCES_URL)
        self.logger.debug(f"Found {len(resources)} accessible Atlassian resources")
        return resources

    @retry(
        stop=stop_after_attempt(5),
        retry=retry_if_rate_limit_or_timeout,
        wait=wait_rate_limit_with_backoff,
        reraise=True,
    )
    async def _get(self, url: str) -> Any:
        """Make an authenticated GET request to the Jira REST API.

        Uses OAuth 2.0 with rotating refresh tokens.  On 401, attempts a
        single token refresh before letting ``raise_for_status`` translate
        the response into a ``SourceAuthError``.
        """
        headers = await self._authed_headers()
        response = await self.http_client.get(url, headers=headers)

        if response.status_code == 401 and self.auth.supports_refresh:
            self.logger.warning("Received 401 from Jira — attempting token refresh")
            headers = await self._refresh_and_get_headers()
            response = await self.http_client.get(url, headers=headers)

        raise_for_status(
            response,
            source_short_name=self.short_name,
            token_provider_kind=self.auth.provider_kind,
        )
        return response.json()

    @retry(
        stop=stop_after_attempt(5),
        retry=retry_if_rate_limit_or_timeout,
        wait=wait_rate_limit_with_backoff,
        reraise=True,
    )
    async def _post(self, url: str, json_data: Dict[str, Any]) -> Any:
        """Make an authenticated POST request to the Jira REST API."""
        headers = await self._authed_headers()
        headers["Content-Type"] = "application/json"

        response = await self.http_client.post(url, headers=headers, json=json_data)

        if response.status_code == 401 and self.auth.supports_refresh:
            self.logger.warning("Received 401 from Jira POST — attempting token refresh")
            headers = await self._refresh_and_get_headers()
            headers["Content-Type"] = "application/json"
            response = await self.http_client.post(url, headers=headers, json=json_data)

        raise_for_status(
            response,
            source_short_name=self.short_name,
            token_provider_kind=self.auth.provider_kind,
        )
        return response.json()

    @retry(
        stop=stop_after_attempt(5),
        retry=retry_if_rate_limit_or_timeout,
        wait=wait_rate_limit_with_backoff,
        reraise=True,
    )
    async def _get_zephyr(self, url: str) -> Any:
        """Make an authenticated GET request to the Zephyr Scale API.

        Zephyr Scale uses a separate API token, not the Jira OAuth token.
        """
        if not self.zephyr_api_token:
            raise ValueError("Zephyr Scale API token not configured")

        headers = {
            "Authorization": f"Bearer {self.zephyr_api_token}",
            "Accept": "application/json",
        }

        response = await self.http_client.get(url, headers=headers)

        raise_for_status(
            response,
            source_short_name=self.short_name,
            token_provider_kind="zephyr_api_key",
        )
        return response.json()

    # ------------------------------------------------------------------
    # Entity generators
    # ------------------------------------------------------------------

    def _build_project_url(self, project_key: str) -> Optional[str]:
        if not self.site_url:
            return None
        return f"{self.site_url}/projects/{project_key}"

    async def _generate_project_entities(
        self,
    ) -> AsyncGenerator[JiraProjectEntity, None]:
        """Generate JiraProjectEntity objects."""
        self.logger.info("Starting project entity generation")

        project_keys_filter = self._project_keys
        if not project_keys_filter:
            raise ValueError(
                "Project keys configuration is required. Please specify which Jira projects "
                "to sync by editing the source connection details."
            )

        project_keys_filter = [key.upper() for key in project_keys_filter]
        project_keys_filter_set = set(project_keys_filter)

        self.logger.info(f"Project filter: will sync only projects with keys {project_keys_filter}")

        search_api_path = "/rest/api/3/project/search"
        max_results = 50
        start_at = 0
        page = 1
        total_projects = 0
        filtered_projects = 0
        found_project_keys: set[str] = set()

        while True:
            project_search_url = (
                f"{self.base_url}{search_api_path}?startAt={start_at}&maxResults={max_results}"
            )
            self.logger.info(f"Fetching project page {page} from {project_search_url}")

            data = await self._get(project_search_url)
            projects = data.get("values", [])
            self.logger.info(f"Retrieved {len(projects)} projects on page {page}")

            for project in projects:
                total_projects += 1
                project_key = project.get("key")

                if project_keys_filter and project_key not in project_keys_filter_set:
                    filtered_projects += 1
                    self.logger.debug(f"Skipping project {project_key} - not in filter list")
                    continue

                found_project_keys.add(project_key)

                project_id = str(project["id"])
                project_name = project.get("name") or project["key"]
                yield JiraProjectEntity(
                    entity_id=project_id,
                    breadcrumbs=[],
                    name=project_name,
                    created_at=None,
                    updated_at=None,
                    project_id=project_id,
                    project_name=project_name,
                    project_key=project["key"],
                    description=project.get("description"),
                    web_url_value=self._build_project_url(project["key"]),
                )

            if data.get("isLast", True):
                matched_count = total_projects - filtered_projects
                missing_keys = project_keys_filter_set - found_project_keys
                if missing_keys:
                    self.logger.warning(
                        f"Some requested projects were not found or not accessible: "
                        f"{sorted(missing_keys)}"
                    )
                if matched_count == 0:
                    self.logger.warning(
                        f"No projects matched the filter! Requested: {project_keys_filter}, "
                        f"but none were found."
                    )
                else:
                    self.logger.info(
                        f"Completed project sync: {matched_count} project(s) included "
                        f"({filtered_projects} filtered out). "
                        f"Found: {sorted(found_project_keys)}"
                    )
                break

            start_at = data.get("startAt", 0) + max_results
            page += 1

    async def _generate_issue_entities(
        self, project: JiraProjectEntity
    ) -> AsyncGenerator[JiraIssueEntity, None]:
        """Generate JiraIssueEntity for each issue in the given project using JQL search."""
        project_key = project.project_key
        self.logger.info(
            f"Starting issue entity generation for project: {project_key} ({project.name})"
        )

        project_breadcrumb = Breadcrumb(
            entity_id=project.project_id,
            name=project.project_name,
            entity_type=JiraProjectEntity.__name__,
        )

        search_url = f"{self.base_url}/rest/api/3/search/jql"
        max_results = 50
        next_page_token = None

        while True:
            search_body: Dict[str, Any] = {
                "jql": f"project = {project_key}",
                "maxResults": max_results,
                "fields": ["summary", "description", "status", "issuetype", "created", "updated"],
            }
            if next_page_token:
                search_body["nextPageToken"] = next_page_token

            self.logger.info(f"Fetching issues for project {project_key}")
            data = await self._post(search_url, search_body)

            total = data.get("total", 0)
            issues = data.get("issues", [])
            self.logger.info(f"Found {len(issues)} issues (total available: {total})")

            for issue_data in issues:
                yield JiraIssueEntity.from_api(
                    issue_data,
                    project_breadcrumb=project_breadcrumb,
                    project_key=project_key,
                    site_url=self.site_url,
                )

            is_last = data.get("isLast", True)
            next_page_token = data.get("nextPageToken")

            if is_last or not next_page_token:
                self.logger.info(f"Completed fetching all issues for project {project_key}")
                break

    # ------------------------------------------------------------------
    # Zephyr Scale integration
    # ------------------------------------------------------------------

    def _is_zephyr_enabled(self) -> bool:
        """Check if Zephyr Scale integration is enabled and configured."""
        return bool(self.zephyr_api_token)

    async def _generate_zephyr_test_case_entities(
        self, project: JiraProjectEntity
    ) -> AsyncGenerator[ZephyrTestCaseEntity, None]:
        """Generate ZephyrTestCaseEntity objects for a project."""
        project_key = project.project_key
        project_breadcrumb = Breadcrumb(
            entity_id=project.project_id,
            name=project.project_name,
            entity_type=JiraProjectEntity.__name__,
        )
        self.logger.info(f"Fetching Zephyr Scale test cases for project: {project_key}")

        max_results = 100
        start_at = 0
        total_fetched = 0

        while True:
            url = (
                f"{ZEPHYR_SCALE_BASE_URL}/testcases"
                f"?projectKey={project_key}&maxResults={max_results}&startAt={start_at}"
            )

            try:
                data = await self._get_zephyr(url)
            except SourceAuthError:
                raise
            except Exception as e:
                if hasattr(e, "status_code") and e.status_code == 404:
                    self.logger.warning(
                        f"Zephyr Scale not found for project {project_key} - "
                        "may not have Zephyr Scale enabled"
                    )
                    return
                raise

            values = data.get("values", [])
            self.logger.info(f"Retrieved {len(values)} test cases for project {project_key}")

            for test_case_data in values:
                total_fetched += 1
                yield ZephyrTestCaseEntity.from_api(
                    test_case_data,
                    project_breadcrumb=project_breadcrumb,
                    project_key=project_key,
                    site_url=self.site_url,
                )

            if data.get("isLast", True) or not values:
                self.logger.info(
                    f"Completed fetching {total_fetched} test cases for project {project_key}"
                )
                break

            start_at += max_results

    async def _generate_zephyr_test_cycle_entities(
        self, project: JiraProjectEntity
    ) -> AsyncGenerator[ZephyrTestCycleEntity, None]:
        """Generate ZephyrTestCycleEntity objects for a project."""
        project_key = project.project_key
        project_breadcrumb = Breadcrumb(
            entity_id=project.project_id,
            name=project.project_name,
            entity_type=JiraProjectEntity.__name__,
        )
        self.logger.info(f"Fetching Zephyr Scale test cycles for project: {project_key}")

        max_results = 100
        start_at = 0
        total_fetched = 0

        while True:
            url = (
                f"{ZEPHYR_SCALE_BASE_URL}/testcycles"
                f"?projectKey={project_key}&maxResults={max_results}&startAt={start_at}"
            )

            try:
                data = await self._get_zephyr(url)
            except SourceAuthError:
                raise
            except Exception as e:
                if hasattr(e, "status_code") and e.status_code == 404:
                    self.logger.warning(
                        f"Zephyr Scale test cycles not found for project {project_key}"
                    )
                    return
                raise

            values = data.get("values", [])
            self.logger.info(f"Retrieved {len(values)} test cycles for project {project_key}")

            for test_cycle_data in values:
                total_fetched += 1
                yield ZephyrTestCycleEntity.from_api(
                    test_cycle_data,
                    project_breadcrumb=project_breadcrumb,
                    project_key=project_key,
                    site_url=self.site_url,
                )

            if data.get("isLast", True) or not values:
                self.logger.info(
                    f"Completed fetching {total_fetched} test cycles for project {project_key}"
                )
                break

            start_at += max_results

    async def _generate_zephyr_test_plan_entities(
        self, project: JiraProjectEntity
    ) -> AsyncGenerator[ZephyrTestPlanEntity, None]:
        """Generate ZephyrTestPlanEntity objects for a project."""
        project_key = project.project_key
        project_breadcrumb = Breadcrumb(
            entity_id=project.project_id,
            name=project.project_name,
            entity_type=JiraProjectEntity.__name__,
        )
        self.logger.info(f"Fetching Zephyr Scale test plans for project: {project_key}")

        max_results = 100
        start_at = 0
        total_fetched = 0

        while True:
            url = (
                f"{ZEPHYR_SCALE_BASE_URL}/testplans"
                f"?projectKey={project_key}&maxResults={max_results}&startAt={start_at}"
            )

            try:
                data = await self._get_zephyr(url)
            except SourceAuthError:
                raise
            except Exception as e:
                if hasattr(e, "status_code") and e.status_code == 404:
                    self.logger.warning(
                        f"Zephyr Scale test plans not found for project {project_key}"
                    )
                    return
                raise

            values = data.get("values", [])
            self.logger.info(f"Retrieved {len(values)} test plans for project {project_key}")

            for test_plan_data in values:
                total_fetched += 1
                yield ZephyrTestPlanEntity.from_api(
                    test_plan_data,
                    project_breadcrumb=project_breadcrumb,
                    project_key=project_key,
                    site_url=self.site_url,
                )

            if data.get("isLast", True) or not values:
                self.logger.info(
                    f"Completed fetching {total_fetched} test plans for project {project_key}"
                )
                break

            start_at += max_results

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def generate_entities(  # noqa: C901
        self,
        *,
        cursor: SyncCursor | None = None,
        files: FileService | None = None,
        node_selections: list[NodeSelectionData] | None = None,
    ) -> AsyncGenerator[BaseEntity, None]:
        """Generate all entities from Jira and optionally Zephyr Scale."""
        self.logger.info("Starting Jira entity generation process")

        resources = await self._get_accessible_resources()
        if not resources:
            raise ValueError("No accessible resources found")
        cloud_id = resources[0]["id"]
        self.site_url = resources[0].get("url")
        if self.site_url:
            self.site_url = self.site_url.rstrip("/")
        else:
            self.logger.warning("Accessible Jira resource missing site URL; web links disabled.")

        self.base_url = f"https://api.atlassian.com/ex/jira/{cloud_id}"
        self.logger.debug(f"Base URL set to: {self.base_url}")

        zephyr_enabled = self._is_zephyr_enabled()
        if zephyr_enabled:
            self.logger.info(
                "Zephyr Scale integration ENABLED - API token configured, will sync test entities"
            )
        else:
            self.logger.info(
                "Zephyr Scale integration DISABLED - "
                "no API token in config (feature flag may be off or token not provided)"
            )

        project_count = 0
        issue_count = 0
        zephyr_test_case_count = 0
        zephyr_test_cycle_count = 0
        zephyr_test_plan_count = 0

        processed_entities: set[tuple] = set()
        projects: List[JiraProjectEntity] = []

        async for project_entity in self._generate_project_entities():
            project_count += 1
            project_identifier = (project_entity.entity_id, project_entity.project_key)

            if project_identifier in processed_entities:
                self.logger.warning(
                    f"Skipping duplicate project: {project_entity.project_key} "
                    f"(ID: {project_entity.entity_id})"
                )
                continue

            processed_entities.add(project_identifier)
            projects.append(project_entity)
            self.logger.info(
                f"Yielding project entity: {project_entity.project_key} ({project_entity.name})"
            )
            yield project_entity

            project_issue_count = 0
            async for issue_entity in self._generate_issue_entities(project_entity):
                issue_identifier = (issue_entity.entity_id, issue_entity.issue_key)

                if issue_identifier in processed_entities:
                    self.logger.warning(
                        f"Skipping duplicate issue: {issue_entity.issue_key} "
                        f"(ID: {issue_entity.entity_id})"
                    )
                    continue

                processed_entities.add(issue_identifier)
                issue_count += 1
                project_issue_count += 1
                self.logger.info(f"Yielding issue entity: {issue_entity.issue_key}")
                yield issue_entity

            self.logger.info(
                f"Completed {project_issue_count} issues for project {project_entity.project_key}"
            )

        self.logger.info(
            f"Completed Jira entity generation: {project_count} projects, "
            f"{issue_count} issues total"
        )

        if zephyr_enabled:
            self.logger.info("Starting Zephyr Scale entity generation")

            for project in projects:
                async for test_case in self._generate_zephyr_test_case_entities(project):
                    tc_identifier = (test_case.entity_id, test_case.test_case_key)
                    if tc_identifier not in processed_entities:
                        processed_entities.add(tc_identifier)
                        zephyr_test_case_count += 1
                        yield test_case

                async for test_cycle in self._generate_zephyr_test_cycle_entities(project):
                    tcyc_identifier = (test_cycle.entity_id, test_cycle.test_cycle_key)
                    if tcyc_identifier not in processed_entities:
                        processed_entities.add(tcyc_identifier)
                        zephyr_test_cycle_count += 1
                        yield test_cycle

                async for test_plan in self._generate_zephyr_test_plan_entities(project):
                    tp_identifier = (test_plan.entity_id, test_plan.test_plan_key)
                    if tp_identifier not in processed_entities:
                        processed_entities.add(tp_identifier)
                        zephyr_test_plan_count += 1
                        yield test_plan

            self.logger.info(
                f"Completed Zephyr Scale entity generation: "
                f"{zephyr_test_case_count} test cases, "
                f"{zephyr_test_cycle_count} test cycles, "
                f"{zephyr_test_plan_count} test plans"
            )

    async def validate(self) -> None:
        """Verify Jira OAuth2 token by calling accessible-resources endpoint."""
        resources = await self._get_accessible_resources()
        if not resources:
            raise SourceAuthError("Jira validation failed: no accessible resources found")
