"""Unit tests for Microsoft PowerPoint source connector."""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from airweave.domains.sources.exceptions import SourceServerError
from airweave.domains.storage import FileSkippedException
from airweave.platform.configs.config import PowerPointConfig
from airweave.platform.entities.powerpoint import _parse_dt
from airweave.platform.sources.powerpoint import PowerPointSource


def _mock_auth(token="test-token"):
    auth = AsyncMock()
    auth.get_token = AsyncMock(return_value=token)
    auth.force_refresh = AsyncMock(return_value="refreshed-token")
    auth.supports_refresh = True
    auth.provider_kind = "oauth"
    return auth


def _mock_http_client():
    client = AsyncMock()
    client.get = AsyncMock()
    return client


def _mock_logger():
    return MagicMock()


def _bare_source():
    """Construct PowerPointSource with injected deps (no create())."""
    return PowerPointSource(
        auth=_mock_auth(),
        logger=_mock_logger(),
        http_client=_mock_http_client(),
    )


async def _make_source(token="test-token"):
    return await PowerPointSource.create(
        auth=_mock_auth(token=token),
        logger=_mock_logger(),
        http_client=_mock_http_client(),
        config=PowerPointConfig(),
    )


# ------------------------------------------------------------------
# create()
# ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_success():
    """create() returns a source whose auth yields the configured token."""
    source = await _make_source("test-token")
    assert isinstance(source, PowerPointSource)
    assert await source.auth.get_token() == "test-token"


@pytest.mark.asyncio
async def test_create_with_config():
    """create() accepts PowerPointConfig (empty schema)."""
    source = await PowerPointSource.create(
        auth=_mock_auth("token"),
        logger=_mock_logger(),
        http_client=_mock_http_client(),
        config=PowerPointConfig(),
    )
    assert await source.auth.get_token() == "token"


# ------------------------------------------------------------------
# _parse_dt() (entity helper; was _parse_datetime on source)
# ------------------------------------------------------------------


def test_parse_dt_valid_z_suffix():
    """_parse_dt parses ISO string with Z suffix."""
    result = _parse_dt("2024-06-15T14:30:00Z")
    assert result is not None
    assert result.year == 2024
    assert result.month == 6
    assert result.day == 15


def test_parse_dt_valid_utc_offset():
    """_parse_dt parses ISO string with +00:00."""
    result = _parse_dt("2024-06-15T14:30:00+00:00")
    assert result is not None
    assert result.year == 2024


def test_parse_dt_none():
    """_parse_dt returns None for None / empty."""
    assert _parse_dt(None) is None
    assert _parse_dt("") is None


def test_parse_dt_invalid():
    """_parse_dt returns None for invalid string."""
    assert _parse_dt("not-a-date") is None


# ------------------------------------------------------------------
# _get()
# ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_401_refreshes_token_and_retries():
    """_get on 401 calls force_refresh and retries with new token."""
    source = await _make_source("token")

    first_response = MagicMock()
    first_response.status_code = 401
    second_response = MagicMock()
    second_response.status_code = 200
    second_response.json.return_value = {"id": "drive-1"}
    source.http_client.get = AsyncMock(side_effect=[first_response, second_response])

    result = await source._get("https://graph.microsoft.com/v1.0/me/drive")

    assert result == {"id": "drive-1"}
    source.auth.force_refresh.assert_called_once()
    assert source.http_client.get.await_count == 2
    call_args = source.http_client.get.call_args_list[1]
    assert "Bearer refreshed-token" in call_args.kwargs.get("headers", {}).get("Authorization", "")


@pytest.mark.asyncio
async def test_get_raises_on_server_error_status():
    """_get uses raise_for_status — 500 maps to SourceServerError."""
    source = await _make_source("token")
    url = "https://graph.microsoft.com/v1.0/me/drive"
    req = httpx.Request("GET", url)
    resp = httpx.Response(status_code=500, request=req)
    source.http_client.get = AsyncMock(return_value=resp)

    with pytest.raises(SourceServerError):
        await source._get(url)


# ------------------------------------------------------------------
# _process_drive_page_items()
# ------------------------------------------------------------------


