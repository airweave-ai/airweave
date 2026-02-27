"""Unit tests for Microsoft PowerPoint source connector."""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import httpx

from airweave.platform.sources.powerpoint import PowerPointSource
from airweave.platform.storage import FileSkippedException


# ------------------------------------------------------------------
# create()
# ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_success():
    """create() should set access_token and return configured source."""
    source = await PowerPointSource.create("test-token")
    assert isinstance(source, PowerPointSource)
    assert source.access_token == "test-token"


@pytest.mark.asyncio
async def test_create_with_config():
    """create() with config does not require config fields (PowerPointConfig is empty)."""
    source = await PowerPointSource.create("token", config={})
    assert source.access_token == "token"


# ------------------------------------------------------------------
# _parse_datetime()
# ------------------------------------------------------------------


def test_parse_datetime_valid_z_suffix():
    """_parse_datetime parses ISO string with Z suffix."""
    source = PowerPointSource()
    result = source._parse_datetime("2024-06-15T14:30:00Z")
    assert result is not None
    assert result.year == 2024
    assert result.month == 6
    assert result.day == 15


def test_parse_datetime_valid_utc_offset():
    """_parse_datetime parses ISO string with +00:00."""
    source = PowerPointSource()
    result = source._parse_datetime("2024-06-15T14:30:00+00:00")
    assert result is not None
    assert result.year == 2024


def test_parse_datetime_none():
    """_parse_datetime returns None for None."""
    source = PowerPointSource()
    assert source._parse_datetime(None) is None


def test_parse_datetime_invalid():
    """_parse_datetime returns None for invalid string."""
    source = PowerPointSource()
    assert source._parse_datetime("not-a-date") is None


# ------------------------------------------------------------------
# _get_descriptive_error_message()
# ------------------------------------------------------------------


def test_descriptive_error_401_drive():
    """_get_descriptive_error_message includes scope hint for 401 on drive."""
    source = PowerPointSource()
    msg = source._get_descriptive_error_message(
        "https://graph.microsoft.com/v1.0/me/drive/root/children",
        "401 Unauthorized",
    )
    assert "Files.Read.All" in msg
    assert "PowerPoint" in msg


def test_descriptive_error_403_drive():
    """_get_descriptive_error_message includes hint for 403 on drive."""
    source = PowerPointSource()
    msg = source._get_descriptive_error_message(
        "https://graph.microsoft.com/v1.0/me/drive/items/123",
        "403 Forbidden",
    )
    assert "Files.Read.All" in msg


def test_descriptive_error_passthrough():
    """_get_descriptive_error_message returns original error when no specific guidance."""
    source = PowerPointSource()
    msg = source._get_descriptive_error_message(
        "https://graph.microsoft.com/v1.0/other",
        "500 Internal Server Error",
    )
    assert msg == "500 Internal Server Error"


# ------------------------------------------------------------------
# _get_with_auth()
# ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_with_auth_401_refreshes_token_and_retries():
    """_get_with_auth on 401 calls refresh_on_unauthorized and retries with new token."""
    source = await PowerPointSource.create("token")
    source.refresh_on_unauthorized = AsyncMock()
    source.get_access_token = AsyncMock(side_effect=["old-token", "new-token"])

    mock_client = AsyncMock()
    first_response = MagicMock()
    first_response.status_code = 401
    second_response = MagicMock()
    second_response.status_code = 200
    second_response.json.return_value = {"id": "drive-1"}
    mock_client.get = AsyncMock(side_effect=[first_response, second_response])

    result = await source._get_with_auth(mock_client, "https://graph.microsoft.com/v1.0/me/drive")

    assert result == {"id": "drive-1"}
    source.refresh_on_unauthorized.assert_called_once()
    assert mock_client.get.await_count == 2
    # Second call should use new token
    call_args = mock_client.get.call_args_list[1]
    assert "Bearer new-token" in call_args.kwargs.get("headers", {}).get("Authorization", "")


