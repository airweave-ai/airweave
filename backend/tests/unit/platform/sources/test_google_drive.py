import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock

from airweave.domains.sources.exceptions import SourceCursorInvalidError
from airweave.platform.configs.config import GoogleDriveConfig
from airweave.platform.entities.google_drive import (
    GoogleDriveCommentEntity,
    GoogleDriveFileEntity,
    GoogleDriveReplyEntity,
)
from airweave.platform.sources.google_drive import GoogleDriveSource


def _mock_auth():
    auth = MagicMock()
    auth.get_token = AsyncMock(return_value="token")
    auth.supports_refresh = False
    auth.provider_kind = "oauth"
    return auth


def _mock_http_client():
    client = MagicMock()
    client.get = AsyncMock()
    return client


@pytest_asyncio.fixture
async def gdrive_source() -> GoogleDriveSource:
    return await GoogleDriveSource.create(
        auth=_mock_auth(),
        logger=MagicMock(),
        http_client=_mock_http_client(),
        config=GoogleDriveConfig(),
    )


@pytest_asyncio.fixture
async def gdrive_source_refresh() -> GoogleDriveSource:
    auth = _mock_auth()
    auth.supports_refresh = True
    auth.force_refresh = AsyncMock(return_value="new-token")
    return await GoogleDriveSource.create(
        auth=auth,
        logger=MagicMock(),
        http_client=_mock_http_client(),
        config=GoogleDriveConfig(),
    )


def _file_entity(file_id: str = "file-1") -> GoogleDriveFileEntity:
    return GoogleDriveFileEntity.from_api(
        {
            "id": file_id,
            "name": "Roadmap",
            "mimeType": "application/pdf",
            "createdTime": "2024-01-01T00:00:00Z",
            "modifiedTime": "2024-01-02T00:00:00Z",
            "size": "123",
            "md5Checksum": "abc",
        },
        breadcrumbs=[],
    )


def _file_payload(
    *,
    file_id: str = "file-1",
    name: str = "Roadmap",
    mime_type: str = "application/pdf",
    size: str = "123",
    trashed: bool = False,
) -> dict:
    return {
        "id": file_id,
        "name": name,
        "mimeType": mime_type,
        "createdTime": "2024-01-01T00:00:00Z",
        "modifiedTime": "2024-01-02T00:00:00Z",
        "size": size,
        "md5Checksum": "abc",
        "trashed": trashed,
        "explicitlyTrashed": False,
        "parents": [],
    }


@pytest.mark.asyncio
async def test_get_refreshes_on_401_and_retries(gdrive_source_refresh: GoogleDriveSource):
    resp_401 = MagicMock()
    resp_401.status_code = 401

    resp_200 = MagicMock()
    resp_200.status_code = 200
    resp_200.json.return_value = {"ok": True}

    gdrive_source_refresh.http_client.get = AsyncMock(side_effect=[resp_401, resp_200])

    data = await gdrive_source_refresh._get("https://www.googleapis.com/drive/v3/about")
    assert data == {"ok": True}
    assert gdrive_source_refresh.auth.force_refresh.await_count == 1
    assert gdrive_source_refresh.http_client.get.await_count == 2


@pytest.mark.asyncio
async def test_list_drives_paginates(gdrive_source: GoogleDriveSource):
    gdrive_source._get = AsyncMock(
        side_effect=[
            {"drives": [{"id": "d1", "name": "Drive 1"}], "nextPageToken": "next"},
            {"drives": [{"id": "d2", "name": "Drive 2"}], "nextPageToken": None},
        ]
    )

    drives = [d async for d in gdrive_source._list_drives()]
    assert [d["id"] for d in drives] == ["d1", "d2"]
    assert gdrive_source._get.await_count == 2


@pytest.mark.asyncio
async def test_iterate_changes_sets_latest_new_start_token(gdrive_source: GoogleDriveSource):
    gdrive_source._get = AsyncMock(
        side_effect=[
            {
                "changes": [{"fileId": "f1", "file": {"id": "f1"}}],
                "nextPageToken": "next",
                "newStartPageToken": "new-start-1",
            },
            {
                "changes": [{"fileId": "f2", "file": {"id": "f2"}}],
                "nextPageToken": None,
                "newStartPageToken": "new-start-2",
            },
        ]
    )

    changes = [c async for c in gdrive_source._iterate_changes("start")]
    assert [c["fileId"] for c in changes] == ["f1", "f2"]
    assert getattr(gdrive_source, "_latest_new_start_page_token") == "new-start-2"


