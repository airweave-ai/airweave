"""API tests for sync SSE endpoints.

Tests both SSE subscription endpoints with a faked PubSub injected via DI.
FakePubSubSubscription supports message queuing and error injection so we can
exercise all code paths: message forwarding, heartbeat, error handling, and
close-error suppression.
"""

import asyncio
import json
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest


def _data_lines(text: str) -> list[str]:
    """Extract SSE data payloads from response text."""
    return [ln.removeprefix("data:").strip() for ln in text.splitlines() if ln.startswith("data:")]


# ---------------------------------------------------------------------------
# GET /sync/job/{job_id}/subscribe
# ---------------------------------------------------------------------------


class TestSubscribeSyncJob:
    """Tests for GET /sync/job/{job_id}/subscribe."""

    @pytest.mark.asyncio
    async def test_connected_event(self, client):
        job_id = uuid4()
        response = await client.get(f"/sync/job/{job_id}/subscribe")

        assert response.status_code == 200
        assert "text/event-stream" in response.headers["content-type"]

        lines = _data_lines(response.text)
        first = json.loads(lines[0])
        assert first == {"type": "connected", "job_id": str(job_id)}

    @pytest.mark.asyncio
    async def test_forwards_messages(self, client, fake_pubsub):
        fake_pubsub.queued_messages = [
            {"type": "message", "data": '{"count": 42}'},
            {"type": "subscribe"},
        ]

        response = await client.get(f"/sync/job/{uuid4()}/subscribe")
        lines = _data_lines(response.text)

        assert len(lines) == 2
        assert json.loads(lines[1]) == {"count": 42}

    @pytest.mark.asyncio
    async def test_heartbeat_emitted_when_stale(self, client, fake_pubsub):
        fake_pubsub.queued_messages = [{"type": "message", "data": '"x"'}]

        # subscribe_sync_job calls time() 3 times: connection_id, last_heartbeat, current_time
        times = iter([0.0, 0.0, 31.0])

        with patch("airweave.api.v1.endpoints.sync.asyncio") as mock_mod:
            mock_mod.CancelledError = asyncio.CancelledError
            mock_loop = MagicMock()
            mock_loop.time.side_effect = lambda: next(times, 31.0)
            mock_mod.get_event_loop.return_value = mock_loop

            response = await client.get(f"/sync/job/{uuid4()}/subscribe")

        lines = _data_lines(response.text)
        assert any('"heartbeat"' in ln for ln in lines)

    @pytest.mark.asyncio
    async def test_listen_error_yields_error_event(self, client, fake_pubsub):
        fake_pubsub.listen_error = RuntimeError("boom")

        response = await client.get(f"/sync/job/{uuid4()}/subscribe")
        lines = _data_lines(response.text)

        error_event = json.loads(lines[-1])
        assert error_event["type"] == "error"
        assert "boom" in error_event["message"]

    @pytest.mark.asyncio
    async def test_cancelled_error_handled(self, client, fake_pubsub):
        fake_pubsub.listen_error = asyncio.CancelledError()

        response = await client.get(f"/sync/job/{uuid4()}/subscribe")

        assert response.status_code == 200
        lines = _data_lines(response.text)
        assert len(lines) == 1
        assert json.loads(lines[0])["type"] == "connected"

    @pytest.mark.asyncio
    async def test_close_error_suppressed(self, client, fake_pubsub):
        fake_pubsub.close_error = RuntimeError("close failed")

        response = await client.get(f"/sync/job/{uuid4()}/subscribe")
        assert response.status_code == 200


# ---------------------------------------------------------------------------
# GET /sync/job/{job_id}/subscribe-state
# ---------------------------------------------------------------------------


class TestSubscribeEntityState:
    """Tests for GET /sync/job/{job_id}/subscribe-state."""

    @pytest.mark.asyncio
    async def test_connected_event(self, client):
        job_id = uuid4()
        response = await client.get(f"/sync/job/{job_id}/subscribe-state")

        assert response.status_code == 200
        assert "text/event-stream" in response.headers["content-type"]

        lines = _data_lines(response.text)
        first = json.loads(lines[0])
        assert first == {"type": "connected", "job_id": str(job_id)}

    @pytest.mark.asyncio
    async def test_forwards_messages(self, client, fake_pubsub):
        fake_pubsub.queued_messages = [
            {"type": "message", "data": '{"entities": 10}'},
            {"type": "subscribe"},
        ]

        response = await client.get(f"/sync/job/{uuid4()}/subscribe-state")
        lines = _data_lines(response.text)

        assert len(lines) == 2
        assert json.loads(lines[1]) == {"entities": 10}

    @pytest.mark.asyncio
    async def test_heartbeat_emitted_when_stale(self, client, fake_pubsub):
        fake_pubsub.queued_messages = [{"type": "message", "data": '"x"'}]

        # subscribe_entity_state calls time() 2 times: last_heartbeat, current_time
        times = iter([0.0, 31.0])

        with patch("airweave.api.v1.endpoints.sync.asyncio") as mock_mod:
            mock_mod.CancelledError = asyncio.CancelledError
            mock_loop = MagicMock()
            mock_loop.time.side_effect = lambda: next(times, 31.0)
            mock_mod.get_event_loop.return_value = mock_loop

            response = await client.get(f"/sync/job/{uuid4()}/subscribe-state")

        lines = _data_lines(response.text)
        assert any('"heartbeat"' in ln for ln in lines)

    @pytest.mark.asyncio
    async def test_listen_error_yields_error_event(self, client, fake_pubsub):
        fake_pubsub.listen_error = RuntimeError("exploded")

        response = await client.get(f"/sync/job/{uuid4()}/subscribe-state")
        lines = _data_lines(response.text)

        error_event = json.loads(lines[-1])
        assert error_event["type"] == "error"
        assert "exploded" in error_event["message"]

    @pytest.mark.asyncio
    async def test_cancelled_error_handled(self, client, fake_pubsub):
        fake_pubsub.listen_error = asyncio.CancelledError()

        response = await client.get(f"/sync/job/{uuid4()}/subscribe-state")

        assert response.status_code == 200
        lines = _data_lines(response.text)
        assert len(lines) == 1
        assert json.loads(lines[0])["type"] == "connected"

    @pytest.mark.asyncio
    async def test_close_error_suppressed(self, client, fake_pubsub):
        fake_pubsub.close_error = RuntimeError("close failed")

        response = await client.get(f"/sync/job/{uuid4()}/subscribe-state")
        assert response.status_code == 200
