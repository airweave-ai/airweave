"""Tests for GoogleDriveSource — drive_id filtering behavior."""

from unittest.mock import AsyncMock, MagicMock

from airweave.platform.configs.config import GoogleDriveConfig
from airweave.platform.sources.google_drive import GoogleDriveSource


def _mock_auth():
    auth = AsyncMock()
    auth.get_token = AsyncMock(return_value="test-token")
    auth.force_refresh = AsyncMock(return_value="refreshed-token")
    auth.supports_refresh = True
    auth.provider_kind = "oauth"
    return auth


async def _make_source(config: GoogleDriveConfig | None = None):
    return await GoogleDriveSource.create(
        auth=_mock_auth(),
        logger=MagicMock(),
        http_client=AsyncMock(),
        config=config if config is not None else GoogleDriveConfig(),
    )


class TestCreate:
    async def test_default_no_drive_filter(self):
        source = await _make_source(GoogleDriveConfig())
        assert source.drive_id_filter is None
        assert source.include_patterns == []

    async def test_drive_id_stored_on_instance(self):
        source = await _make_source(GoogleDriveConfig(drive_id="0ABCdef"))
        assert source.drive_id_filter == "0ABCdef"

    async def test_whitespace_drive_id_normalized_to_none(self):
        source = await _make_source(GoogleDriveConfig(drive_id="   "))
        assert source.drive_id_filter is None


class TestChangesApiScoping:
    """drive_id_filter should scope Changes API requests to that drive only."""

    async def test_start_page_token_includes_drive_id(self):
        source = await _make_source(GoogleDriveConfig(drive_id="0ABCdef"))
        source._get = AsyncMock(return_value={"startPageToken": "tok-1"})

        token = await source._get_start_page_token()

        assert token == "tok-1"
        source._get.assert_awaited_once()
        _, kwargs = source._get.call_args
        params = kwargs["params"]
        assert params["driveId"] == "0ABCdef"
        assert params["supportsAllDrives"] == "true"

    async def test_start_page_token_omits_drive_id_when_unscoped(self):
        source = await _make_source(GoogleDriveConfig())
        source._get = AsyncMock(return_value={"startPageToken": "tok-2"})

        await source._get_start_page_token()

        _, kwargs = source._get.call_args
        assert "driveId" not in kwargs["params"]

    async def test_iterate_changes_scopes_to_drive(self):
        source = await _make_source(GoogleDriveConfig(drive_id="0ABCdef"))
        source._get = AsyncMock(return_value={"changes": [], "newStartPageToken": "tok-n"})

        async for _ in source._iterate_changes("start-tok"):
            pass

        _, kwargs = source._get.call_args
        params = kwargs["params"]
        assert params["driveId"] == "0ABCdef"
        assert params["includeItemsFromAllDrives"] == "false"

    async def test_iterate_changes_unscoped_includes_all_drives(self):
        source = await _make_source(GoogleDriveConfig())
        source._get = AsyncMock(return_value={"changes": [], "newStartPageToken": "tok-n"})

        async for _ in source._iterate_changes("start-tok"):
            pass

        _, kwargs = source._get.call_args
        params = kwargs["params"]
        assert "driveId" not in params
        assert params["includeItemsFromAllDrives"] == "true"


class TestGenerateEntitiesDriveFilter:
    """generate_entities should filter drive list and skip My Drive when scoped."""

    async def test_filters_drives_to_configured_drive_id(self):
        """Only the matching drive should be emitted; others skipped."""
        source = await _make_source(GoogleDriveConfig(drive_id="drive-b"))

        async def fake_list_drives():
            for d in [
                {"id": "drive-a", "name": "A", "createdTime": None},
                {"id": "drive-b", "name": "B", "createdTime": None},
                {"id": "drive-c", "name": "C", "createdTime": None},
            ]:
                yield d

        source._list_drives = fake_list_drives
        # No files needed for this assertion; stub the per-drive file generator to be empty.
        source._generate_file_entities = lambda **kwargs: _aiter_empty()
        source._store_next_start_page_token = AsyncMock()

        drive_entities = []
        async for ent in source.generate_entities(cursor=None, files=None):
            drive_entities.append(ent)

        drive_ids = [
            getattr(e, "entity_id", None) or getattr(e, "drive_id", None) for e in drive_entities
        ]
        assert "drive-b" in drive_ids
        assert "drive-a" not in drive_ids
        assert "drive-c" not in drive_ids

    async def test_unknown_drive_id_warns_and_yields_no_drives(self):
        source = await _make_source(GoogleDriveConfig(drive_id="missing"))
        logger_warning = source.logger.warning = MagicMock()

        async def fake_list_drives():
            yield {"id": "drive-x", "name": "X", "createdTime": None}

        source._list_drives = fake_list_drives
        source._generate_file_entities = lambda **kwargs: _aiter_empty()
        source._store_next_start_page_token = AsyncMock()

        entities = [e async for e in source.generate_entities(cursor=None, files=None)]
        assert entities == []

        warnings = [call.args[0] for call in logger_warning.call_args_list]
        assert any("missing" in msg and "not found" in msg for msg in warnings)

    async def test_my_drive_skipped_when_drive_id_set(self):
        """corpora='user' branch should not be visited when scoped to a shared drive."""
        source = await _make_source(GoogleDriveConfig(drive_id="drive-b"))

        async def fake_list_drives():
            yield {"id": "drive-b", "name": "B", "createdTime": None}

        source._list_drives = fake_list_drives

        calls = []

        def fake_generate_file_entities(**kwargs):
            calls.append(kwargs)
            return _aiter_empty()

        source._generate_file_entities = fake_generate_file_entities
        source._store_next_start_page_token = AsyncMock()

        [_ async for _ in source.generate_entities(cursor=None, files=None)]

        corpora_seen = [c["corpora"] for c in calls]
        assert "drive" in corpora_seen, "expected shared-drive iteration"
        assert "user" not in corpora_seen, "My Drive must be skipped when drive_id is set"

    async def test_my_drive_included_when_no_drive_id(self):
        source = await _make_source(GoogleDriveConfig())

        async def fake_list_drives():
            yield {"id": "drive-a", "name": "A", "createdTime": None}

        source._list_drives = fake_list_drives

        calls = []

        def fake_generate_file_entities(**kwargs):
            calls.append(kwargs)
            return _aiter_empty()

        source._generate_file_entities = fake_generate_file_entities
        source._store_next_start_page_token = AsyncMock()

        [_ async for _ in source.generate_entities(cursor=None, files=None)]

        corpora_seen = [c["corpora"] for c in calls]
        assert "user" in corpora_seen, "My Drive should be iterated when unscoped"


async def _aiter_empty():
    """Async generator that yields nothing — used as a stub for file entity generators."""
    if False:
        yield  # pragma: no cover