def test_build_file_entity_skips_video(gdrive_source: GoogleDriveSource):
    ent = gdrive_source._build_file_entity(
        _file_payload(mime_type="video/mp4"),
        parent_breadcrumb=None,
    )
    assert ent is None


def test_build_file_entity_skips_oversized(gdrive_source: GoogleDriveSource):
    ent = gdrive_source._build_file_entity(
        _file_payload(size=str(201 * 1024 * 1024)),
        parent_breadcrumb=None,
    )
    assert ent is None


def test_build_file_entity_skips_trashed_non_google_file(gdrive_source: GoogleDriveSource):
    ent = gdrive_source._build_file_entity(
        _file_payload(trashed=True, mime_type="application/pdf"),
        parent_breadcrumb=None,
    )
    assert ent is None


@pytest.mark.asyncio
async def test_list_label_ids_for_file_paginates(gdrive_source: GoogleDriveSource):
    gdrive_source._get = AsyncMock(
        side_effect=[
            {"labels": [{"id": "l1"}], "nextPageToken": "next"},
            {"labels": [{"id": "l2"}], "nextPageToken": None},
        ]
    )

    labels = await gdrive_source._list_label_ids_for_file("file-1")
    assert labels == ["l1", "l2"]
    assert gdrive_source._get.await_count == 2


@pytest.mark.asyncio
async def test_emit_changes_since_token_emits_extras_after_file(gdrive_source: GoogleDriveSource):
    file_ent = _file_entity("file-1")

    async def _changes():
        yield {"fileId": "file-1"}

    async def _extras(_file: GoogleDriveFileEntity):
        yield GoogleDriveCommentEntity(
            entity_id="c1",
            breadcrumbs=[],
            comment_id="c1",
            file_id=_file.file_id,
            content="comment",
            author_name=None,
            created_time=None,
            modified_time=None,
            deleted=False,
        )

    gdrive_source._iterate_changes = MagicMock(return_value=_changes())
    gdrive_source._build_entity_from_change = AsyncMock(return_value=file_ent)
    gdrive_source._emit_comments_and_replies_for_file = MagicMock(return_value=_extras(file_ent))

    out = [e async for e in gdrive_source._emit_changes_since_token("start")]
    assert [type(e) for e in out] == [GoogleDriveFileEntity, GoogleDriveCommentEntity]

@pytest.mark.asyncio
async def test_emit_changes_since_token_recovers_from_cursor_invalid_410(gdrive_source: GoogleDriveSource):
    cursor = MagicMock()
    cursor.data = {"start_page_token": "old"}
    cursor.update = MagicMock()
    gdrive_source._cursor = cursor

    async def _iterate(token: str):
        if token == "old":
            raise SourceCursorInvalidError(
                "Cursor invalid (410)",
                source_short_name="google_drive",
            )
        yield {"fileId": "file-1"}

    async def _empty_extras(_file: GoogleDriveFileEntity):
        if False:  # pragma: no cover
            yield _file

    gdrive_source._iterate_changes = _iterate
    gdrive_source._get_start_page_token = AsyncMock(return_value="fresh-token")
    gdrive_source._build_entity_from_change = AsyncMock(return_value=_file_entity("file-1"))
    gdrive_source._emit_comments_and_replies_for_file = _empty_extras

    out = [e async for e in gdrive_source._emit_changes_since_token("old")]
    assert len(out) == 1
    assert isinstance(out[0], GoogleDriveFileEntity)
    cursor.update.assert_any_call(start_page_token="fresh-token")


@pytest.mark.asyncio
async def test_native_search_builds_drive_q_and_escapes(gdrive_source: GoogleDriveSource):
    gdrive_source._get = AsyncMock(
        return_value={"files": [_file_payload(file_id="f1", name="One")], "nextPageToken": None}
    )

    results = await gdrive_source.native_search("Bob's \\\\ roadmap", limit=5)
    assert len(results) == 1
    assert results[0].airweave_system_metadata is not None
    assert results[0].textual_representation is not None

    _, kwargs = gdrive_source._get.call_args
    assert kwargs["params"]["q"] == "trashed = false and fullText contains 'Bob\\'s \\\\\\\\ roadmap'"


@pytest.mark.asyncio
async def test_native_search_paginates_and_applies_limit(gdrive_source: GoogleDriveSource):
    gdrive_source._get = AsyncMock(
        side_effect=[
            {
                "files": [
                    _file_payload(file_id="f1", name="One"),
                    _file_payload(file_id="f2", name="Two"),
                ],
                "nextPageToken": "next-1",
            },
            {
                "files": [
                    _file_payload(file_id="f3", name="Three"),
                    _file_payload(file_id="f4", name="Four"),
                ],
                "nextPageToken": None,
            },
        ]
    )

    results = await gdrive_source.native_search("roadmap", limit=3)
    assert [r.file_id for r in results] == ["f1", "f2", "f3"]
    assert gdrive_source._get.await_count == 2