@pytest.mark.asyncio
async def test_get_with_auth_raises_and_logs_descriptive_message():
    """_get_with_auth on exception calls _get_descriptive_error_message and reraises."""
    source = await PowerPointSource.create("token")
    source.get_access_token = AsyncMock(return_value="token")
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(side_effect=httpx.HTTPStatusError("429", request=MagicMock(), response=MagicMock()))

    with patch.object(source, "_get_descriptive_error_message", return_value="Custom error msg") as mock_desc:
        with pytest.raises(httpx.HTTPStatusError):
            await source._get_with_auth(mock_client, "https://graph.microsoft.com/v1.0/me/drive")
        mock_desc.assert_called_once()
        assert "graph.microsoft.com" in mock_desc.call_args[0][0]


# ------------------------------------------------------------------
# _process_drive_page_items()
# ------------------------------------------------------------------


def test_process_drive_page_items_includes_folders_with_id():
    """_process_drive_page_items collects folder ids for items with folder and id."""
    source = PowerPointSource()
    items = [
        {"id": "file1", "name": "deck.pptx"},
        {"id": "folder1", "name": "Slides", "folder": {}},
        {"id": "folder2", "name": "NoId", "folder": {}},  # no "id" key would use .get("id") -> None
    ]
    ppt_items, folder_ids = source._process_drive_page_items(items)
    assert len(ppt_items) == 1
    assert ppt_items[0]["name"] == "deck.pptx"
    assert "folder1" in folder_ids
    assert "folder2" in folder_ids


def test_process_drive_page_items_skips_deleted():
    """_process_drive_page_items skips deleted items."""
    source = PowerPointSource()
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
    source = await PowerPointSource.create("token")
    mock_client = AsyncMock()

    async def get_json(client, url, params=None):
        if "root/children" in url:
            return {
                "value": [
                    {"id": "file1", "name": "deck.pptx", "size": 1000},
                    {"id": "folder1", "name": "Slides", "folder": {}},
                ],
                "@odata.nextLink": None,
            }
        return {"value": [], "@odata.nextLink": None}

    source._get_with_auth = AsyncMock(side_effect=get_json)

    items = []
    async for item in source._discover_powerpoint_files_recursive(mock_client):
        items.append(item)

    assert len(items) == 1
    assert items[0]["name"] == "deck.pptx"
    assert items[0]["id"] == "file1"


@pytest.mark.asyncio
async def test_discover_powerpoint_files_skips_deleted():
    """_discover_powerpoint_files_recursive skips items with deleted=true."""
    source = await PowerPointSource.create("token")
    mock_client = AsyncMock()
    source._get_with_auth = AsyncMock(
        return_value={
            "value": [
                {"id": "del1", "name": "old.pptx", "deleted": True},
                {"id": "f1", "name": "good.pptx"},
            ],
            "@odata.nextLink": None,
        }
    )

    items = []
    async for item in source._discover_powerpoint_files_recursive(mock_client):
        items.append(item)

    assert len(items) == 1
    assert items[0]["name"] == "good.pptx"


@pytest.mark.asyncio
async def test_discover_powerpoint_files_recursive_follows_next_link():
    """_discover_powerpoint_files_recursive follows @odata.nextLink and uses params=None."""
    source = await PowerPointSource.create("token")
    mock_client = AsyncMock()
    next_url = "https://graph.microsoft.com/v1.0/me/drive/root/children?$skiptoken=abc"

    async def get_json(client, url, params=None):
        if "root/children" in url and "skiptoken" not in url:
            return {
                "value": [{"id": "f1", "name": "first.pptx"}],
                "@odata.nextLink": next_url,
            }
        if "skiptoken" in url:
            return {"value": [{"id": "f2", "name": "second.pptx"}], "@odata.nextLink": None}
        return {"value": [], "@odata.nextLink": None}

    source._get_with_auth = AsyncMock(side_effect=get_json)
    items = []
    async for item in source._discover_powerpoint_files_recursive(mock_client):
        items.append(item)
    assert len(items) == 2
    assert items[0]["name"] == "first.pptx"
    assert items[1]["name"] == "second.pptx"