def test_process_drive_page_items_includes_folders_with_id():
    """_process_drive_page_items collects folder ids for items with folder and id."""
    source = _bare_source()
    items = [
        {"id": "file1", "name": "deck.pptx"},
        {"id": "folder1", "name": "Slides", "folder": {}},
        {"id": "folder2", "name": "NoId", "folder": {}},
    ]
    ppt_items, folder_ids = source._process_drive_page_items(items)
    assert len(ppt_items) == 1
    assert ppt_items[0]["name"] == "deck.pptx"
    assert "folder1" in folder_ids
    assert "folder2" in folder_ids


def test_process_drive_page_items_skips_deleted():
    """_process_drive_page_items skips deleted items."""
    source = _bare_source()
    items = [{"id": "del1", "name": "old.pptx", "deleted": True}]
    ppt_items, folder_ids = source._process_drive_page_items(items)
    assert len(ppt_items) == 0
    assert len(folder_ids) == 0


# ------------------------------------------------------------------
# _discover_powerpoint_files_recursive()
# ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_discover_powerpoint_files_yields_pptx():
    """_discover_powerpoint_files_recursive yields drive items ending in .pptx."""
    source = await _make_source("token")

    async def get_json(url, params=None):
        if "root/children" in url:
            return {
                "value": [
                    {"id": "file1", "name": "deck.pptx", "size": 1000},
                    {"id": "folder1", "name": "Slides", "folder": {}},
                ],
                "@odata.nextLink": None,
            }
        return {"value": [], "@odata.nextLink": None}

    source._get = AsyncMock(side_effect=get_json)

    items = []
    async for item in source._discover_powerpoint_files_recursive():
        items.append(item)

    assert len(items) == 1
    assert items[0]["name"] == "deck.pptx"
    assert items[0]["id"] == "file1"


@pytest.mark.asyncio
async def test_discover_powerpoint_files_skips_deleted():
    """_discover_powerpoint_files_recursive skips items with deleted=true."""
    source = await _make_source("token")
    source._get = AsyncMock(
        return_value={
            "value": [
                {"id": "del1", "name": "old.pptx", "deleted": True},
                {"id": "f1", "name": "good.pptx"},
            ],
            "@odata.nextLink": None,
        }
    )

    items = []
    async for item in source._discover_powerpoint_files_recursive():
        items.append(item)

    assert len(items) == 1
    assert items[0]["name"] == "good.pptx"


@pytest.mark.asyncio
async def test_discover_powerpoint_files_recursive_follows_next_link():
    """_discover_powerpoint_files_recursive follows @odata.nextLink and uses params=None."""
    source = await _make_source("token")
    next_url = "https://graph.microsoft.com/v1.0/me/drive/root/children?$skiptoken=abc"

    async def get_json(url, params=None):
        if "root/children" in url and "skiptoken" not in url:
            return {
                "value": [{"id": "f1", "name": "first.pptx"}],
                "@odata.nextLink": next_url,
            }
        if "skiptoken" in url:
            return {"value": [{"id": "f2", "name": "second.pptx"}], "@odata.nextLink": None}
        return {"value": [], "@odata.nextLink": None}

    source._get = AsyncMock(side_effect=get_json)
    items = []
    async for item in source._discover_powerpoint_files_recursive():
        items.append(item)
    assert len(items) == 2
    assert items[0]["name"] == "first.pptx"
    assert items[1]["name"] == "second.pptx"


@pytest.mark.asyncio
async def test_discover_powerpoint_files_recursive_handles_exception():
    """_discover_powerpoint_files_recursive logs and yields nothing when _get raises."""
    source = await _make_source("token")
    source._get = AsyncMock(side_effect=ValueError("boom"))
    items = []
    async for item in source._discover_powerpoint_files_recursive():
        items.append(item)
    assert len(items) == 0


@pytest.mark.asyncio
async def test_discover_powerpoint_files_recursive_max_depth():
    """_discover_powerpoint_files_recursive stops at MAX_FOLDER_DEPTH."""
    source = await _make_source("token")
    items = []
    async for item in source._discover_powerpoint_files_recursive(folder_id="f1", depth=10):
        items.append(item)
    assert len(items) == 0


