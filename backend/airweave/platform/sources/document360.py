"""Document360 source implementation.

Syncs Project Versions, Categories, and Articles from Document360 knowledge bases.
API reference: https://apidocs.document360.com/apidocs/getting-started
Authentication: API token (header api_token).
"""

from __future__ import annotations

from typing import Any, AsyncGenerator, Dict, List, Optional

from tenacity import retry, stop_after_attempt, wait_exponential

from airweave.core.logging import ContextualLogger
from airweave.domains.browse_tree.types import NodeSelectionData
from airweave.domains.sources.exceptions import SourceAuthError
from airweave.domains.sources.token_providers.protocol import AuthProviderKind, SourceAuthProvider
from airweave.domains.storage.file_service import FileService
from airweave.domains.syncs.cursors.cursor import SyncCursor
from airweave.platform.configs.auth import Document360AuthConfig
from airweave.platform.configs.config import Document360Config
from airweave.platform.decorators import source
from airweave.platform.entities._base import BaseEntity, Breadcrumb
from airweave.platform.entities.document360 import (
    Document360ArticleEntity,
    Document360CategoryEntity,
    Document360ProjectVersionEntity,
)
from airweave.platform.http_client.airweave_client import AirweaveHttpClient
from airweave.platform.sources._base import BaseSource
from airweave.platform.sources.http_helpers import raise_for_status
from airweave.schemas.source_connection import AuthenticationMethod

DEFAULT_BASE_URL = "https://apihub.document360.io"
API_PATH_PREFIX = "/v2"