@pytest.mark.asyncio
async def test_discover_powerpoint_files_recursive_handles_exception():
    """_discover_powerpoint_files_recursive logs and yields nothing when _get_with_auth raises."""
    source = await PowerPointSource.create("token")
    mock_client = AsyncMock()
    source._get_with_auth = AsyncMock(side_effect=httpx.HTTPStatusError("500", request=MagicMock(), response=MagicMock()))
    items = []
    async for item in source._discover_powerpoint_files_recursive(mock_client):
        items.append(item)
    assert len(items) == 0


@pytest.mark.asyncio
async def test_discover_powerpoint_files_recursive_max_depth():
    """_discover_powerpoint_files_recursive stops at MAX_FOLDER_DEPTH."""
    source = await PowerPointSource.create("token")
    mock_client = AsyncMock()
    items = []
    async for item in source._discover_powerpoint_files_recursive(mock_client, folder_id="f1", depth=10):
        items.append(item)
    assert len(items) == 0


# ------------------------------------------------------------------
# _generate_presentation_entities()
# ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_generate_presentation_entities_maps_drive_item():
    """_generate_presentation_entities maps Graph drive item to PowerPointPresentationEntity."""
    source = await PowerPointSource.create("token")
    mock_client = AsyncMock()

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

    async def discover(_client):
        yield drive_item

    source._discover_powerpoint_files_recursive = discover

    entities = []
    async for ent in source._generate_presentation_entities(mock_client):
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
    source = await PowerPointSource.create("token")
    mock_client = AsyncMock()

    async def discover_empty(_client):
        return
        yield  # no items

    source._discover_powerpoint_files_recursive = discover_empty
    entities = []
    async for ent in source._generate_presentation_entities(mock_client):
        entities.append(ent)
    assert len(entities) == 0


@pytest.mark.asyncio
async def test_generate_presentation_entities_discover_raises():
    """_generate_presentation_entities reraises when discover raises."""
    source = await PowerPointSource.create("token")
    mock_client = AsyncMock()

    async def discover_raises(_client):
        raise ValueError("API error")
        yield  # unreachable; makes this an async generator

    source._discover_powerpoint_files_recursive = discover_raises
    with pytest.raises(ValueError, match="API error"):
        async for _ in source._generate_presentation_entities(mock_client):
            pass


@pytest.mark.asyncio
async def test_generate_presentation_entities_folder_path_strips_root():
    """_generate_presentation_entities strips /root: from folder_path."""
    source = await PowerPointSource.create("token")
    mock_client = AsyncMock()
    drive_item = {
        "id": "item-1",
        "name": "Deck.pptx",
        "size": 100,
        "parentReference": {"driveId": "d1", "path": "/drive/root:/MyFolder/Docs"},
    }

    async def discover_one(_client):
        yield drive_item

    source._discover_powerpoint_files_recursive = discover_one
    entities = []
    async for ent in source._generate_presentation_entities(mock_client):
        entities.append(ent)
    assert len(entities) == 1
    assert entities[0].folder_path == "/MyFolder/Docs"


# ------------------------------------------------------------------
# validate()
# ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_validate_returns_true_on_success():
    """validate() returns True when drive ping succeeds."""
    source = await PowerPointSource.create("token")
    source._validate_oauth2 = AsyncMock(return_value=True)
    assert await source.validate() is True


@pytest.mark.asyncio
async def test_validate_returns_false_on_failure():
    """validate() returns False when _validate_oauth2 fails."""
    source = await PowerPointSource.create("token")
    source._validate_oauth2 = AsyncMock(return_value=False)
    assert await source.validate() is False


