"""API tests for sync SSE endpoints.

Tests the SSE subscription endpoints with a faked PubSub injected via DI.
FakePubSubSubscription.listen() yields nothing, so the stream emits a
"connected" event and terminates immediately — no hanging, no timeout.
"""

import json
from uuid import uuid4

import pytest


class TestSubscribeEntityState:
    """Tests for GET /sync/job/{job_id}/subscribe-state."""

    @pytest.mark.asyncio
    async def test_returns_sse_stream_with_connected_event(self, client):
        job_id = uuid4()

        response = await client.get(f"/sync/job/{job_id}/subscribe-state")

        assert response.status_code == 200
        assert "text/event-stream" in response.headers["content-type"]

        lines = [ln for ln in response.text.splitlines() if ln.startswith("data:")]
        assert len(lines) >= 1

        first_event = json.loads(lines[0].removeprefix("data:").strip())
        assert first_event["type"] == "connected"
        assert first_event["job_id"] == str(job_id)