@pytest.mark.asyncio
async def test_enrich_file_with_labels_sets_ids(gdrive_source: GoogleDriveSource):
    gdrive_source._get = AsyncMock(
        return_value={
            "labels": [{"id": "label-1"}, {"id": "label-2"}],
            "nextPageToken": None,
        }
    )

    ent = _file_entity()
    await gdrive_source._enrich_file_with_labels(ent)
    assert ent.labels == ["label-1", "label-2"]


@pytest.mark.asyncio
async def test_enrich_file_with_labels_uses_cache(gdrive_source: GoogleDriveSource):
    gdrive_source._get = AsyncMock(
        return_value={
            "labels": [{"id": "label-1"}],
            "nextPageToken": None,
        }
    )

    ent = _file_entity("file-1")
    await gdrive_source._enrich_file_with_labels(ent)
    await gdrive_source._enrich_file_with_labels(ent)

    assert ent.labels == ["label-1"]
    assert gdrive_source._get.await_count == 1


@pytest.mark.asyncio
async def test_emit_comments_and_replies_yields_entities(gdrive_source: GoogleDriveSource):
    gdrive_source._get = AsyncMock(
        return_value={
            "comments": [
                {
                    "id": "c-1",
                    "content": "Top-level comment",
                    "deleted": False,
                    "createdTime": "2024-01-03T00:00:00Z",
                    "modifiedTime": "2024-01-03T00:00:00Z",
                    "author": {"displayName": "Alice"},
                    "replies": [
                        {
                            "id": "r-1",
                            "content": "Reply text",
                            "deleted": False,
                            "createdTime": "2024-01-04T00:00:00Z",
                            "modifiedTime": "2024-01-04T00:00:00Z",
                            "author": {"displayName": "Bob"},
                        }
                    ],
                }
            ],
            "nextPageToken": None,
        }
    )

    ent = _file_entity()
    results = [e async for e in gdrive_source._emit_comments_and_replies_for_file(ent)]

    assert [type(e) for e in results] == [GoogleDriveCommentEntity, GoogleDriveReplyEntity]
    assert results[0].file_id == ent.file_id
    assert results[1].comment_id == results[0].comment_id


@pytest.mark.asyncio
async def test_emit_comments_and_replies_paginates_and_skips_deleted(
    gdrive_source: GoogleDriveSource,
):
    gdrive_source._get = AsyncMock(
        side_effect=[
            {
                "comments": [
                    {
                        "id": "c-1",
                        "content": "Keep",
                        "deleted": False,
                        "createdTime": "2024-01-03T00:00:00Z",
                        "modifiedTime": "2024-01-03T00:00:00Z",
                        "author": {"displayName": "Alice"},
                        "replies": [
                            {
                                "id": "r-1",
                                "content": "Deleted reply",
                                "deleted": True,
                                "createdTime": "2024-01-04T00:00:00Z",
                                "modifiedTime": "2024-01-04T00:00:00Z",
                                "author": {"displayName": "Bob"},
                            }
                        ],
                    }
                ],
                "nextPageToken": "next-1",
            },
            {
                "comments": [
                    {
                        "id": "c-2",
                        "content": "Deleted comment",
                        "deleted": True,
                        "createdTime": "2024-01-05T00:00:00Z",
                        "modifiedTime": "2024-01-05T00:00:00Z",
                        "author": {"displayName": "Charlie"},
                        "replies": [
                            {
                                "id": "r-2",
                                "content": "Keep reply",
                                "deleted": False,
                                "createdTime": "2024-01-06T00:00:00Z",
                                "modifiedTime": "2024-01-06T00:00:00Z",
                                "author": {"displayName": "Dana"},
                            }
                        ],
                    }
                ],
                "nextPageToken": None,
            },
        ]
    )

    ent = _file_entity()
    results = [e async for e in gdrive_source._emit_comments_and_replies_for_file(ent)]

    # c-1 emitted, r-1 skipped (deleted), c-2 skipped (deleted), r-2 emitted
    assert [type(e) for e in results] == [GoogleDriveCommentEntity, GoogleDriveReplyEntity]
    assert results[0].comment_id == "c-1"
    assert results[1].reply_id == "r-2"
    assert gdrive_source._get.await_count == 2