# ------------------------------------------------------------------
# generate_entities()
# ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_generate_entities_yields_downloaded_presentations():
    """generate_entities yields presentation entities after successful download."""
    source = await PowerPointSource.create("token")
    source.get_access_token = AsyncMock(return_value="token")

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

    async def gen_entities(client):
        yield entity

    source._generate_presentation_entities = gen_entities
    mock_downloader = MagicMock()
    mock_downloader.download_from_url = AsyncMock()
    source.set_file_downloader(mock_downloader)

    mock_client = AsyncMock()
    mock_cm = AsyncMock()
    mock_cm.__aenter__.return_value = mock_client
    mock_cm.__aexit__.return_value = None
    source.http_client = MagicMock(return_value=mock_cm)

    results = []
    async for e in source.generate_entities():
        results.append(e)

    assert len(results) == 1
    assert results[0].id == "e1"
    assert results[0].title == "Test"
    mock_downloader.download_from_url.assert_called_once()


@pytest.mark.asyncio
async def test_generate_entities_download_missing_local_path_continues():
    """generate_entities continues when download leaves local_path None (ValueError)."""
    source = await PowerPointSource.create("token")
    source.get_access_token = AsyncMock(return_value="token")
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

    async def gen_entities(client):
        yield entity

    source._generate_presentation_entities = gen_entities
    mock_downloader = MagicMock()
    mock_downloader.download_from_url = AsyncMock()  # does not set local_path
    source.set_file_downloader(mock_downloader)
    mock_cm = AsyncMock()
    mock_cm.__aenter__.return_value = AsyncMock()
    mock_cm.__aexit__.return_value = None
    source.http_client = MagicMock(return_value=mock_cm)

    results = []
    async for e in source.generate_entities():
        results.append(e)
    assert len(results) == 0


@pytest.mark.asyncio
async def test_generate_entities_skips_on_file_skipped_exception():
    """generate_entities skips presentation when FileSkippedException is raised."""
    source = await PowerPointSource.create("token")
    source.get_access_token = AsyncMock(return_value="token")
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

    async def gen_entities(client):
        yield entity

    source._generate_presentation_entities = gen_entities
    mock_downloader = MagicMock()
    mock_downloader.download_from_url = AsyncMock(
        side_effect=FileSkippedException("too large", "Skip.pptx")
    )
    source.set_file_downloader(mock_downloader)
    mock_cm = AsyncMock()
    mock_cm.__aenter__.return_value = AsyncMock()
    mock_cm.__aexit__.return_value = None
    source.http_client = MagicMock(return_value=mock_cm)

    results = []
    async for e in source.generate_entities():
        results.append(e)
    assert len(results) == 0


@pytest.mark.asyncio
async def test_generate_entities_continues_on_download_exception():
    """generate_entities continues when download raises generic Exception."""
    source = await PowerPointSource.create("token")
    source.get_access_token = AsyncMock(return_value="token")
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

    async def gen_entities(client):
        yield entity

    source._generate_presentation_entities = gen_entities
    mock_downloader = MagicMock()
    mock_downloader.download_from_url = AsyncMock(side_effect=RuntimeError("network error"))
    source.set_file_downloader(mock_downloader)
    mock_cm = AsyncMock()
    mock_cm.__aenter__.return_value = AsyncMock()
    mock_cm.__aexit__.return_value = None
    source.http_client = MagicMock(return_value=mock_cm)

    results = []
    async for e in source.generate_entities():
        results.append(e)
    assert len(results) == 0


def test_parse_datetime_invalid_logs_warning():
    """_parse_datetime logs warning and returns None on invalid input."""
    source = PowerPointSource()
    with patch.object(source.logger, "warning", MagicMock()) as mock_warning:
        result = source._parse_datetime("invalid-date")
    assert result is None
    mock_warning.assert_called_once()
    assert "invalid-date" in mock_warning.call_args[0][0]