# ------------------------------------------------------------------
# _generate_presentation_entities()
# ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_generate_presentation_entities_maps_drive_item():
    """_generate_presentation_entities maps Graph drive item to PowerPointPresentationEntity."""
    source = await _make_source("token")

    drive_item = {
        "id": "item-123",
        "name": "Q4 Review.pptx",
        "size": 5000,
        "createdDateTime": "2024-01-10T09:00:00Z",
        "lastModifiedDateTime": "2024-01-15T14:00:00Z",
        "webUrl": "https://contoso.sharepoint.com/...",
        "parentReference": {"driveId": "drive-1", "path": "/drive/root:/Docs"},
        "createdBy": {"user": {"displayName": "Alice"}},
        "lastModifiedBy": {"user": {"displayName": "Bob"}},
    }

    async def discover():
        yield drive_item

    source._discover_powerpoint_files_recursive = discover

    entities = []
    async for ent in source._generate_presentation_entities():
        entities.append(ent)

    assert len(entities) == 1
    e = entities[0]
    assert e.id == "item-123"
    assert e.title == "Q4 Review"
    assert e.name == "Q4 Review.pptx"
    assert e.size == 5000
    assert e.file_type == "microsoft_powerpoint"
    assert e.created_datetime is not None
    assert e.last_modified_datetime is not None
    assert e.web_url_override == "https://contoso.sharepoint.com/..."


@pytest.mark.asyncio
async def test_generate_presentation_entities_empty_warns():
    """_generate_presentation_entities logs warning when no presentations found."""
    source = await _make_source("token")

    async def discover_empty():
        for _ in []:
            yield  # pragma: no cover — empty async generator

    source._discover_powerpoint_files_recursive = discover_empty
    entities = []
    async for ent in source._generate_presentation_entities():
        entities.append(ent)
    assert len(entities) == 0


@pytest.mark.asyncio
async def test_generate_presentation_entities_discover_raises():
    """_generate_presentation_entities reraises when discover raises."""
    source = await _make_source("token")

    async def discover_raises():
        raise ValueError("API error")
        yield  # noqa: unreachable — makes async generator

    source._discover_powerpoint_files_recursive = discover_raises
    with pytest.raises(ValueError, match="API error"):
        async for _ in source._generate_presentation_entities():
            pass


@pytest.mark.asyncio
async def test_generate_presentation_entities_folder_path_strips_root():
    """_generate_presentation_entities strips /root: from folder_path."""
    source = await _make_source("token")
    drive_item = {
        "id": "item-1",
        "name": "Deck.pptx",
        "size": 100,
        "parentReference": {"driveId": "d1", "path": "/drive/root:/MyFolder/Docs"},
    }

    async def discover_one():
        yield drive_item

    source._discover_powerpoint_files_recursive = discover_one
    entities = []
    async for ent in source._generate_presentation_entities():
        entities.append(ent)
    assert len(entities) == 1
    assert entities[0].folder_path == "/MyFolder/Docs"


# ------------------------------------------------------------------
# validate()
# ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_validate_succeeds_when_drive_ping_succeeds():
    """validate() completes when Graph drive ping succeeds."""
    source = await _make_source("token")
    source._get = AsyncMock(return_value={"id": "drive-1"})
    await source.validate()
    source._get.assert_awaited()


@pytest.mark.asyncio
async def test_validate_raises_on_auth_failure():
    """validate() raises SourceAuthError when _get returns 401."""
    from airweave.domains.sources.exceptions import SourceAuthError

    source = await _make_source("token")
    source._get = AsyncMock(side_effect=SourceAuthError(
        "Unauthorized",
        status_code=401,
        source_short_name="powerpoint",
        token_provider_kind="oauth",
    ))
    with pytest.raises(SourceAuthError):
        await source.validate()


