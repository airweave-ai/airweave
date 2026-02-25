"""Document360 source implementation.

Syncs Project Versions, Categories, and Articles from Document360 knowledge bases.
API reference: https://apidocs.document360.com/apidocs/getting-started
Authentication: API token (header api_token).
"""

from datetime import datetime
from typing import Any, AsyncGenerator, Dict, List, Optional

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from airweave.platform.configs.auth import Document360AuthConfig
from airweave.platform.configs.config import Document360Config
from airweave.platform.decorators import source
from airweave.platform.entities._base import BaseEntity, Breadcrumb
from airweave.platform.entities.document360 import (
    Document360ArticleEntity,
    Document360CategoryEntity,
    Document360ProjectVersionEntity,
)
from airweave.platform.sources._base import BaseSource
from airweave.schemas.source_connection import AuthenticationMethod

DEFAULT_BASE_URL = "https://apihub.document360.io"
API_PATH_PREFIX = "/v2"


def _parse_iso_datetime(value: Optional[str]) -> Optional[datetime]:
    """Parse ISO 8601 datetime string to datetime."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


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
        credentials: Document360AuthConfig,
        config: Optional[Dict[str, Any]] = None,
    ) -> "Document360Source":
        """Create and configure the source.

        Args:
            credentials: Document360AuthConfig with api_token.
            config: Optional config with base_url, lang_code.

        Returns:
            Configured Document360Source instance.
        """
        instance = cls()
        instance.api_token = credentials.api_token
        instance.base_url = (config or {}).get("base_url") or DEFAULT_BASE_URL
        instance.base_url = instance.base_url.rstrip("/")
        instance.lang_code = (config or {}).get("lang_code", "en")
        return instance

    def _api_url(self, path: str) -> str:
        """Build full API URL. path should start with /."""
        p = path if path.startswith("/") else f"/{path}"
        if not p.startswith(API_PATH_PREFIX):
            p = f"{API_PATH_PREFIX}{p}"
        return f"{self.base_url}{p}"

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True,
    )
    async def _get_with_auth(
        self,
        client: httpx.AsyncClient,
        path: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Make authenticated GET request. path is e.g. /v2/ProjectVersions."""
        url = self._api_url(path)
        headers = {"api_token": self.api_token, "Accept": "application/json"}
        response = await client.get(url, headers=headers, params=params, timeout=30.0)
        response.raise_for_status()
        data = response.json()
        if not data.get("success", True):
            errors = data.get("errors") or []
            msg = (
                "; ".join(e.get("description", str(e)) for e in errors if isinstance(e, dict))
                or "Unknown API error"
            )
            raise ValueError(f"Document360 API error: {msg}")
        return data

    async def _fetch_project_versions(self, client: httpx.AsyncClient) -> List[Dict[str, Any]]:
        """Fetch list of project versions."""
        data = await self._get_with_auth(client, "/ProjectVersions")
        raw = data.get("data")
        return raw if isinstance(raw, list) else []

    async def _fetch_categories_tree(
        self, client: httpx.AsyncClient, project_version_id: str
    ) -> List[Dict[str, Any]]:
        """Fetch categories tree for a project version (includes nested categories and articles)."""
        data = await self._get_with_auth(
            client,
            f"/ProjectVersions/{project_version_id}/categories",
            params={"includeCategoryDescription": "true"},
        )
        raw = data.get("data")
        return raw if isinstance(raw, list) else []

    async def _fetch_article_by_version(
        self,
        client: httpx.AsyncClient,
        article_id: str,
        lang_code: str,
        version_number: int,
    ) -> Optional[Dict[str, Any]]:
        """Fetch full article content by version."""
        path = f"/Articles/{article_id}/{lang_code}/versions/{version_number}"
        try:
            data = await self._get_with_auth(client, path)
            return data.get("data") if isinstance(data.get("data"), dict) else None
        except httpx.HTTPStatusError:
            return None

    async def generate_entities(self) -> AsyncGenerator[BaseEntity, None]:
        """Generate project versions, categories, and articles."""
        self.logger.info("Starting Document360 sync")
        async with self.http_client() as client:
            versions = await self._fetch_project_versions(client)
            for v in versions:
                version_id = v.get("id")
                if not version_id:
                    continue
                version_name = (
                    v.get("version_code_name")
                    or (str(v["version_number"]) if v.get("version_number") is not None else None)
                    or version_id
                )
                version_entity = Document360ProjectVersionEntity(
                    entity_id=version_id,
                    breadcrumbs=[],
                    id=version_id,
                    name=str(version_name),
                    version_number=v.get("version_number"),
                    version_code_name=v.get("version_code_name"),
                    is_main_version=v.get("is_main_version", False),
                    is_public=v.get("is_public", True),
                    is_beta=v.get("is_beta", False),
                    is_deprecated=v.get("is_deprecated", False),
                    created_at=_parse_iso_datetime(v.get("created_at")),
                    modified_at=_parse_iso_datetime(v.get("modified_at")),
                    slug=v.get("slug"),
                    order=v.get("order"),
                    version_type=v.get("version_type"),
                )
                yield version_entity

                version_breadcrumb = Breadcrumb(
                    entity_id=version_id,
                    name=str(version_name),
                    entity_type="Document360ProjectVersionEntity",
                )

                categories = await self._fetch_categories_tree(client, version_id)
                async for entity in self._yield_categories_and_articles(
                    client,
                    categories,
                    version_id,
                    str(version_name),
                    [version_breadcrumb],
                    [],
                ):
                    yield entity
        self.logger.info("Document360 sync completed")

    async def _yield_categories_and_articles(
        self,
        client: httpx.AsyncClient,
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
            cat_name = cat.get("name") or "Unnamed category"
            cat_breadcrumbs = parent_breadcrumbs + [
                Breadcrumb(
                    entity_id=cat_id,
                    name=cat_name,
                    entity_type="Document360CategoryEntity",
                )
            ]
            category_entity = Document360CategoryEntity(
                entity_id=cat_id,
                breadcrumbs=parent_breadcrumbs,
                id=cat_id,
                name=cat_name,
                description=cat.get("description"),
                project_version_id=project_version_id,
                project_version_name=project_version_name,
                parent_category_id=cat.get("parent_category_id"),
                order=cat.get("order"),
                slug=cat.get("slug"),
                category_type=cat.get("category_type"),
                hidden=cat.get("hidden", False),
                created_at=_parse_iso_datetime(cat.get("created_at")),
                modified_at=_parse_iso_datetime(cat.get("modified_at")),
            )
            yield category_entity

            for art in cat.get("articles") or []:
                article_id = art.get("id")
                if not article_id:
                    continue
                version_num = art.get("public_version") or art.get("latest_version") or 1
                full_article = await self._fetch_article_by_version(
                    client, article_id, self.lang_code, int(version_num)
                )
                content = None
                html_content = None
                authors = []
                created_at = None
                modified_at = None
                description = None
                if full_article:
                    content = full_article.get("content")
                    html_content = full_article.get("html_content")
                    authors = full_article.get("authors") or []
                    created_at = _parse_iso_datetime(full_article.get("created_at"))
                    modified_at = _parse_iso_datetime(full_article.get("modified_at"))
                    description = full_article.get("description")

                title = (
                    art.get("title") or full_article.get("title")
                    if full_article
                    else "Unnamed article"
                )
                article_url = art.get("url")
                article_entity = Document360ArticleEntity(
                    entity_id=article_id,
                    breadcrumbs=cat_breadcrumbs,
                    id=article_id,
                    name=title,
                    content=content,
                    html_content=html_content,
                    description=description,
                    category_id=cat_id,
                    category_name=cat_name,
                    project_version_id=project_version_id,
                    project_version_name=project_version_name,
                    slug=art.get("slug") or (full_article.get("slug") if full_article else None),
                    status=art.get("status")
                    or (full_article.get("status") if full_article else None),
                    language_code=art.get("language_code") or self.lang_code,
                    public_version=art.get("public_version"),
                    latest_version=art.get("latest_version"),
                    authors=authors,
                    created_at=created_at or _parse_iso_datetime(art.get("modified_at")),
                    modified_at=modified_at or _parse_iso_datetime(art.get("modified_at")),
                    article_url=article_url,
                    web_url_value=article_url,
                )
                yield article_entity

            child_cats = cat.get("child_categories") or []
            if child_cats:
                async for e in self._yield_categories_and_articles(
                    client,
                    child_cats,
                    project_version_id,
                    project_version_name,
                    cat_breadcrumbs,
                    parent_category_names + [cat_name],
                ):
                    yield e

    async def validate(self) -> bool:
        """Verify API token by fetching project versions."""
        if not getattr(self, "api_token", None):
            self.logger.error("Document360 validation failed: missing API token")
            return False
        try:
            async with self.http_client(timeout=10.0) as client:
                await self._get_with_auth(client, "/ProjectVersions")
                return True
        except httpx.HTTPStatusError as e:
            self.logger.error(
                f"Document360 validation failed: HTTP {e.response.status_code} - "
                f"{e.response.text[:200]}"
            )
            return False
        except Exception as e:
            self.logger.error(f"Document360 validation failed: {e}")
            return False
