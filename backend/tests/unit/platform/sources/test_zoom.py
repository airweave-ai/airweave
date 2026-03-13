"""Unit tests for Zoom source connector."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from airweave.platform.entities.zoom import (
    ZoomMeetingEntity,
    ZoomMeetingParticipantEntity,
    ZoomRecordingEntity,
)
from airweave.platform.sources.zoom import ZoomSource


# ---------------------------------------------------------------------------
# create()
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_sets_access_token():
    """create() should set access_token on the instance."""
    source = await ZoomSource.create("my-zoom-token", None)
    assert source.access_token == "my-zoom-token"


@pytest.mark.asyncio
async def test_create_with_config():
    """create() with config should still set access_token (config is optional)."""
    source = await ZoomSource.create("token", {"some_key": "value"})
    assert source.access_token == "token"


# ---------------------------------------------------------------------------
# validate()
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_validate_success():
    """validate() should return True when _validate_oauth2 succeeds."""
    source = await ZoomSource.create("token", None)
    with patch.object(
        source, "_validate_oauth2", new_callable=AsyncMock, return_value=True
    ) as mock_validate:
        result = await source.validate()
        assert result is True
        mock_validate.assert_called_once()
        call_kw = mock_validate.call_args[1]
        assert call_kw["ping_url"] == "https://api.zoom.us/v2/users/me"
        assert "Accept" in call_kw["headers"]


@pytest.mark.asyncio
async def test_validate_failure():
    """validate() should return False when _validate_oauth2 fails."""
    source = await ZoomSource.create("token", None)
    with patch.object(
        source, "_validate_oauth2", new_callable=AsyncMock, return_value=False
    ):
        result = await source.validate()
        assert result is False


# ---------------------------------------------------------------------------
# _parse_datetime()
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_parse_datetime_none_or_empty():
    """_parse_datetime should return None for None or empty string."""
    source = await ZoomSource.create("token", None)
    assert source._parse_datetime(None) is None
    assert source._parse_datetime("") is None


@pytest.mark.asyncio
async def test_parse_datetime_valid_iso_z():
    """_parse_datetime should parse ISO string with Z suffix."""
    source = await ZoomSource.create("token", None)
    dt = source._parse_datetime("2024-06-15T12:00:00Z")
    assert dt is not None
    assert dt.year == 2024
    assert dt.month == 6
    assert dt.day == 15


@pytest.mark.asyncio
async def test_parse_datetime_valid_iso_offset():
    """_parse_datetime should parse ISO string with +00:00 offset."""
    source = await ZoomSource.create("token", None)
    dt = source._parse_datetime("2024-01-01T00:00:00+00:00")
    assert dt is not None
    assert dt.year == 2024


@pytest.mark.asyncio
async def test_parse_datetime_invalid_returns_none():
    """_parse_datetime should return None for invalid input."""
    source = await ZoomSource.create("token", None)
    assert source._parse_datetime("not-a-date") is None
    assert source._parse_datetime("2024-13-45T00:00:00Z") is None


# ---------------------------------------------------------------------------
# _get_current_user()
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_current_user_returns_user():
    """_get_current_user should return user dict from _get_with_auth."""
    source = await ZoomSource.create("token", None)
    expected = {"id": "user-123", "email": "user@example.com"}
    with patch.object(
        source, "_get_with_auth", new_callable=AsyncMock, return_value=expected
    ) as mock_get:
        result = await source._get_current_user(AsyncMock())
        assert result == expected
        mock_get.assert_called_once()
        call_args = mock_get.call_args[0]
        assert call_args[1] == "https://api.zoom.us/v2/users/me"


# ---------------------------------------------------------------------------
# generate_entities()
# ---------------------------------------------------------------------------

_UTC = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)


@pytest.mark.asyncio
async def test_generate_entities_yields_from_all_generators():
    """generate_entities should yield from meetings, past meetings, participants, recordings."""
    source = await ZoomSource.create("token", None)
    seen = []

    async def fake_meeting_entities(client, user_id):
        seen.append("meeting")
        yield ZoomMeetingEntity(
            breadcrumbs=[],
            name="Scheduled Meeting",
            created_at=_UTC,
            updated_at=_UTC,
            meeting_id="m1",
            topic="Scheduled Meeting",
        )

    async def fake_past_meeting_entities(client, user_id):
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

    async def fake_participant_entities(client, meeting_id, meeting_uuid, topic, breadcrumb):
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

    async def fake_recording_entities(client, user_id):
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
        ), patch.object(source, "http_client") as mock_http:
            mock_client = MagicMock()
            mock_http.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_http.return_value.__aexit__ = AsyncMock(return_value=None)

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
    source = await ZoomSource.create("token", None)
    user_ids_seen = []

    async def capture_meeting(client, user_id):
        user_ids_seen.append(("meeting", user_id))
        return
        yield  # makes this an async generator that yields nothing

    async def capture_past(client, user_id):
        user_ids_seen.append(("past", user_id))
        return
        yield

    async def capture_recording(client, user_id):
        user_ids_seen.append(("recording", user_id))
        return
        yield

    with patch.object(source, "_get_current_user", new_callable=AsyncMock) as mock_user:
        mock_user.return_value = {"id": "test-user-id", "email": "u@x.com"}
        with patch.object(source, "_generate_meeting_entities", capture_meeting), patch.object(
            source, "_generate_past_meeting_entities", capture_past
        ), patch.object(
            source, "_generate_recording_entities", capture_recording
        ), patch.object(source, "http_client") as mock_http:
            mock_http.return_value.__aenter__ = AsyncMock(return_value=MagicMock())
            mock_http.return_value.__aexit__ = AsyncMock(return_value=None)
            async for _ in source.generate_entities():
                pass

    assert mock_user.await_count == 1
    assert all(uid == "test-user-id" for _, uid in user_ids_seen)
    assert len(user_ids_seen) == 3