# ------------------------------------------------------------------
# generate_entities()
# ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_generate_entities_yields_downloaded_presentations():
    """generate_entities yields presentation entities after successful download."""
    source = await _make_source("token")

    from airweave.platform.entities.powerpoint import PowerPointPresentationEntity

    entity = PowerPointPresentationEntity(
        breadcrumbs=[],
        name="Test.pptx",
        id="e1",
        title="Test",
        created_datetime=datetime.now(),
        last_modified_datetime=datetime.now(),
        url="https://graph.microsoft.com/v1.0/me/drive/items/e1/content",
        size=100,
        file_type="microsoft_powerpoint",
        mime_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        local_path="/tmp/test.pptx",
    )

    async def gen_entities():
        yield entity

    source._generate_presentation_entities = gen_entities
    mock_files = MagicMock()

    async def download_ok(entity, client, auth, logger):
        entity.local_path = "/tmp/test.pptx"
        return entity

    mock_files.download_from_url = AsyncMock(side_effect=download_ok)

    results = []
    async for e in source.generate_entities(files=mock_files):
        results.append(e)

    assert len(results) == 1
    assert results[0].id == "e1"
    assert results[0].title == "Test"
    mock_files.download_from_url.assert_called_once()


@pytest.mark.asyncio
async def test_generate_entities_download_missing_local_path_continues():
    """generate_entities continues when download leaves local_path None."""
    source = await _make_source("token")
    from airweave.platform.entities.powerpoint import PowerPointPresentationEntity

    entity = PowerPointPresentationEntity(
        breadcrumbs=[],
        name="Test.pptx",
        id="e1",
        title="Test",
        created_datetime=datetime.now(),
        last_modified_datetime=datetime.now(),
        url="https://graph.microsoft.com/v1.0/me/drive/items/e1/content",
        size=100,
        file_type="microsoft_powerpoint",
        mime_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        local_path=None,
    )

    async def gen_entities():
        yield entity

    source._generate_presentation_entities = gen_entities
    mock_files = MagicMock()
    mock_files.download_from_url = AsyncMock()  # does not set local_path

    results = []
    async for e in source.generate_entities(files=mock_files):
        results.append(e)
    assert len(results) == 0


@pytest.mark.asyncio
async def test_generate_entities_skips_on_file_skipped_exception():
    """generate_entities skips presentation when FileSkippedException is raised."""
    source = await _make_source("token")
    from airweave.platform.entities.powerpoint import PowerPointPresentationEntity

    entity = PowerPointPresentationEntity(
        breadcrumbs=[],
        name="Skip.pptx",
        id="e1",
        title="Skip",
        created_datetime=datetime.now(),
        last_modified_datetime=datetime.now(),
        url="https://graph.microsoft.com/v1.0/me/drive/items/e1/content",
        size=100,
        file_type="microsoft_powerpoint",
        mime_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        local_path=None,
    )

    async def gen_entities():
        yield entity

    source._generate_presentation_entities = gen_entities
    mock_files = MagicMock()
    mock_files.download_from_url = AsyncMock(
        side_effect=FileSkippedException("too large", "Skip.pptx")
    )

    results = []
    async for e in source.generate_entities(files=mock_files):
        results.append(e)
    assert len(results) == 0


@pytest.mark.asyncio
async def test_generate_entities_continues_on_download_exception():
    """generate_entities continues when download raises generic Exception."""
    source = await _make_source("token")
    from airweave.platform.entities.powerpoint import PowerPointPresentationEntity

    entity = PowerPointPresentationEntity(
        breadcrumbs=[],
        name="Fail.pptx",
        id="e1",
        title="Fail",
        created_datetime=datetime.now(),
        last_modified_datetime=datetime.now(),
        url="https://graph.microsoft.com/v1.0/me/drive/items/e1/content",
        size=100,
        file_type="microsoft_powerpoint",
        mime_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        local_path=None,
    )

    async def gen_entities():
        yield entity

    source._generate_presentation_entities = gen_entities
    mock_files = MagicMock()
    mock_files.download_from_url = AsyncMock(side_effect=RuntimeError("network error"))

    results = []
    async for e in source.generate_entities(files=mock_files):
        results.append(e)
    assert len(results) == 0