@source(
    name="Document360",
    short_name="document360",
    auth_methods=[
        AuthenticationMethod.DIRECT,
        AuthenticationMethod.AUTH_PROVIDER,
    ],
    oauth_type=None,
    auth_config_class=Document360AuthConfig,
    config_class=Document360Config,
    labels=["Documentation", "Knowledge Base"],
    supports_continuous=False,
)
class Document360Source(BaseSource):
    """Document360 source connector.

    Syncs project versions, categories, and articles from Document360
    knowledge bases. Uses API token authentication.
    """

    @classmethod
    async def create(
        cls,
        *,
        auth: SourceAuthProvider,
        logger: ContextualLogger,
        http_client: AirweaveHttpClient,
        config: Document360Config,
    ) -> Document360Source:
        """Create and configure the source."""
        instance = cls(auth=auth, logger=logger, http_client=http_client)
        if auth.provider_kind == AuthProviderKind.CREDENTIAL:
            instance._api_token = auth.credentials.api_token
        else:
            instance._api_token = await auth.get_token()
        instance._base_url = (config.base_url or DEFAULT_BASE_URL).rstrip("/")
        instance._lang_code = config.lang_code or "en"
        return instance

    def _api_url(self, path: str) -> str:
        """Build full API URL. path should start with /."""
        p = path if path.startswith("/") else f"/{path}"
        if not p.startswith(API_PATH_PREFIX):
            p = f"{API_PATH_PREFIX}{p}"
        return f"{self._base_url}{p}"

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True,
    )
    async def _get(
        self,
        path: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Make authenticated GET request. path is e.g. /v2/ProjectVersions."""
        url = self._api_url(path)
        headers = {"api_token": self._api_token, "Accept": "application/json"}
        response = await self.http_client.get(url, headers=headers, params=params, timeout=30.0)

        if response.status_code == 401 and self.auth.supports_refresh:
            self._api_token = await self.auth.force_refresh()
            headers = {"api_token": self._api_token, "Accept": "application/json"}
            response = await self.http_client.get(url, headers=headers, params=params, timeout=30.0)

        raise_for_status(
            response,
            source_short_name=self.short_name,
            token_provider_kind=self.auth.provider_kind,
        )

        data = response.json()
        if not data.get("success", True):
            errors = data.get("errors") or []
            msg = (
                "; ".join(e.get("description", str(e)) for e in errors if isinstance(e, dict))
                or "Unknown API error"
            )
            raise ValueError(f"Document360 API error: {msg}")
        return data

    async def _fetch_project_versions(self) -> List[Dict[str, Any]]:
        """Fetch list of project versions."""
        data = await self._get("/ProjectVersions")
        raw = data.get("data")
        return raw if isinstance(raw, list) else []

    async def _fetch_categories_tree(self, project_version_id: str) -> List[Dict[str, Any]]:
        """Fetch categories tree for a project version (includes nested categories and articles)."""
        data = await self._get(
            f"/ProjectVersions/{project_version_id}/categories",
            params={"includeCategoryDescription": "true"},
        )
        raw = data.get("data")
        return raw if isinstance(raw, list) else []

    async def _fetch_article_by_version(
        self,
        article_id: str,
        lang_code: str,
        version_number: int,
    ) -> Optional[Dict[str, Any]]:
        """Fetch full article content by version."""
        path = f"/Articles/{article_id}/{lang_code}/versions/{version_number}"
        try:
            data = await self._get(path)
            return data.get("data") if isinstance(data.get("data"), dict) else None
        except SourceAuthError:
            raise
        except Exception:
            return None

    async def generate_entities(
        self,
        *,
        cursor: SyncCursor | None = None,
        files: FileService | None = None,
        node_selections: list[NodeSelectionData] | None = None,
    ) -> AsyncGenerator[BaseEntity, None]:
        """Generate project versions, categories, and articles."""
        self.logger.info("Starting Document360 sync")
        versions = await self._fetch_project_versions()
        for v in versions:
            version_id = v.get("id")
            if not version_id:
                continue
            version_entity = Document360ProjectVersionEntity.from_api(v)
            yield version_entity

            version_breadcrumb = Breadcrumb(
                entity_id=version_entity.id,
                name=version_entity.name,
                entity_type="Document360ProjectVersionEntity",
            )

            categories = await self._fetch_categories_tree(version_id)
            async for entity in self._yield_categories_and_articles(
                categories,
                version_entity.id,
                version_entity.name,
                [version_breadcrumb],
                [],
            ):
                yield entity
        self.logger.info("Document360 sync completed")

    async def _yield_categories_and_articles(
        self,
        categories: List[Dict[str, Any]],
        project_version_id: str,
        project_version_name: str,
        parent_breadcrumbs: List[Breadcrumb],
        parent_category_names: List[str],
    ) -> AsyncGenerator[BaseEntity, None]:
        """Recursively yield category and article entities from the category tree."""
        for cat in categories:
            cat_id = cat.get("id")
            if not cat_id:
                continue
            category_entity = Document360CategoryEntity.from_api(
                cat,
                project_version_id=project_version_id,
                project_version_name=project_version_name,
                breadcrumbs=parent_breadcrumbs,
            )
            yield category_entity

            cat_breadcrumbs = parent_breadcrumbs + [
                Breadcrumb(
                    entity_id=category_entity.id,
                    name=category_entity.name,
                    entity_type="Document360CategoryEntity",
                )
            ]

            for art in cat.get("articles") or []:
                article_id = art.get("id")
                if not article_id:
                    continue
                version_num = art.get("public_version") or art.get("latest_version") or 1
                full_article = await self._fetch_article_by_version(
                    article_id, self._lang_code, int(version_num)
                )
                yield Document360ArticleEntity.from_api(
                    art,
                    detail=full_article,
                    category_id=category_entity.id,
                    category_name=category_entity.name,
                    project_version_id=project_version_id,
                    project_version_name=project_version_name,
                    breadcrumbs=cat_breadcrumbs,
                    lang_code=self._lang_code,
                )

            child_cats = cat.get("child_categories") or []
            if child_cats:
                async for e in self._yield_categories_and_articles(
                    child_cats,
                    project_version_id,
                    project_version_name,
                    cat_breadcrumbs,
                    parent_category_names + [category_entity.name],
                ):
                    yield e

    async def validate(self) -> None:
        """Verify API token by fetching project versions."""
        await self._get("/ProjectVersions")
