"""Unit tests for Document360 source and entities."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

import httpx

from airweave.domains.sources.token_providers.credential import DirectCredentialProvider
from airweave.platform.configs.auth import Document360AuthConfig
from airweave.platform.configs.config import Document360Config
from airweave.platform.entities.document360 import (
    Document360ArticleEntity,
    Document360CategoryEntity,
    Document360ProjectVersionEntity,
)
from airweave.platform.entities.document360 import _parse_dt as _parse_iso_datetime
from airweave.platform.sources.document360 import (
    DEFAULT_BASE_URL,
    Document360Source,
)

# Document360AuthConfig requires api_token min length 10
VALID_API_TOKEN = "test-token-12"


def _mock_logger():
    return MagicMock()


def _mock_http_client():
    return AsyncMock()


async def _make_source(
    *,
    api_token: str = "test-token-12345",
    config: Document360Config | None = None,
):
    creds = Document360AuthConfig(api_token=api_token)
    auth = DirectCredentialProvider(creds, source_short_name="document360")
    return await Document360Source.create(
        auth=auth,
        logger=_mock_logger(),
        http_client=_mock_http_client(),
        config=config or Document360Config(),
    )


# ---------------------------------------------------------------------------
# Entity schema tests
# ---------------------------------------------------------------------------


class TestDocument360ProjectVersionEntity:
    """Tests for Document360ProjectVersionEntity."""

    def test_web_url_returns_value_when_set(self):
        entity = Document360ProjectVersionEntity(
            entity_id="pv-1",
            breadcrumbs=[],
            id="pv-1",
            name="v1",
            web_url_value="https://docs.example.com",
        )
        assert entity.web_url == "https://docs.example.com"

    def test_web_url_returns_empty_when_not_set(self):
        entity = Document360ProjectVersionEntity(
            entity_id="pv-1",
            breadcrumbs=[],
            id="pv-1",
            name="v1",
        )
        assert entity.web_url == ""


class TestDocument360CategoryEntity:
    """Tests for Document360CategoryEntity."""

    def test_web_url_returns_value_when_set(self):
        entity = Document360CategoryEntity(
            entity_id="cat-1",
            breadcrumbs=[],
            id="cat-1",
            name="Getting started",
            web_url_value="https://docs.example.com/cat",
        )
        assert entity.web_url == "https://docs.example.com/cat"


class TestDocument360ArticleEntity:
    """Tests for Document360ArticleEntity."""

    def test_web_url_prefers_web_url_value(self):
        entity = Document360ArticleEntity(
            entity_id="art-1",
            breadcrumbs=[],
            id="art-1",
            name="Article",
            web_url_value="https://docs.example.com/article",
            article_url="https://other.com/article",
        )
        assert entity.web_url == "https://docs.example.com/article"

    def test_web_url_falls_back_to_article_url(self):
        entity = Document360ArticleEntity(
            entity_id="art-1",
            breadcrumbs=[],
            id="art-1",
            name="Article",
            article_url="https://docs.example.com/article",
        )
        assert entity.web_url == "https://docs.example.com/article"


# ---------------------------------------------------------------------------
# _parse_iso_datetime
# ---------------------------------------------------------------------------


def test_parse_iso_datetime_valid():
    assert _parse_iso_datetime("2024-06-13T14:30:00Z") is not None
    assert _parse_iso_datetime("2024-06-13T14:30:00+00:00") is not None


def test_parse_iso_datetime_none_or_empty():
    assert _parse_iso_datetime(None) is None
    assert _parse_iso_datetime("") is None


# ---------------------------------------------------------------------------
# Document360Source.create
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_sets_credentials_and_default_config():
    source = await _make_source(api_token="test-token-12345")
    assert source._api_token == "test-token-12345"
    assert source._base_url == DEFAULT_BASE_URL
    assert source._lang_code == "en"


@pytest.mark.asyncio
async def test_create_sets_custom_base_url_and_lang():
    config = Document360Config(
        base_url="https://apihub.us.document360.io",
        lang_code="es",
    )
    source = await _make_source(api_token="test-token-12345", config=config)
    assert source._base_url == "https://apihub.us.document360.io"
    assert source._lang_code == "es"


@pytest.mark.asyncio
async def test_create_strips_trailing_slash_from_base_url():
    config = Document360Config(base_url="https://apihub.document360.io/")
    source = await _make_source(api_token=VALID_API_TOKEN, config=config)
    assert source._base_url == "https://apihub.document360.io"


# ---------------------------------------------------------------------------
# Document360Source._api_url
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_api_url_builds_full_url():
    source = await _make_source(api_token=VALID_API_TOKEN)
    url = source._api_url("/ProjectVersions")
    assert url == f"{DEFAULT_BASE_URL}/v2/ProjectVersions"
    url2 = source._api_url("ProjectVersions")
    assert url2 == f"{DEFAULT_BASE_URL}/v2/ProjectVersions"


# ---------------------------------------------------------------------------
# Document360Source._get (success / API error)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_raises_on_success_false():
    source = await _make_source(api_token=VALID_API_TOKEN)
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.is_success = True
    mock_response.json.return_value = {
        "success": False,
        "errors": [{"description": "Category not found"}],
    }
    source.http_client.get = AsyncMock(return_value=mock_response)
    with pytest.raises(ValueError, match="Document360 API error"):
        await source._get("/ProjectVersions")


# ---------------------------------------------------------------------------
# Document360Source.validate
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_validate_delegates_to_get_project_versions():
    """validate() should call _get with ProjectVersions; failures come from _get / HTTP."""
    source = await _make_source(api_token=VALID_API_TOKEN)
    mock_get = AsyncMock(return_value={"success": True, "data": []})
    with patch.object(source, "_get", mock_get):
        await source.validate()
    mock_get.assert_awaited_once_with("/ProjectVersions")


@pytest.mark.asyncio
async def test_validate_succeeds_on_success():
    source = await _make_source(api_token=VALID_API_TOKEN)
    mock_get = AsyncMock(return_value={"success": True, "data": []})
    with patch.object(source, "_get", mock_get):
        await source.validate()


@pytest.mark.asyncio
async def test_validate_propagates_http_error():
    source = await _make_source(api_token=VALID_API_TOKEN)
    err = httpx.HTTPStatusError("err", request=MagicMock(), response=MagicMock())
    with patch.object(source, "_get", side_effect=err):
        with pytest.raises(httpx.HTTPStatusError):
            await source.validate()


# ---------------------------------------------------------------------------
# Document360Source.generate_entities (mocked)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_generate_entities_yields_versions_and_categories_and_articles():
    source = await _make_source(api_token=VALID_API_TOKEN)

    async def mock_get(path, params=None):
        if "ProjectVersions" in path and "categories" not in path and "articles" not in path:
            return {"success": True, "data": [{"id": "pv1", "version_number": 1.0, "version_code_name": "v1"}]}
        if "categories" in path:
            return {
                "success": True,
                "data": [
                    {
                        "id": "cat1",
                        "name": "Cat1",
                        "description": "Desc",
                        "project_version_id": "pv1",
                        "parent_category_id": None,
                        "order": 1,
                        "slug": "cat1",
                        "category_type": 0,
                        "hidden": False,
                        "created_at": "2024-06-13T14:30:00Z",
                        "modified_at": "2024-06-13T14:30:00Z",
                        "articles": [
                            {
                                "id": "art1",
                                "title": "Article 1",
                                "slug": "article-1",
                                "public_version": 1,
                                "latest_version": 1,
                                "modified_at": "2024-06-13T14:30:00Z",
                                "url": "https://docs.example.com/article-1",
                            }
                        ],
                        "child_categories": [],
                    }
                ],
            }
        if "Articles" in path and "versions" in path:
            return {
                "success": True,
                "data": {
                    "id": "art1",
                    "title": "Article 1",
                    "content": "Article content here",
                    "created_at": "2024-06-13T14:30:00Z",
                    "modified_at": "2024-06-13T14:30:00Z",
                },
            }
        return {"success": True, "data": []}

    with patch.object(source, "_get", side_effect=mock_get):
        entities = []
        async for e in source.generate_entities():
            entities.append(e)

    version_entities = [e for e in entities if isinstance(e, Document360ProjectVersionEntity)]
    category_entities = [e for e in entities if isinstance(e, Document360CategoryEntity)]
    article_entities = [e for e in entities if isinstance(e, Document360ArticleEntity)]

    assert len(version_entities) == 1
    assert version_entities[0].entity_id == "pv1"
    assert version_entities[0].name == "v1"

    assert len(category_entities) == 1
    assert category_entities[0].entity_id == "cat1"
    assert category_entities[0].name == "Cat1"

    assert len(article_entities) == 1
    assert article_entities[0].entity_id == "art1"
    assert article_entities[0].name == "Article 1"
    assert article_entities[0].content == "Article content here"
