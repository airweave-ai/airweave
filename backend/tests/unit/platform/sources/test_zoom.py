"""Unit tests for Zoom source connector."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import BaseModel

from airweave.platform.entities.zoom import (
    ZoomMeetingEntity,
    ZoomMeetingParticipantEntity,
    ZoomRecordingEntity,
)
from airweave.platform.sources.zoom import ZoomSource, _parse_dt


class _EmptyZoomConfig(BaseModel):
    """Stand-in config; Zoom source uses config_class=None."""


def _mock_auth(token="my-zoom-token"):
    auth = AsyncMock()
    auth.get_token = AsyncMock(return_value=token)
    auth.force_refresh = AsyncMock(return_value="refreshed-token")
    auth.supports_refresh = True
    auth.provider_kind = "oauth"
    return auth


def _mock_http_client():
    return AsyncMock()


def _mock_logger():
    return MagicMock()


async def _make_zoom_source(token="my-zoom-token", config: BaseModel | None = None):
    return await ZoomSource.create(
        auth=_mock_auth(token),
        logger=_mock_logger(),
        http_client=_mock_http_client(),
        config=config if config is not None else _EmptyZoomConfig(),
    )


# ---------------------------------------------------------------------------
# create()
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_stores_auth():
    """create() should attach the token provider to the instance."""
    auth = _mock_auth("my-zoom-token")
    source = await ZoomSource.create(
        auth=auth,
        logger=_mock_logger(),
        http_client=_mock_http_client(),
        config=_EmptyZoomConfig(),
    )
    assert source.auth is auth


@pytest.mark.asyncio
async def test_create_with_config():
    """create() accepts a Pydantic config model."""
    cfg = _EmptyZoomConfig()
    source = await ZoomSource.create(
        auth=_mock_auth("token"),
        logger=_mock_logger(),
        http_client=_mock_http_client(),
        config=cfg,
    )
    assert source.auth is not None


# ---------------------------------------------------------------------------
# validate()
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_validate_success():
    """validate() should complete when _get succeeds."""
    source = await _make_zoom_source("token")
    with patch.object(
        source, "_get", new_callable=AsyncMock, return_value={"id": "u1"}
    ) as mock_get:
        await source.validate()
        mock_get.assert_awaited_once()
        assert mock_get.call_args[0][0] == "https://api.zoom.us/v2/users/me"


@pytest.mark.asyncio
async def test_validate_failure():
    """validate() should propagate when _get raises."""
    source = await _make_zoom_source("token")
    with patch.object(
        source, "_get", new_callable=AsyncMock, side_effect=RuntimeError("boom")
    ):
        with pytest.raises(RuntimeError, match="boom"):
            await source.validate()


# ---------------------------------------------------------------------------
# _parse_dt()
# ---------------------------------------------------------------------------


def test_parse_dt_none_or_empty():
    """_parse_dt should return None for None or empty string."""
    assert _parse_dt(None) is None
    assert _parse_dt("") is None


def test_parse_dt_valid_iso_z():
    """_parse_dt should parse ISO string with Z suffix."""
    dt = _parse_dt("2024-06-15T12:00:00Z")
    assert dt is not None
    assert dt.year == 2024
    assert dt.month == 6
    assert dt.day == 15


def test_parse_dt_valid_iso_offset():
    """_parse_dt should parse ISO string with +00:00 offset."""
    dt = _parse_dt("2024-01-01T00:00:00+00:00")
    assert dt is not None
    assert dt.year == 2024


def test_parse_dt_invalid_returns_none():
    """_parse_dt should return None for invalid input."""
    assert _parse_dt("not-a-date") is None
    assert _parse_dt("2024-13-45T00:00:00Z") is None


# ---------------------------------------------------------------------------
# _get_current_user()
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_current_user_returns_user():
    """_get_current_user should return user dict from _get."""
    source = await _make_zoom_source("token")
    expected = {"id": "user-123", "email": "user@example.com"}
    with patch.object(source, "_get", new_callable=AsyncMock, return_value=expected) as mock_get:
        result = await source._get_current_user()
        assert result == expected
        mock_get.assert_called_once()
        call_args = mock_get.call_args[0]
        assert call_args[0] == "https://api.zoom.us/v2/users/me"


# ---------------------------------------------------------------------------
# generate_entities()
# ---------------------------------------------------------------------------

_UTC = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)


@pytest.mark.asyncio
async def test_generate_entities_yields_from_all_generators():
    """generate_entities should yield from meetings, past meetings, participants, recordings."""
    source = await _make_zoom_source("token")
    seen = []

    async def fake_meeting_entities(user_id):
        seen.append("meeting")
        yield ZoomMeetingEntity(
            breadcrumbs=[],
            name="Scheduled Meeting",
            created_at=_UTC,
            updated_at=_UTC,
            meeting_id="m1",
            topic="Scheduled Meeting",
        )

    async def fake_past_meeting_entities(user_id):
        seen.append("past_meeting")
        yield ZoomMeetingEntity(
            breadcrumbs=[],
            name="Past Meeting",
            created_at=_UTC,
            updated_at=_UTC,
            meeting_id="m2",
            topic="Past Meeting",
            uuid="uuid-past",
        )

    async def fake_participant_entities(meeting_id, meeting_uuid, topic, breadcrumb):
        seen.append("participant")
        yield ZoomMeetingParticipantEntity(
            breadcrumbs=[breadcrumb],
            name="Participant One",
            created_at=_UTC,
            updated_at=_UTC,
            participant_id="p1",
            participant_name="Participant One",
            meeting_id=meeting_id,
            user_id="u1",
        )

    async def fake_recording_entities(user_id):
        seen.append("recording")
        yield ZoomRecordingEntity(
            breadcrumbs=[],
            name="Recording 1",
            created_at=_UTC,
            updated_at=_UTC,
            recording_id="r1",
            recording_name="Recording 1",
            meeting_id="m2",
            meeting_topic="Past Meeting",
        )

    with patch.object(source, "_get_current_user", new_callable=AsyncMock) as mock_user:
        mock_user.return_value = {"id": "user-1", "email": "u@example.com"}
        with patch.object(
            source, "_generate_meeting_entities", fake_meeting_entities
        ), patch.object(
            source, "_generate_past_meeting_entities", fake_past_meeting_entities
        ), patch.object(
            source, "_generate_participant_entities", fake_participant_entities
        ), patch.object(
            source, "_generate_recording_entities", fake_recording_entities
        ):
            entities = []
            async for e in source.generate_entities():
                entities.append(e)

    assert len(entities) == 4
    assert seen == ["meeting", "past_meeting", "participant", "recording"]
    assert isinstance(entities[0], ZoomMeetingEntity)
    assert entities[0].topic == "Scheduled Meeting"
    assert isinstance(entities[1], ZoomMeetingEntity)
    assert entities[1].topic == "Past Meeting"
    assert isinstance(entities[2], ZoomMeetingParticipantEntity)
    assert entities[2].participant_name == "Participant One"
    assert isinstance(entities[3], ZoomRecordingEntity)
    assert entities[3].recording_id == "r1"


@pytest.mark.asyncio
async def test_generate_entities_calls_get_current_user_once():
    """generate_entities should call _get_current_user once and pass user_id to generators."""
    source = await _make_zoom_source("token")
    user_ids_seen = []

    async def capture_meeting(user_id):
        user_ids_seen.append(("meeting", user_id))
        return
        yield  # makes this an async generator that yields nothing

    async def capture_past(user_id):
        user_ids_seen.append(("past", user_id))
        return
        yield

    async def capture_recording(user_id):
        user_ids_seen.append(("recording", user_id))
        return
        yield

    with patch.object(source, "_get_current_user", new_callable=AsyncMock) as mock_user:
        mock_user.return_value = {"id": "test-user-id", "email": "u@x.com"}
        with patch.object(source, "_generate_meeting_entities", capture_meeting), patch.object(
            source, "_generate_past_meeting_entities", capture_past
        ), patch.object(
            source, "_generate_recording_entities", capture_recording
        ):
            async for _ in source.generate_entities():
                pass

    assert mock_user.await_count == 1
    assert all(uid == "test-user-id" for _, uid in user_ids_seen)
    assert len(user_ids_seen) == 3
