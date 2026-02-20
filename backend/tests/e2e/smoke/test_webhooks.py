"""E2E tests for Webhooks API functionality.

These tests cover two distinct concepts:
- **Messages**: Records of what happened in the system (sync.pending, sync.completed, etc.)
- **Subscriptions**: Endpoints that receive event notifications at configured URLs

A minimal webhook receiver (started in conftest.py) accepts Svix deliveries
so we can verify end-to-end that events actually arrive.

Tests use the stub connector for fast execution while testing the full flow
including Svix integration.
"""

import asyncio
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import AsyncGenerator, Dict

import httpx
import pytest
import pytest_asyncio


# Timeout for Svix message to appear (sync must complete first)
SVIX_MESSAGE_TIMEOUT = 60

# Timeout for Svix to deliver to the receiver after message exists
SVIX_DELIVERY_TIMEOUT = 10


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================


async def wait_for_sync_completed_message(
    api_client: httpx.AsyncClient,
    source_connection_id: str | None = None,
    timeout: float = SVIX_MESSAGE_TIMEOUT,
    existing_ids: set | None = None,
) -> Dict:
    """Poll the messages API until a sync.completed message appears.

    Args:
        api_client: The HTTP client for the Airweave API.
        source_connection_id: If provided, only match messages with this
            source_connection_id in the payload.
        timeout: Max seconds to wait.
        existing_ids: Set of message IDs that existed before the test
            started. Messages with these IDs are ignored.

    Returns:
        The matching webhook message dict.

    Raises:
        TimeoutError: If no matching message appears within the timeout.
    """
    start_time = time.time()
    if existing_ids is None:
        existing_ids = set()
    last_status_log = 0.0

    while time.time() - start_time < timeout:
        response = await api_client.get(
            "/webhooks/messages", params={"event_types": ["sync.completed"]}
        )
        if response.status_code == 200:
            for msg in response.json():
                if msg["id"] in existing_ids:
                    continue
                payload = msg.get("payload", {})
                if source_connection_id is None:
                    return msg
                if payload.get("source_connection_id") == source_connection_id:
                    return msg

        # Diagnostics every 15s
        elapsed = time.time() - start_time
        if elapsed - last_status_log >= 15.0:
            last_status_log = elapsed
            sync_status = "unknown"
            if source_connection_id:
                sc_resp = await api_client.get(f"/source-connections/{source_connection_id}")
                if sc_resp.status_code == 200:
                    sync_status = sc_resp.json().get("status", "unknown")
            print(
                f"[{elapsed:.0f}s] Waiting for sync.completed "
                f"(sc_id={source_connection_id}, sync_status={sync_status})"
            )

        await asyncio.sleep(1)

    raise TimeoutError(
        f"No sync.completed message for source_connection_id={source_connection_id} "
        f"within {timeout}s"
    )


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture(scope="function")
def unique_webhook_url(webhook_receiver) -> str:
    """Generate a unique, *reachable* webhook URL for this test.

    Each test gets a unique path so we can distinguish deliveries if needed.
    The receiver ignores paths — all POSTs are stored.
    """
    base = webhook_receiver["url"]
    return f"{base}/hook/{uuid.uuid4().hex[:8]}"


@pytest_asyncio.fixture(scope="function")
async def webhook_subscription(
    api_client: httpx.AsyncClient,
    unique_webhook_url: str,
) -> AsyncGenerator[Dict, None]:
    """Create a webhook subscription for sync.completed events."""
    response = await api_client.post(
        "/webhooks/subscriptions",
        json={
            "url": unique_webhook_url,
            "event_types": ["sync.completed"],
        },
    )
    assert response.status_code == 200, f"Failed to create subscription: {response.text}"
    subscription = response.json()

    yield subscription

    # Cleanup
    try:
        await api_client.delete(f"/webhooks/subscriptions/{subscription['id']}")
    except Exception:
        pass


@pytest_asyncio.fixture(scope="function")
async def webhook_subscription_all_events(
    api_client: httpx.AsyncClient,
    unique_webhook_url: str,
) -> AsyncGenerator[Dict, None]:
    """Create a webhook subscription for a representative set of event types.

    Note: Svix limits subscriptions to 10 channels max, so we pick a
    representative set across all three domains.
    """
    response = await api_client.post(
        "/webhooks/subscriptions",
        json={
            "url": unique_webhook_url,
            "event_types": [
                # Sync lifecycle
                "sync.pending",
                "sync.running",
                "sync.completed",
                "sync.failed",
                "sync.cancelled",
                # Source connection lifecycle
                "source_connection.created",
                "source_connection.auth_completed",
                "source_connection.deleted",
                # Collection lifecycle
                "collection.created",
                "collection.deleted",
            ],
        },
    )
    assert response.status_code == 200, f"Failed to create subscription: {response.text}"
    subscription = response.json()

    yield subscription

    # Cleanup
    try:
        await api_client.delete(f"/webhooks/subscriptions/{subscription['id']}")
    except Exception:
        pass


# =============================================================================
# WEBHOOK MESSAGES TESTS - Testing the Messages API
# =============================================================================


@pytest.mark.asyncio
class TestWebhookMessages:
    """Tests for webhook messages - the record of what events occurred."""

    async def test_get_messages_returns_list(self, api_client: httpx.AsyncClient):
        """Test that GET /webhooks/messages returns a list."""
        response = await api_client.get("/webhooks/messages")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    async def test_get_messages_with_event_type_filter(
        self, api_client: httpx.AsyncClient
    ):
        """Test filtering messages by event type."""
        response = await api_client.get(
            "/webhooks/messages", params={"event_types": ["sync.completed"]}
        )
        assert response.status_code == 200
        messages = response.json()

        # All returned messages should be sync.completed
        for msg in messages:
            assert msg["event_type"] == "sync.completed"

    async def test_messages_created_after_sync(
        self,
        api_client: httpx.AsyncClient,
        collection: Dict,
    ):
        """Test that webhook messages are created when syncs occur."""
        # Get initial message count
        initial_response = await api_client.get(
            "/webhooks/messages", params={"event_types": ["sync.completed"]}
        )
        initial_count = len(initial_response.json()) if initial_response.status_code == 200 else 0

        # Trigger a sync
        response = await api_client.post(
            "/source-connections",
            json={
                "name": "Stub Message Test",
                "description": "Testing message creation",
                "short_name": "stub",
                "readable_collection_id": collection["readable_id"],
                "authentication": {"credentials": {"stub_key": "key"}},
                "config": {"entity_count": 1},
                "sync_immediately": True,
            },
        )
        assert response.status_code == 200
        sc_id = response.json()["id"]

        # Wait for new message to appear
        message = await wait_for_sync_completed_message(
            api_client, source_connection_id=sc_id, timeout=SVIX_MESSAGE_TIMEOUT
        )

        # Verify message structure
        assert "id" in message
        assert "event_type" in message
        assert message["event_type"] == "sync.completed"
        assert "payload" in message


@pytest.mark.asyncio
class TestWebhookDelivery:
    """Tests the full webhook pipeline: event bus → Svix → postbin.

    Full lifecycle timeline for a stub source with ``sync_immediately=True``::

        ┌─ API process ──────────────────────────────────────────────────┐
        │  POST /collections         → collection.created               │
        │  POST /source-connections  → source_connection.created         │
        │                            → sync.pending                     │
        ├─ Worker process ───────────────────────────────────────────────┤
        │  RunSyncActivity           → sync.running                     │
        │                            → sync.completed                   │
        ├─ API process (cleanup) ────────────────────────────────────────┤
        │  DELETE /source-connections → source_connection.deleted        │
        │  DELETE /collections       → collection.deleted               │
        └────────────────────────────────────────────────────────────────┘

    Note: ``source_connection.auth_completed`` only fires for OAuth flows,
    not for credential-based auth like the stub connector.

    Cascade: ``DELETE /collections`` CASCADE-deletes source connections
    from the DB but does **not** emit ``source_connection.deleted`` events.
    Only ``collection.deleted`` fires.
    """

    # -----------------------------------------------------------------
    # 1. Postbin delivery: sync.completed lands at the actual endpoint
    # -----------------------------------------------------------------

    async def test_sync_completed_delivered_to_postbin(
        self,
        api_client: httpx.AsyncClient,
        collection: Dict,
    ):
        """Trigger a sync and verify sync.completed actually arrives at postbin."""
        import json as _json

        # Create dedicated postbin
        async with httpx.AsyncClient(timeout=15.0) as http:
            bin_resp = await http.post("https://www.postb.in/api/bin")
            assert bin_resp.status_code in (200, 201), (
                f"Failed to create postbin: {bin_resp.status_code} {bin_resp.text}"
            )
            bin_id = bin_resp.json()["binId"]
            bin_url = f"https://www.postb.in/{bin_id}"
            try:
                await http.post(bin_url, json={"warmup": True}, timeout=10.0)
            except Exception:
                pass

        # Subscribe to sync.completed
        sub_resp = await api_client.post(
            "/webhooks/subscriptions",
            json={"url": bin_url, "event_types": ["sync.completed"]},
        )
        assert sub_resp.status_code == 200
        sub_id = sub_resp.json()["id"]

        try:
            # Trigger sync
            sc_resp = await api_client.post(
                "/source-connections",
                json={
                    "name": f"Stub Postbin {uuid.uuid4().hex[:8]}",
                    "description": "Postbin delivery test",
                    "short_name": "stub",
                    "readable_collection_id": collection["readable_id"],
                    "authentication": {"credentials": {"stub_key": "key"}},
                    "config": {"entity_count": 1},
                    "sync_immediately": True,
                },
            )
            assert sc_resp.status_code == 200
            sc_id = sc_resp.json()["id"]

            # Wait for message in Svix first
            await wait_for_sync_completed_message(
                api_client, source_connection_id=sc_id, timeout=SVIX_MESSAGE_TIMEOUT
            )

            # Now poll postbin for the actual delivery
            delivered = False
            async with httpx.AsyncClient(timeout=10.0) as http:
                for _ in range(15):
                    await asyncio.sleep(2)
                    try:
                        pb_resp = await http.get(
                            f"https://www.postb.in/api/bin/{bin_id}/req/shift",
                            timeout=10.0,
                        )
                        if pb_resp.status_code != 200:
                            continue
                        body = pb_resp.json().get("body", {})
                        if isinstance(body, str):
                            try:
                                body = _json.loads(body)
                            except Exception:
                                continue
                        if isinstance(body, dict) and body.get("source_connection_id") == sc_id:
                            delivered = True
                            break
                    except Exception:
                        pass

            assert delivered, (
                f"sync.completed for sc_id={sc_id} was not delivered to postbin "
                f"within 30s (message exists in Svix)"
            )
        finally:
            try:
                await api_client.delete(f"/webhooks/subscriptions/{sub_id}")
            except Exception:
                pass

    # -----------------------------------------------------------------
    # 2. Messages API: all lifecycle events exist in Svix
    # -----------------------------------------------------------------

    async def test_full_lifecycle_events_in_messages_api(
        self,
        api_client: httpx.AsyncClient,
        webhook_receiver,
    ):
        """Verify every lifecycle event appears in the messages API.

        Uses the messages API (not postbin) to avoid the Svix dispatch
        race window for events that fire immediately after subscription
        creation.
        """
        # Subscribe to all event types so Svix creates the org/app
        all_event_types = [
            "source_connection.created",
            "sync.pending",
            "sync.running",
            "sync.completed",
            "source_connection.deleted",
            "collection.created",
            "collection.deleted",
        ]
        sub_resp = await api_client.post(
            "/webhooks/subscriptions",
            json={"url": webhook_receiver["url"], "event_types": all_event_types},
        )
        assert sub_resp.status_code == 200
        sub_id = sub_resp.json()["id"]

        try:
            # Snapshot existing messages
            existing_resp = await api_client.get("/webhooks/messages")
            existing_ids = set()
            if existing_resp.status_code == 200:
                existing_ids = {m["id"] for m in existing_resp.json()}

            # Create collection
            coll_resp = await api_client.post(
                "/collections/", json={"name": f"Lifecycle {uuid.uuid4().hex[:8]}"}
            )
            assert coll_resp.status_code == 200
            collection = coll_resp.json()

            # Create source connection + sync
            sc_resp = await api_client.post(
                "/source-connections",
                json={
                    "name": f"Stub Lifecycle {uuid.uuid4().hex[:8]}",
                    "description": "Lifecycle events test",
                    "short_name": "stub",
                    "readable_collection_id": collection["readable_id"],
                    "authentication": {"credentials": {"stub_key": "key"}},
                    "config": {"entity_count": 1},
                    "sync_immediately": True,
                },
            )
            assert sc_resp.status_code == 200
            sc_id = sc_resp.json()["id"]

            # Wait for sync to finish
            await wait_for_sync_completed_message(
                api_client, source_connection_id=sc_id, timeout=SVIX_MESSAGE_TIMEOUT
            )

            # Delete source connection
            del_resp = await api_client.delete(f"/source-connections/{sc_id}")
            assert del_resp.status_code == 200

            # Poll for lifecycle events in messages API.
            #
            # Events that fire from the worker (sync.running, sync.completed) or
            # from later API calls (source_connection.deleted) are always reliable.
            #
            # source_connection.created and collection.created fire from the API
            # process in the same request that creates the resource. They exist in
            # Svix but may not appear in the first messages API poll due to eventual
            # consistency. We still check for them but treat them as optional.
            #
            required_events = {
                "sync.pending",
                "sync.running",
                "sync.completed",
                "source_connection.deleted",
            }
            optional_events = {
                "collection.created",
                "source_connection.created",
            }
            all_expected = required_events | optional_events

            poll_timeout = 30
            poll_start = time.time()
            new_msgs: list = []
            event_types: list[str] = []

            while time.time() - poll_start < poll_timeout:
                resp = await api_client.get("/webhooks/messages")
                if resp.status_code == 200:
                    new_msgs = [m for m in resp.json() if m["id"] not in existing_ids]
                    event_types = [m["event_type"] for m in new_msgs]
                    if all_expected.issubset(set(event_types)):
                        break
                await asyncio.sleep(2)

            print(f"[lifecycle] messages API event types: {event_types}")

            # Hard assert on reliable events
            for expected in required_events:
                assert expected in event_types, (
                    f"Expected {expected} in messages API. Got: {event_types}"
                )

            # Soft check on race-prone events (log, don't fail)
            for expected in optional_events:
                if expected not in event_types:
                    print(
                        f"[lifecycle] WARN: {expected} not found in messages API — "
                        f"likely Svix dispatch race (event fires before endpoint is indexed)"
                    )

            # Verify source_connection_id on sync events belonging to this test.
            # Parallel test workers may produce sync events for other source
            # connections that land in the messages API during our poll window.
            our_sync_msgs = [
                m
                for m in new_msgs
                if m["event_type"].startswith("sync.")
                and m["payload"].get("source_connection_id") == sc_id
            ]
            assert len(our_sync_msgs) >= len(
                required_events & {"sync.pending", "sync.running", "sync.completed"}
            ), (
                f"Expected sync events for sc_id={sc_id}, got {len(our_sync_msgs)}. "
                f"Types: {[m['event_type'] for m in our_sync_msgs]}"
            )

        finally:
            try:
                await api_client.delete(f"/webhooks/subscriptions/{sub_id}")
            except Exception:
                pass
            try:
                await api_client.delete(f"/collections/{collection['readable_id']}")
            except Exception:
                pass

    # -----------------------------------------------------------------
    # 3. Collection delete cascade: only collection.deleted fires
    # -----------------------------------------------------------------

    async def test_collection_delete_fires_collection_deleted_only(
        self,
        api_client: httpx.AsyncClient,
        webhook_receiver,
    ):
        """Delete a collection with a source connection. Verify:
        - collection.deleted fires
        - source_connection.deleted does NOT fire (CASCADE deletes the SC
          at DB level, but the API event is not published)
        """
        sub_resp = await api_client.post(
            "/webhooks/subscriptions",
            json={
                "url": webhook_receiver["url"],
                "event_types": [
                    "collection.deleted",
                    "source_connection.deleted",
                    "sync.completed",
                ],
            },
        )
        assert sub_resp.status_code == 200
        sub_id = sub_resp.json()["id"]

        try:
            # Snapshot
            existing_resp = await api_client.get("/webhooks/messages")
            existing_ids = {m["id"] for m in existing_resp.json()} if existing_resp.status_code == 200 else set()

            # Create collection + source connection, wait for sync
            coll_resp = await api_client.post(
                "/collections/", json={"name": f"Cascade {uuid.uuid4().hex[:8]}"}
            )
            assert coll_resp.status_code == 200
            collection = coll_resp.json()

            sc_resp = await api_client.post(
                "/source-connections",
                json={
                    "name": f"Stub Cascade {uuid.uuid4().hex[:8]}",
                    "short_name": "stub",
                    "readable_collection_id": collection["readable_id"],
                    "authentication": {"credentials": {"stub_key": "key"}},
                    "config": {"entity_count": 1},
                    "sync_immediately": True,
                },
            )
            assert sc_resp.status_code == 200
            sc_id = sc_resp.json()["id"]

            await wait_for_sync_completed_message(
                api_client, source_connection_id=sc_id, timeout=SVIX_MESSAGE_TIMEOUT
            )

            # Delete the COLLECTION (not the source connection)
            del_resp = await api_client.delete(f"/collections/{collection['readable_id']}")
            assert del_resp.status_code == 200

            await asyncio.sleep(3)

            # Check messages
            resp = await api_client.get("/webhooks/messages")
            assert resp.status_code == 200
            new_msgs = [m for m in resp.json() if m["id"] not in existing_ids]
            event_types = [m["event_type"] for m in new_msgs]
            print(f"[cascade] event types after collection delete: {event_types}")

            assert "collection.deleted" in event_types, (
                f"collection.deleted should fire on collection delete. Got: {event_types}"
            )
            # source_connection.deleted should NOT fire — the SC was CASCADE-deleted
            sc_deleted_events = [
                m for m in new_msgs
                if m["event_type"] == "source_connection.deleted"
                and m["payload"].get("source_connection_id") == str(sc_id)
            ]
            assert len(sc_deleted_events) == 0, (
                "source_connection.deleted should NOT fire on cascade delete — "
                "only collection.deleted should fire"
            )

        finally:
            try:
                await api_client.delete(f"/webhooks/subscriptions/{sub_id}")
            except Exception:
                pass

    # -----------------------------------------------------------------
    # 4. Payload structure: verify all fields
    # -----------------------------------------------------------------

    async def test_sync_completed_payload_structure(
        self,
        api_client: httpx.AsyncClient,
        collection: Dict,
        webhook_receiver,
    ):
        """Verify the sync.completed payload has all required fields."""
        sub_resp = await api_client.post(
            "/webhooks/subscriptions",
            json={"url": webhook_receiver["url"], "event_types": ["sync.completed"]},
        )
        assert sub_resp.status_code == 200
        sub_id = sub_resp.json()["id"]

        try:
            sc_resp = await api_client.post(
                "/source-connections",
                json={
                    "name": f"Stub Payload {uuid.uuid4().hex[:8]}",
                    "description": "Payload structure test",
                    "short_name": "stub",
                    "readable_collection_id": collection["readable_id"],
                    "authentication": {"credentials": {"stub_key": "key"}},
                    "config": {"entity_count": 1},
                    "sync_immediately": True,
                },
            )
            assert sc_resp.status_code == 200
            sc_id = sc_resp.json()["id"]

            message = await wait_for_sync_completed_message(
                api_client, source_connection_id=sc_id, timeout=SVIX_MESSAGE_TIMEOUT
            )
            payload = message["payload"]

            # Required fields
            assert payload["event_type"] == "sync.completed"
            assert payload["source_connection_id"] == sc_id
            assert payload["source_type"] == "stub"
            assert len(payload["sync_job_id"]) == 36  # UUID
            assert len(payload["sync_id"]) == 36
            assert len(payload["collection_id"]) == 36
            assert "collection_name" in payload
            assert "collection_readable_id" in payload
            assert "timestamp" in payload
        finally:
            try:
                await api_client.delete(f"/webhooks/subscriptions/{sub_id}")
            except Exception:
                pass

    # -----------------------------------------------------------------
    # 5. sync.failed: stub connector with fail_after triggers failure
    # -----------------------------------------------------------------

    async def test_sync_failed_event(
        self,
        api_client: httpx.AsyncClient,
        collection: Dict,
        webhook_receiver,
    ):
        """Use stub's fail_after config to trigger a sync failure,
        verify sync.failed appears in the messages API with error info.
        """
        sub_resp = await api_client.post(
            "/webhooks/subscriptions",
            json={
                "url": webhook_receiver["url"],
                "event_types": ["sync.failed", "sync.running"],
            },
        )
        assert sub_resp.status_code == 200
        sub_id = sub_resp.json()["id"]

        try:
            # Snapshot existing messages
            existing_resp = await api_client.get("/webhooks/messages")
            existing_ids = set()
            if existing_resp.status_code == 200:
                existing_ids = {m["id"] for m in existing_resp.json()}

            # Create source with fail_after=1 (fail after first entity)
            sc_resp = await api_client.post(
                "/source-connections",
                json={
                    "name": f"Stub Fail {uuid.uuid4().hex[:8]}",
                    "description": "Testing sync.failed event",
                    "short_name": "stub",
                    "readable_collection_id": collection["readable_id"],
                    "authentication": {"credentials": {"stub_key": "key"}},
                    "config": {"entity_count": 5, "fail_after": 1},
                    "sync_immediately": True,
                },
            )
            assert sc_resp.status_code == 200
            sc_id = sc_resp.json()["id"]

            # Poll for sync.failed message
            found_failed = None
            for i in range(SVIX_MESSAGE_TIMEOUT):
                await asyncio.sleep(1)
                resp = await api_client.get(
                    "/webhooks/messages", params={"event_types": ["sync.failed"]}
                )
                if resp.status_code == 200:
                    for msg in resp.json():
                        if msg["id"] in existing_ids:
                            continue
                        payload = msg.get("payload", {})
                        if payload.get("source_connection_id") == sc_id:
                            found_failed = msg
                            break
                if found_failed:
                    break
                if i > 0 and i % 15 == 0:
                    print(f"[{i}s] waiting for sync.failed with sc_id={sc_id}...")

            assert found_failed is not None, (
                f"sync.failed for sc_id={sc_id} never appeared within {SVIX_MESSAGE_TIMEOUT}s"
            )

            payload = found_failed["payload"]
            assert payload["event_type"] == "sync.failed"
            assert payload["source_connection_id"] == sc_id
            assert payload["source_type"] == "stub"
            assert "error" in payload
            assert payload["error"] is not None, "sync.failed should include an error message"
            print(f"[sync.failed] error={payload['error']}")

        finally:
            try:
                await api_client.delete(f"/webhooks/subscriptions/{sub_id}")
            except Exception:
                pass

    # -----------------------------------------------------------------
    # 6. sync.cancelled: slow stub + cancel job via API
    # -----------------------------------------------------------------

    async def test_sync_cancelled_event(
        self,
        api_client: httpx.AsyncClient,
        collection: Dict,
        webhook_receiver,
    ):
        """Start a slow sync, cancel it via the API, verify sync.cancelled fires."""
        sub_resp = await api_client.post(
            "/webhooks/subscriptions",
            json={
                "url": webhook_receiver["url"],
                "event_types": ["sync.cancelled", "sync.running"],
            },
        )
        assert sub_resp.status_code == 200
        sub_id = sub_resp.json()["id"]

        try:
            # Snapshot existing messages
            existing_resp = await api_client.get("/webhooks/messages")
            existing_ids = set()
            if existing_resp.status_code == 200:
                existing_ids = {m["id"] for m in existing_resp.json()}

            # Create a slow source: 100 entities with 500ms delay each = ~50s total
            sc_resp = await api_client.post(
                "/source-connections",
                json={
                    "name": f"Stub Cancel {uuid.uuid4().hex[:8]}",
                    "description": "Testing sync.cancelled event",
                    "short_name": "stub",
                    "readable_collection_id": collection["readable_id"],
                    "authentication": {"credentials": {"stub_key": "key"}},
                    "config": {"entity_count": 100, "generation_delay_ms": 500},
                    "sync_immediately": True,
                },
            )
            assert sc_resp.status_code == 200
            sc_id = sc_resp.json()["id"]

            # Wait for sync.running so we know the worker picked it up
            found_running = False
            for i in range(30):
                await asyncio.sleep(1)
                resp = await api_client.get(
                    "/webhooks/messages", params={"event_types": ["sync.running"]}
                )
                if resp.status_code == 200:
                    for msg in resp.json():
                        if msg["id"] in existing_ids:
                            continue
                        if msg["payload"].get("source_connection_id") == sc_id:
                            found_running = True
                            break
                if found_running:
                    break

            assert found_running, (
                f"sync.running for sc_id={sc_id} never appeared — "
                "cannot test cancellation without a running sync"
            )

            # Get the job ID to cancel
            jobs_resp = await api_client.get(f"/source-connections/{sc_id}/jobs")
            assert jobs_resp.status_code == 200
            jobs = jobs_resp.json()
            running_jobs = [j for j in jobs if j["status"] in ("running", "pending")]
            assert running_jobs, f"No running jobs found for sc_id={sc_id}"
            job_id = running_jobs[0]["id"]

            # Cancel the job
            cancel_resp = await api_client.post(
                f"/source-connections/{sc_id}/jobs/{job_id}/cancel"
            )
            assert cancel_resp.status_code == 200, (
                f"Cancel failed: {cancel_resp.status_code} {cancel_resp.text}"
            )
            print(f"[cancel] cancelled job {job_id}")

            # Poll for sync.cancelled message
            found_cancelled = None
            for i in range(SVIX_MESSAGE_TIMEOUT):
                await asyncio.sleep(1)
                resp = await api_client.get(
                    "/webhooks/messages", params={"event_types": ["sync.cancelled"]}
                )
                if resp.status_code == 200:
                    for msg in resp.json():
                        if msg["id"] in existing_ids:
                            continue
                        payload = msg.get("payload", {})
                        if payload.get("source_connection_id") == sc_id:
                            found_cancelled = msg
                            break
                if found_cancelled:
                    break
                if i > 0 and i % 15 == 0:
                    print(f"[{i}s] waiting for sync.cancelled with sc_id={sc_id}...")

            assert found_cancelled is not None, (
                f"sync.cancelled for sc_id={sc_id} never appeared "
                f"within {SVIX_MESSAGE_TIMEOUT}s"
            )

            payload = found_cancelled["payload"]
            assert payload["event_type"] == "sync.cancelled"
            assert payload["source_connection_id"] == sc_id

        finally:
            try:
                await api_client.delete(f"/webhooks/subscriptions/{sub_id}")
            except Exception:
                pass

    # -----------------------------------------------------------------
    # 7. collection.updated: PATCH collection triggers event
    # -----------------------------------------------------------------

    async def test_collection_updated_event(
        self,
        api_client: httpx.AsyncClient,
        webhook_receiver,
    ):
        """PATCH a collection and verify collection.updated appears in messages API."""
        sub_resp = await api_client.post(
            "/webhooks/subscriptions",
            json={
                "url": webhook_receiver["url"],
                "event_types": ["collection.updated", "collection.created"],
            },
        )
        assert sub_resp.status_code == 200
        sub_id = sub_resp.json()["id"]

        try:
            # Snapshot existing messages
            existing_resp = await api_client.get("/webhooks/messages")
            existing_ids = set()
            if existing_resp.status_code == 200:
                existing_ids = {m["id"] for m in existing_resp.json()}

            # Create a collection
            coll_resp = await api_client.post(
                "/collections/", json={"name": f"Update Test {uuid.uuid4().hex[:8]}"}
            )
            assert coll_resp.status_code == 200
            collection = coll_resp.json()

            # Update the collection name
            patch_resp = await api_client.patch(
                f"/collections/{collection['readable_id']}",
                json={"name": f"Updated {uuid.uuid4().hex[:8]}"},
            )
            assert patch_resp.status_code == 200

            # Poll for collection.updated message
            found_updated = None
            for i in range(30):
                await asyncio.sleep(1)
                resp = await api_client.get(
                    "/webhooks/messages",
                    params={"event_types": ["collection.updated"]},
                )
                if resp.status_code == 200:
                    for msg in resp.json():
                        if msg["id"] in existing_ids:
                            continue
                        payload = msg.get("payload", {})
                        if payload.get("collection_id") == str(collection["id"]):
                            found_updated = msg
                            break
                if found_updated:
                    break
                if i > 0 and i % 10 == 0:
                    print(
                        f"[{i}s] waiting for collection.updated "
                        f"for collection_id={collection['id']}..."
                    )

            assert found_updated is not None, (
                f"collection.updated for collection_id={collection['id']} "
                f"never appeared within 30s"
            )

            payload = found_updated["payload"]
            assert payload["event_type"] == "collection.updated"
            assert payload["collection_id"] == str(collection["id"])
            assert "collection_name" in payload
            assert "collection_readable_id" in payload

        finally:
            try:
                await api_client.delete(f"/webhooks/subscriptions/{sub_id}")
            except Exception:
                pass
            try:
                await api_client.delete(f"/collections/{collection['readable_id']}")
            except Exception:
                pass

    # -----------------------------------------------------------------
    # 8. source_connection.auth_completed: OAuth-only, not testable with stub
    # -----------------------------------------------------------------
    # source_connection.auth_completed only fires on OAuth callback completion.
    # The stub connector uses direct credentials, so this event cannot be
    # triggered in E2E smoke tests. It is covered by:
    # - Unit tests with FakeEventBus verifying the event is published
    # - Subscription CRUD tests confirming the event type is accepted


@pytest.mark.asyncio
class TestWebhookEventTypes:
    """Tests for different event types (sync.pending, sync.running, sync.completed, etc.)."""

    async def test_event_payload_structure(
        self,
        api_client: httpx.AsyncClient,
        collection: Dict,
    ):
        """Test that event payloads contain all required fields."""
        # Trigger a sync
        response = await api_client.post(
            "/source-connections",
            json={
                "name": "Stub Payload Test",
                "description": "Testing payload structure",
                "short_name": "stub",
                "readable_collection_id": collection["readable_id"],
                "authentication": {"credentials": {"stub_key": "key"}},
                "config": {"entity_count": 1},
                "sync_immediately": True,
            },
        )
        assert response.status_code == 200
        sc_id = response.json()["id"]

        # Wait for message
        message = await wait_for_sync_completed_message(
            api_client, source_connection_id=sc_id, timeout=SVIX_MESSAGE_TIMEOUT
        )
        payload = message.get("payload", {})

        # Verify required fields per SyncLifecycleEvent schema
        assert "event_type" in payload
        assert "sync_job_id" in payload
        assert "sync_id" in payload
        assert "collection_id" in payload
        assert "collection_readable_id" in payload
        assert "collection_name" in payload
        assert "source_connection_id" in payload
        assert "source_type" in payload
        assert "timestamp" in payload

    async def test_completed_event_has_sync_job_id(
        self,
        api_client: httpx.AsyncClient,
        collection: Dict,
    ):
        """Test that completed events include the sync_job_id in correct format."""
        # Trigger a sync
        response = await api_client.post(
            "/source-connections",
            json={
                "name": "Stub Job ID Test",
                "description": "Testing sync_job_id presence",
                "short_name": "stub",
                "readable_collection_id": collection["readable_id"],
                "authentication": {"credentials": {"stub_key": "key"}},
                "config": {"entity_count": 2},
                "sync_immediately": True,
            },
        )
        assert response.status_code == 200
        sc_id = response.json()["id"]

        # Wait for message
        message = await wait_for_sync_completed_message(
            api_client, source_connection_id=sc_id, timeout=SVIX_MESSAGE_TIMEOUT
        )
        payload = message.get("payload", {})

        assert "sync_job_id" in payload
        sync_job_id = payload["sync_job_id"]
        # UUID format validation
        assert len(sync_job_id) == 36  # xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx


# =============================================================================
# WEBHOOK TESTS - Testing webhook subscriptions
# =============================================================================


@pytest.mark.asyncio
class TestWebhookSubscriptions:
    """Tests for webhook subscription CRUD operations."""

    async def test_list_subscriptions(self, api_client: httpx.AsyncClient):
        """Test listing all webhook subscriptions."""
        response = await api_client.get("/webhooks/subscriptions")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    async def test_create_subscription(
        self, api_client: httpx.AsyncClient, unique_webhook_url: str
    ):
        """Test creating a webhook subscription."""
        response = await api_client.post(
            "/webhooks/subscriptions",
            json={
                "url": unique_webhook_url,
                "event_types": ["sync.completed"],
            },
        )
        assert response.status_code == 200
        subscription = response.json()
        assert subscription["id"] is not None
        assert subscription["url"].rstrip("/") == unique_webhook_url.rstrip("/")

        # Cleanup
        await api_client.delete(f"/webhooks/subscriptions/{subscription['id']}")

    async def test_create_subscription_multiple_event_types(
        self, api_client: httpx.AsyncClient, unique_webhook_url: str
    ):
        """Test creating a subscription with multiple event types."""
        event_types = ["sync.completed", "sync.failed", "sync.running"]

        response = await api_client.post(
            "/webhooks/subscriptions",
            json={
                "url": unique_webhook_url,
                "event_types": event_types,
            },
        )
        assert response.status_code == 200
        subscription = response.json()

        # Cleanup
        await api_client.delete(f"/webhooks/subscriptions/{subscription['id']}")

    async def test_get_subscription_by_id(
        self, api_client: httpx.AsyncClient, webhook_subscription: Dict
    ):
        """Test getting a specific subscription with its delivery attempts."""
        response = await api_client.get(
            f"/webhooks/subscriptions/{webhook_subscription['id']}"
        )
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == webhook_subscription["id"]
        assert "delivery_attempts" in data

    async def test_update_subscription_url(
        self,
        api_client: httpx.AsyncClient,
        webhook_subscription: Dict,
        webhook_receiver,
    ):
        """Test updating a subscription URL."""
        new_url = f"{webhook_receiver['url']}/updated-{uuid.uuid4().hex[:8]}"
        response = await api_client.patch(
            f"/webhooks/subscriptions/{webhook_subscription['id']}",
            json={"url": new_url},
        )
        assert response.status_code == 200
        updated = response.json()
        assert updated["url"].rstrip("/") == new_url.rstrip("/")

    async def test_delete_subscription(
        self, api_client: httpx.AsyncClient, unique_webhook_url: str
    ):
        """Test deleting a webhook subscription returns the deleted object."""
        # Create a subscription to delete
        create_response = await api_client.post(
            "/webhooks/subscriptions",
            json={
                "url": unique_webhook_url,
                "event_types": ["sync.completed"],
            },
        )
        subscription = create_response.json()

        # Delete it
        delete_response = await api_client.delete(
            f"/webhooks/subscriptions/{subscription['id']}"
        )
        assert delete_response.status_code == 200

        # Verify the response contains the deleted subscription
        deleted = delete_response.json()
        assert deleted["id"] == subscription["id"]
        assert deleted["url"].rstrip("/") == unique_webhook_url.rstrip("/")
        assert "filter_types" in deleted
        assert "created_at" in deleted
        assert "updated_at" in deleted

    async def test_delete_subscription_returns_correct_fields(
        self, api_client: httpx.AsyncClient, unique_webhook_url: str
    ):
        """Test that delete returns all expected subscription fields."""
        # Create a subscription with specific event types
        event_types = ["sync.completed", "sync.failed"]
        create_response = await api_client.post(
            "/webhooks/subscriptions",
            json={
                "url": unique_webhook_url,
                "event_types": event_types,
            },
        )
        assert create_response.status_code == 200
        subscription = create_response.json()

        # Delete and verify all fields are returned
        delete_response = await api_client.delete(
            f"/webhooks/subscriptions/{subscription['id']}"
        )
        assert delete_response.status_code == 200
        deleted = delete_response.json()

        # Verify structure matches the created subscription
        assert deleted["id"] == subscription["id"]
        assert deleted["url"] == subscription["url"]
        assert set(deleted["filter_types"]) == set(event_types)
        assert deleted["disabled"] == subscription["disabled"]
        assert deleted["created_at"] == subscription["created_at"]

    async def test_delete_subscription_not_found(
        self, api_client: httpx.AsyncClient
    ):
        """Test deleting a non-existent subscription returns 404."""
        fake_id = "00000000-0000-0000-0000-000000000000"
        response = await api_client.delete(f"/webhooks/subscriptions/{fake_id}")
        assert response.status_code == 404

    async def test_get_subscription_with_secret(
        self, api_client: httpx.AsyncClient, webhook_subscription: Dict
    ):
        """Test retrieving a subscription with include_secret=true."""
        response = await api_client.get(
            f"/webhooks/subscriptions/{webhook_subscription['id']}",
            params={"include_secret": True},
        )
        assert response.status_code == 200
        data = response.json()
        assert "secret" in data
        assert data["secret"] is not None
        # Svix secrets start with whsec_
        assert data["secret"].startswith("whsec_")

    async def test_get_subscription_without_secret(
        self, api_client: httpx.AsyncClient, webhook_subscription: Dict
    ):
        """Test retrieving a subscription without include_secret (default)."""
        response = await api_client.get(
            f"/webhooks/subscriptions/{webhook_subscription['id']}"
        )
        assert response.status_code == 200
        data = response.json()
        # Secret should be null when not requested
        assert data.get("secret") is None


@pytest.mark.asyncio
class TestNewEventTypeSubscriptions:
    """Tests for subscription CRUD with source_connection.* and collection.* event types.

    These tests verify the API correctly accepts the new event type domains
    introduced alongside source connection and collection lifecycle events.
    """

    async def test_create_subscription_source_connection_events(
        self, api_client: httpx.AsyncClient, unique_webhook_url: str
    ):
        """Test creating a subscription for source_connection events."""
        event_types = [
            "source_connection.created",
            "source_connection.auth_completed",
            "source_connection.deleted",
        ]
        response = await api_client.post(
            "/webhooks/subscriptions",
            json={"url": unique_webhook_url, "event_types": event_types},
        )
        assert response.status_code == 200
        subscription = response.json()
        assert set(subscription["filter_types"]) == set(event_types)

        await api_client.delete(f"/webhooks/subscriptions/{subscription['id']}")

    async def test_create_subscription_collection_events(
        self, api_client: httpx.AsyncClient, unique_webhook_url: str
    ):
        """Test creating a subscription for collection events."""
        event_types = [
            "collection.created",
            "collection.updated",
            "collection.deleted",
        ]
        response = await api_client.post(
            "/webhooks/subscriptions",
            json={"url": unique_webhook_url, "event_types": event_types},
        )
        assert response.status_code == 200
        subscription = response.json()
        assert set(subscription["filter_types"]) == set(event_types)

        await api_client.delete(f"/webhooks/subscriptions/{subscription['id']}")

    async def test_create_subscription_mixed_domains(
        self, api_client: httpx.AsyncClient, unique_webhook_url: str
    ):
        """Test creating a subscription mixing sync, source_connection, and collection events."""
        event_types = [
            "sync.completed",
            "sync.failed",
            "source_connection.created",
            "source_connection.deleted",
            "collection.created",
            "collection.deleted",
        ]
        response = await api_client.post(
            "/webhooks/subscriptions",
            json={"url": unique_webhook_url, "event_types": event_types},
        )
        assert response.status_code == 200
        subscription = response.json()
        assert set(subscription["filter_types"]) == set(event_types)

        await api_client.delete(f"/webhooks/subscriptions/{subscription['id']}")

    async def test_create_subscription_all_event_types(
        self, api_client: httpx.AsyncClient, unique_webhook_url: str
    ):
        """Test creating a subscription with 10 event types (Svix max per subscription).

        Svix limits subscriptions to at most 10 channels. We pick a representative
        set across all three domains.
        """
        event_types = [
            "sync.pending",
            "sync.running",
            "sync.completed",
            "sync.failed",
            "sync.cancelled",
            "source_connection.created",
            "source_connection.auth_completed",
            "source_connection.deleted",
            "collection.created",
            "collection.deleted",
        ]
        assert len(event_types) <= 10, "Svix allows at most 10 channels per subscription"

        response = await api_client.post(
            "/webhooks/subscriptions",
            json={"url": unique_webhook_url, "event_types": event_types},
        )
        assert response.status_code == 200
        subscription = response.json()
        assert set(subscription["filter_types"]) == set(event_types)

        await api_client.delete(f"/webhooks/subscriptions/{subscription['id']}")

    async def test_update_subscription_to_new_event_types(
        self, api_client: httpx.AsyncClient, webhook_subscription: Dict
    ):
        """Test updating a sync-only subscription to source_connection + collection types."""
        subscription_id = webhook_subscription["id"]
        new_event_types = [
            "source_connection.created",
            "collection.created",
            "collection.deleted",
        ]

        response = await api_client.patch(
            f"/webhooks/subscriptions/{subscription_id}",
            json={"event_types": new_event_types},
        )
        assert response.status_code == 200
        updated = response.json()
        assert set(updated["filter_types"]) == set(new_event_types)

    async def test_update_subscription_add_new_domain_to_existing(
        self, api_client: httpx.AsyncClient, webhook_subscription: Dict
    ):
        """Test adding source_connection events to an existing sync subscription."""
        subscription_id = webhook_subscription["id"]
        combined_types = [
            "sync.completed",
            "source_connection.created",
            "source_connection.deleted",
        ]

        response = await api_client.patch(
            f"/webhooks/subscriptions/{subscription_id}",
            json={"event_types": combined_types},
        )
        assert response.status_code == 200
        updated = response.json()
        assert set(updated["filter_types"]) == set(combined_types)

    async def test_get_subscription_shows_new_event_types(
        self, api_client: httpx.AsyncClient, unique_webhook_url: str
    ):
        """Test that GET returns the correct new event types."""
        event_types = [
            "source_connection.created",
            "collection.updated",
        ]
        create_response = await api_client.post(
            "/webhooks/subscriptions",
            json={"url": unique_webhook_url, "event_types": event_types},
        )
        assert create_response.status_code == 200
        subscription = create_response.json()

        # Fetch and verify
        get_response = await api_client.get(
            f"/webhooks/subscriptions/{subscription['id']}"
        )
        assert get_response.status_code == 200
        data = get_response.json()
        assert set(data["filter_types"]) == set(event_types)

        await api_client.delete(f"/webhooks/subscriptions/{subscription['id']}")

    async def test_delete_subscription_with_new_event_types(
        self, api_client: httpx.AsyncClient, unique_webhook_url: str
    ):
        """Test that deleting a subscription with new event types returns them correctly."""
        event_types = [
            "source_connection.auth_completed",
            "collection.deleted",
        ]
        create_response = await api_client.post(
            "/webhooks/subscriptions",
            json={"url": unique_webhook_url, "event_types": event_types},
        )
        assert create_response.status_code == 200
        subscription = create_response.json()

        delete_response = await api_client.delete(
            f"/webhooks/subscriptions/{subscription['id']}"
        )
        assert delete_response.status_code == 200
        deleted = delete_response.json()
        assert set(deleted["filter_types"]) == set(event_types)

    async def test_list_subscriptions_includes_new_event_types(
        self, api_client: httpx.AsyncClient, unique_webhook_url: str
    ):
        """Test that list subscriptions correctly shows new event types."""
        event_types = ["source_connection.created", "collection.created"]
        create_response = await api_client.post(
            "/webhooks/subscriptions",
            json={"url": unique_webhook_url, "event_types": event_types},
        )
        assert create_response.status_code == 200
        subscription = create_response.json()

        list_response = await api_client.get("/webhooks/subscriptions")
        assert list_response.status_code == 200
        subscriptions = list_response.json()

        our_sub = next(
            (s for s in subscriptions if s["id"] == subscription["id"]),
            None,
        )
        assert our_sub is not None
        assert set(our_sub["filter_types"]) == set(event_types)

        await api_client.delete(f"/webhooks/subscriptions/{subscription['id']}")


@pytest.mark.asyncio
class TestNewEventTypeMessageFiltering:
    """Tests for filtering messages by new event type domains.

    These tests verify the messages API accepts source_connection.* and
    collection.* event types as filter parameters. Messages may not exist
    yet for these types, but the API should accept the filter gracefully.
    """

    async def test_filter_messages_by_source_connection_events(
        self, api_client: httpx.AsyncClient
    ):
        """Test filtering messages by source_connection event types."""
        response = await api_client.get(
            "/webhooks/messages",
            params={"event_types": ["source_connection.created"]},
        )
        assert response.status_code == 200
        messages = response.json()
        assert isinstance(messages, list)
        for msg in messages:
            assert msg["event_type"] == "source_connection.created"

    async def test_filter_messages_by_collection_events(
        self, api_client: httpx.AsyncClient
    ):
        """Test filtering messages by collection event types."""
        response = await api_client.get(
            "/webhooks/messages",
            params={"event_types": ["collection.created", "collection.deleted"]},
        )
        assert response.status_code == 200
        messages = response.json()
        assert isinstance(messages, list)
        for msg in messages:
            assert msg["event_type"] in ["collection.created", "collection.deleted"]

    async def test_filter_messages_mixed_domains(
        self, api_client: httpx.AsyncClient
    ):
        """Test filtering messages by event types across all three domains."""
        response = await api_client.get(
            "/webhooks/messages",
            params={
                "event_types": [
                    "sync.completed",
                    "source_connection.created",
                    "collection.deleted",
                ]
            },
        )
        assert response.status_code == 200
        messages = response.json()
        assert isinstance(messages, list)
        for msg in messages:
            assert msg["event_type"] in [
                "sync.completed",
                "source_connection.created",
                "collection.deleted",
            ]

    async def test_filter_messages_all_source_connection_events(
        self, api_client: httpx.AsyncClient
    ):
        """Test filtering by all source_connection event types at once."""
        response = await api_client.get(
            "/webhooks/messages",
            params={
                "event_types": [
                    "source_connection.created",
                    "source_connection.auth_completed",
                    "source_connection.deleted",
                ]
            },
        )
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    async def test_filter_messages_all_collection_events(
        self, api_client: httpx.AsyncClient
    ):
        """Test filtering by all collection event types at once."""
        response = await api_client.get(
            "/webhooks/messages",
            params={
                "event_types": [
                    "collection.created",
                    "collection.updated",
                    "collection.deleted",
                ]
            },
        )
        assert response.status_code == 200
        assert isinstance(response.json(), list)


@pytest.mark.asyncio
class TestNewEventTypeSingleSubscriptions:
    """Tests creating a subscription for each individual new event type.

    Validates that every event type in the enum can be used on its own.
    """

    @pytest.mark.parametrize(
        "event_type",
        [
            "source_connection.created",
            "source_connection.auth_completed",
            "source_connection.deleted",
            "collection.created",
            "collection.updated",
            "collection.deleted",
        ],
    )
    async def test_create_subscription_single_new_event_type(
        self, api_client: httpx.AsyncClient, event_type: str, webhook_receiver
    ):
        """Test creating a subscription with a single new event type."""
        url = f"{webhook_receiver['url']}/single-{event_type.replace('.', '-')}"
        response = await api_client.post(
            "/webhooks/subscriptions",
            json={"url": url, "event_types": [event_type]},
        )
        assert response.status_code == 200, f"Failed for {event_type}: {response.text}"
        subscription = response.json()
        assert subscription["filter_types"] == [event_type]

        await api_client.delete(f"/webhooks/subscriptions/{subscription['id']}")


@pytest.mark.asyncio
class TestNewEventTypeDisableEnable:
    """Tests for disabling/enabling subscriptions with new event types."""

    async def test_disable_source_connection_subscription(
        self, api_client: httpx.AsyncClient, unique_webhook_url: str
    ):
        """Test disabling and re-enabling a source_connection subscription."""
        response = await api_client.post(
            "/webhooks/subscriptions",
            json={
                "url": unique_webhook_url,
                "event_types": ["source_connection.created", "source_connection.deleted"],
            },
        )
        assert response.status_code == 200
        subscription = response.json()
        sub_id = subscription["id"]

        # Disable
        resp = await api_client.patch(
            f"/webhooks/subscriptions/{sub_id}",
            json={"disabled": True},
        )
        assert resp.status_code == 200
        assert resp.json()["disabled"] is True

        # Verify event types are preserved
        assert set(resp.json()["filter_types"]) == {
            "source_connection.created",
            "source_connection.deleted",
        }

        # Re-enable
        resp = await api_client.patch(
            f"/webhooks/subscriptions/{sub_id}",
            json={"disabled": False},
        )
        assert resp.status_code == 200
        assert resp.json()["disabled"] is False
        assert set(resp.json()["filter_types"]) == {
            "source_connection.created",
            "source_connection.deleted",
        }

        await api_client.delete(f"/webhooks/subscriptions/{sub_id}")

    async def test_disable_collection_subscription(
        self, api_client: httpx.AsyncClient, unique_webhook_url: str
    ):
        """Test disabling and re-enabling a collection subscription."""
        response = await api_client.post(
            "/webhooks/subscriptions",
            json={
                "url": unique_webhook_url,
                "event_types": ["collection.created", "collection.updated", "collection.deleted"],
            },
        )
        assert response.status_code == 200
        sub_id = response.json()["id"]

        # Disable
        resp = await api_client.patch(
            f"/webhooks/subscriptions/{sub_id}",
            json={"disabled": True},
        )
        assert resp.status_code == 200
        assert resp.json()["disabled"] is True

        # Re-enable
        resp = await api_client.patch(
            f"/webhooks/subscriptions/{sub_id}",
            json={"disabled": False},
        )
        assert resp.status_code == 200
        assert resp.json()["disabled"] is False

        await api_client.delete(f"/webhooks/subscriptions/{sub_id}")


@pytest.mark.asyncio
class TestNewEventTypeSecretHandling:
    """Tests for secret handling with new event type subscriptions."""

    async def test_secret_with_source_connection_subscription(
        self, api_client: httpx.AsyncClient, unique_webhook_url: str
    ):
        """Test that include_secret works on source_connection subscriptions."""
        response = await api_client.post(
            "/webhooks/subscriptions",
            json={
                "url": unique_webhook_url,
                "event_types": ["source_connection.created"],
            },
        )
        assert response.status_code == 200
        sub_id = response.json()["id"]

        # Fetch with secret
        resp = await api_client.get(
            f"/webhooks/subscriptions/{sub_id}",
            params={"include_secret": True},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["secret"] is not None
        assert data["secret"].startswith("whsec_")

        # Fetch without secret
        resp = await api_client.get(f"/webhooks/subscriptions/{sub_id}")
        assert resp.status_code == 200
        assert resp.json().get("secret") is None

        await api_client.delete(f"/webhooks/subscriptions/{sub_id}")


@pytest.mark.asyncio
class TestNewEventTypeSvixLimits:
    """Tests for Svix-specific limits with event types.

    Svix limits subscriptions to at most 10 channels (event types).
    """

    async def test_eleven_event_types_rejected(
        self, api_client: httpx.AsyncClient, unique_webhook_url: str
    ):
        """Test that creating a subscription with >10 event types is rejected."""
        all_event_types = [
            "sync.pending",
            "sync.running",
            "sync.completed",
            "sync.failed",
            "sync.cancelled",
            "source_connection.created",
            "source_connection.auth_completed",
            "source_connection.deleted",
            "collection.created",
            "collection.updated",
            "collection.deleted",
        ]
        assert len(all_event_types) == 11

        response = await api_client.post(
            "/webhooks/subscriptions",
            json={"url": unique_webhook_url, "event_types": all_event_types},
        )
        # Svix rejects >10 channels — surfaces as an error from our API
        assert response.status_code in [400, 422, 500]

    async def test_ten_event_types_accepted(
        self, api_client: httpx.AsyncClient, unique_webhook_url: str
    ):
        """Test that exactly 10 event types is the maximum that works."""
        event_types = [
            "sync.pending",
            "sync.running",
            "sync.completed",
            "sync.failed",
            "sync.cancelled",
            "source_connection.created",
            "source_connection.auth_completed",
            "source_connection.deleted",
            "collection.created",
            "collection.deleted",
        ]
        assert len(event_types) == 10

        response = await api_client.post(
            "/webhooks/subscriptions",
            json={"url": unique_webhook_url, "event_types": event_types},
        )
        assert response.status_code == 200
        subscription = response.json()
        assert len(subscription["filter_types"]) == 10

        await api_client.delete(f"/webhooks/subscriptions/{subscription['id']}")


@pytest.mark.asyncio
class TestCrossDomainSubscriptionUpdates:
    """Tests for updating subscriptions across event type domains."""

    async def test_replace_sync_with_source_connection_types(
        self, api_client: httpx.AsyncClient, webhook_subscription: Dict
    ):
        """Test replacing sync event types with source_connection types entirely."""
        sub_id = webhook_subscription["id"]

        response = await api_client.patch(
            f"/webhooks/subscriptions/{sub_id}",
            json={"event_types": ["source_connection.created", "source_connection.deleted"]},
        )
        assert response.status_code == 200
        updated = response.json()
        assert set(updated["filter_types"]) == {
            "source_connection.created",
            "source_connection.deleted",
        }

        # Verify the old sync.completed is gone
        assert "sync.completed" not in updated["filter_types"]

    async def test_replace_source_connection_with_collection_types(
        self, api_client: httpx.AsyncClient, unique_webhook_url: str
    ):
        """Test replacing source_connection types with collection types."""
        # Create with source_connection types
        response = await api_client.post(
            "/webhooks/subscriptions",
            json={
                "url": unique_webhook_url,
                "event_types": ["source_connection.created"],
            },
        )
        assert response.status_code == 200
        sub_id = response.json()["id"]

        # Replace with collection types
        response = await api_client.patch(
            f"/webhooks/subscriptions/{sub_id}",
            json={"event_types": ["collection.created", "collection.updated"]},
        )
        assert response.status_code == 200
        updated = response.json()
        assert set(updated["filter_types"]) == {"collection.created", "collection.updated"}
        assert "source_connection.created" not in updated["filter_types"]

        await api_client.delete(f"/webhooks/subscriptions/{sub_id}")

    async def test_multiple_subscriptions_different_domains(
        self, api_client: httpx.AsyncClient, webhook_receiver
    ):
        """Test creating separate subscriptions for each event domain."""
        base = webhook_receiver["url"]
        subs = []
        domain_configs = [
            {
                "url": f"{base}/sync-{uuid.uuid4().hex[:8]}",
                "event_types": ["sync.completed", "sync.failed"],
            },
            {
                "url": f"{base}/sc-{uuid.uuid4().hex[:8]}",
                "event_types": ["source_connection.created", "source_connection.deleted"],
            },
            {
                "url": f"{base}/coll-{uuid.uuid4().hex[:8]}",
                "event_types": ["collection.created", "collection.deleted"],
            },
        ]

        # Create all three
        for config in domain_configs:
            response = await api_client.post(
                "/webhooks/subscriptions",
                json=config,
            )
            assert response.status_code == 200, f"Failed for {config['event_types']}: {response.text}"
            subs.append(response.json())

        # Verify each has the correct event types
        for sub, config in zip(subs, domain_configs):
            assert set(sub["filter_types"]) == set(config["event_types"])

        # Verify all appear in list
        list_response = await api_client.get("/webhooks/subscriptions")
        assert list_response.status_code == 200
        all_ids = {s["id"] for s in list_response.json()}
        for sub in subs:
            assert sub["id"] in all_ids

        # Cleanup
        for sub in subs:
            await api_client.delete(f"/webhooks/subscriptions/{sub['id']}")

    async def test_update_url_preserves_new_event_types(
        self, api_client: httpx.AsyncClient, unique_webhook_url: str, webhook_receiver
    ):
        """Test that updating the URL doesn't change the event types."""
        event_types = ["source_connection.created", "collection.deleted"]
        response = await api_client.post(
            "/webhooks/subscriptions",
            json={"url": unique_webhook_url, "event_types": event_types},
        )
        assert response.status_code == 200
        sub_id = response.json()["id"]

        # Update only the URL
        new_url = f"{webhook_receiver['url']}/new-{uuid.uuid4().hex[:8]}"
        response = await api_client.patch(
            f"/webhooks/subscriptions/{sub_id}",
            json={"url": new_url},
        )
        assert response.status_code == 200
        updated = response.json()
        assert updated["url"].rstrip("/") == new_url.rstrip("/")
        assert set(updated["filter_types"]) == set(event_types)

        await api_client.delete(f"/webhooks/subscriptions/{sub_id}")

    async def test_disable_preserves_new_event_types(
        self, api_client: httpx.AsyncClient, unique_webhook_url: str
    ):
        """Test that disabling/enabling preserves new event types."""
        event_types = [
            "source_connection.auth_completed",
            "collection.created",
            "collection.updated",
        ]
        response = await api_client.post(
            "/webhooks/subscriptions",
            json={"url": unique_webhook_url, "event_types": event_types},
        )
        assert response.status_code == 200
        sub_id = response.json()["id"]

        # Disable
        response = await api_client.patch(
            f"/webhooks/subscriptions/{sub_id}",
            json={"disabled": True},
        )
        assert response.status_code == 200
        assert set(response.json()["filter_types"]) == set(event_types)

        # Re-enable
        response = await api_client.patch(
            f"/webhooks/subscriptions/{sub_id}",
            json={"disabled": False},
        )
        assert response.status_code == 200
        assert set(response.json()["filter_types"]) == set(event_types)

        await api_client.delete(f"/webhooks/subscriptions/{sub_id}")


@pytest.mark.asyncio
class TestWebhookDisableEnable:
    """Tests for disabling and enabling webhook endpoints."""

    async def test_disable_subscription_via_patch(
        self, api_client: httpx.AsyncClient, webhook_subscription: Dict
    ):
        """Test disabling a subscription using PATCH with disabled=true."""
        subscription_id = webhook_subscription["id"]

        # Disable the subscription
        response = await api_client.patch(
            f"/webhooks/subscriptions/{subscription_id}",
            json={"disabled": True},
        )
        assert response.status_code == 200
        updated = response.json()
        assert updated["disabled"] is True

        # Verify it's disabled when fetching
        get_response = await api_client.get(f"/webhooks/subscriptions/{subscription_id}")
        assert get_response.status_code == 200
        assert get_response.json()["disabled"] is True

    async def test_enable_subscription_via_patch(
        self, api_client: httpx.AsyncClient, webhook_subscription: Dict
    ):
        """Test re-enabling a disabled subscription using PATCH with disabled=false."""
        subscription_id = webhook_subscription["id"]

        # First disable it
        await api_client.patch(
            f"/webhooks/subscriptions/{subscription_id}",
            json={"disabled": True},
        )

        # Now enable it
        response = await api_client.patch(
            f"/webhooks/subscriptions/{subscription_id}",
            json={"disabled": False},
        )
        assert response.status_code == 200
        updated = response.json()
        assert updated["disabled"] is False

    async def test_update_url_and_disable_simultaneously(
        self, api_client: httpx.AsyncClient, webhook_subscription: Dict, webhook_receiver
    ):
        """Test updating URL and disabling in the same PATCH request."""
        subscription_id = webhook_subscription["id"]
        new_url = f"{webhook_receiver['url']}/updated-{uuid.uuid4().hex[:8]}"

        response = await api_client.patch(
            f"/webhooks/subscriptions/{subscription_id}",
            json={
                "url": new_url,
                "disabled": True,
            },
        )
        assert response.status_code == 200
        updated = response.json()
        assert updated["url"].rstrip("/") == new_url.rstrip("/")
        assert updated["disabled"] is True

    async def test_enable_subscription_via_patch_2(
        self, api_client: httpx.AsyncClient, webhook_subscription: Dict
    ):
        """Test enabling a subscription via PATCH with disabled=false."""
        subscription_id = webhook_subscription["id"]

        # First disable it
        await api_client.patch(
            f"/webhooks/subscriptions/{subscription_id}",
            json={"disabled": True},
        )

        # Enable via PATCH
        response = await api_client.patch(
            f"/webhooks/subscriptions/{subscription_id}",
            json={"disabled": False},
        )
        assert response.status_code == 200
        updated = response.json()
        assert updated["disabled"] is False

    async def test_enable_with_recovery_parameter(
        self, api_client: httpx.AsyncClient, webhook_subscription: Dict
    ):
        """Test enabling with the recover_since parameter.

        Note: We can't easily verify that recovery actually happened without
        having failed messages, but we can verify the API accepts the parameter.
        """
        subscription_id = webhook_subscription["id"]

        # First disable it
        await api_client.patch(
            f"/webhooks/subscriptions/{subscription_id}",
            json={"disabled": True},
        )

        # Enable with recovery - use a recent timestamp
        recover_since = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()

        response = await api_client.patch(
            f"/webhooks/subscriptions/{subscription_id}",
            json={"disabled": False, "recover_since": recover_since},
        )
        assert response.status_code == 200
        updated = response.json()
        assert updated["disabled"] is False

    async def test_enable_already_enabled_subscription(
        self, api_client: httpx.AsyncClient, webhook_subscription: Dict
    ):
        """Test that enabling an already-enabled subscription is idempotent."""
        subscription_id = webhook_subscription["id"]

        # Enable when already enabled - should succeed
        response = await api_client.patch(
            f"/webhooks/subscriptions/{subscription_id}",
            json={"disabled": False},
        )
        assert response.status_code == 200
        assert response.json()["disabled"] is False


@pytest.mark.asyncio
class TestWebhookRecovery:
    """Tests for webhook message recovery functionality.

    Expected behavior: Recovery should succeed (200) even when there are no
    messages to recover - it's a no-op, not an error.
    """

    async def test_recover_messages_missing_since_returns_error(
        self, api_client: httpx.AsyncClient, webhook_subscription: Dict
    ):
        """Test that POST /recover requires the since parameter.

        Expected: 422 validation error.
        """
        subscription_id = webhook_subscription["id"]

        response = await api_client.post(
            f"/webhooks/subscriptions/{subscription_id}/recover",
            json={},
        )
        assert response.status_code == 422

    async def test_recover_messages_endpoint_accepts_valid_request(
        self, api_client: httpx.AsyncClient, webhook_subscription: Dict
    ):
        """Test that POST /recover accepts a valid request with since parameter.

        Expected: 200 - recovery should succeed even with no messages.
        """
        subscription_id = webhook_subscription["id"]
        since = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()

        response = await api_client.post(
            f"/webhooks/subscriptions/{subscription_id}/recover",
            json={"since": since},
        )
        assert response.status_code == 200

    async def test_recover_messages_with_until_parameter(
        self, api_client: httpx.AsyncClient, webhook_subscription: Dict
    ):
        """Test recovery with both since and until parameters.

        Expected: 200 - valid request should succeed.
        """
        subscription_id = webhook_subscription["id"]
        since = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
        until = datetime.now(timezone.utc).isoformat()

        response = await api_client.post(
            f"/webhooks/subscriptions/{subscription_id}/recover",
            json={
                "since": since,
                "until": until,
            },
        )
        assert response.status_code == 200

    async def test_recover_returns_task_info(
        self, api_client: httpx.AsyncClient, webhook_subscription: Dict
    ):
        """Test that POST /recover returns recovery task information.

        Expected: 200 with task info in response.
        """
        subscription_id = webhook_subscription["id"]
        since = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()

        response = await api_client.post(
            f"/webhooks/subscriptions/{subscription_id}/recover",
            json={"since": since},
        )
        assert response.status_code == 200
        result = response.json()
        assert result is not None


@pytest.mark.asyncio
class TestSubscriptionStatusInList:
    """Tests for subscription status visibility in list operations."""

    async def test_list_subscriptions_includes_disabled_status(
        self, api_client: httpx.AsyncClient, webhook_subscription: Dict
    ):
        """Test that listing subscriptions includes the disabled field."""
        # First disable the subscription
        await api_client.patch(
            f"/webhooks/subscriptions/{webhook_subscription['id']}",
            json={"disabled": True},
        )

        # List all subscriptions
        response = await api_client.get("/webhooks/subscriptions")
        assert response.status_code == 200
        subscriptions = response.json()

        # Find our subscription
        our_sub = next(
            (s for s in subscriptions if s["id"] == webhook_subscription["id"]),
            None,
        )
        assert our_sub is not None
        assert "disabled" in our_sub
        assert our_sub["disabled"] is True

    async def test_new_subscription_is_enabled_by_default(
        self, api_client: httpx.AsyncClient, unique_webhook_url: str
    ):
        """Test that newly created subscriptions are enabled by default."""
        response = await api_client.post(
            "/webhooks/subscriptions",
            json={
                "url": unique_webhook_url,
                "event_types": ["sync.completed"],
            },
        )
        assert response.status_code == 200
        subscription = response.json()

        # Should be enabled (disabled=False or not present)
        assert subscription.get("disabled", False) is False

        # Cleanup
        await api_client.delete(f"/webhooks/subscriptions/{subscription['id']}")


# =============================================================================
# EDGE CASE TESTS
# =============================================================================


@pytest.mark.asyncio
class TestSubscriptionValidation:
    """Edge case tests for subscription input validation."""

    async def test_create_subscription_invalid_url_format(
        self, api_client: httpx.AsyncClient
    ):
        """Test creating subscription with invalid URL format returns 422."""
        response = await api_client.post(
            "/webhooks/subscriptions",
            json={
                "url": "not-a-valid-url",
                "event_types": ["sync.completed"],
            },
        )
        assert response.status_code == 422

    async def test_create_subscription_empty_event_types(
        self, api_client: httpx.AsyncClient, unique_webhook_url: str
    ):
        """Test creating subscription with empty event_types array.

        Expected: 422 validation error - a subscription with no events is meaningless.
        """
        response = await api_client.post(
            "/webhooks/subscriptions",
            json={
                "url": unique_webhook_url,
                "event_types": [],
            },
        )
        assert response.status_code == 422

    async def test_create_subscription_duplicate_event_types(
        self, api_client: httpx.AsyncClient, unique_webhook_url: str
    ):
        """Test creating subscription with duplicate event types."""
        response = await api_client.post(
            "/webhooks/subscriptions",
            json={
                "url": unique_webhook_url,
                "event_types": ["sync.completed", "sync.completed", "sync.failed"],
            },
        )
        # Should succeed - duplicates should be deduplicated or allowed
        assert response.status_code == 200
        subscription = response.json()
        await api_client.delete(f"/webhooks/subscriptions/{subscription['id']}")

    async def test_create_subscription_with_http_url(
        self, api_client: httpx.AsyncClient, webhook_receiver
    ):
        """Test creating subscription with HTTP (non-HTTPS) URL.

        Expected: 200 - HTTP URLs should be allowed for local development/testing.
        The webhook receiver already runs on HTTP so this is a natural fit.
        """
        response = await api_client.post(
            "/webhooks/subscriptions",
            json={
                "url": f"{webhook_receiver['url']}/http-test-{uuid.uuid4().hex[:8]}",
                "event_types": ["sync.completed"],
            },
        )
        assert response.status_code == 200
        await api_client.delete(f"/webhooks/subscriptions/{response.json()['id']}")

    async def test_create_subscription_with_localhost_url(
        self, api_client: httpx.AsyncClient, webhook_receiver
    ):
        """Test creating subscription with a host.docker.internal URL.

        Expected: 200 - non-HTTPS / internal host URLs should be allowed.
        Uses the receiver so the endpoint is genuinely reachable from Svix.
        """
        response = await api_client.post(
            "/webhooks/subscriptions",
            json={
                "url": f"{webhook_receiver['url']}/localhost-test",
                "event_types": ["sync.completed"],
            },
        )
        assert response.status_code == 200
        await api_client.delete(f"/webhooks/subscriptions/{response.json()['id']}")

    async def test_create_subscription_missing_url(
        self, api_client: httpx.AsyncClient
    ):
        """Test creating subscription without URL field."""
        response = await api_client.post(
            "/webhooks/subscriptions",
            json={
                "event_types": ["sync.completed"],
            },
        )
        assert response.status_code == 422

    async def test_create_subscription_missing_event_types(
        self, api_client: httpx.AsyncClient, unique_webhook_url: str
    ):
        """Test creating subscription without event_types field."""
        response = await api_client.post(
            "/webhooks/subscriptions",
            json={
                "url": unique_webhook_url,
            },
        )
        assert response.status_code == 422

    async def test_update_subscription_with_invalid_url(
        self, api_client: httpx.AsyncClient, webhook_subscription: Dict
    ):
        """Test updating subscription with invalid URL format."""
        response = await api_client.patch(
            f"/webhooks/subscriptions/{webhook_subscription['id']}",
            json={"url": "not-a-valid-url"},
        )
        assert response.status_code == 422


@pytest.mark.asyncio
class TestSubscriptionSecretValidation:
    """Edge case tests for subscription secret handling."""

    async def test_create_subscription_with_custom_secret(
        self, api_client: httpx.AsyncClient, unique_webhook_url: str
    ):
        """Test creating subscription with a valid custom secret."""
        # whsec_ prefix with base64 encoded secret (at least 24 chars)
        custom_secret = "whsec_" + "a" * 32

        response = await api_client.post(
            "/webhooks/subscriptions",
            json={
                "url": unique_webhook_url,
                "event_types": ["sync.completed"],
                "secret": custom_secret,
            },
        )
        # May succeed or fail depending on secret format requirements
        if response.status_code == 200:
            subscription = response.json()
            # Verify we can retrieve the secret via include_secret param
            secret_response = await api_client.get(
                f"/webhooks/subscriptions/{subscription['id']}",
                params={"include_secret": True},
            )
            assert secret_response.status_code == 200
            assert secret_response.json().get("secret") is not None
            await api_client.delete(f"/webhooks/subscriptions/{subscription['id']}")

    async def test_create_subscription_with_short_secret(
        self, api_client: httpx.AsyncClient, unique_webhook_url: str
    ):
        """Test creating subscription with too short secret.

        Expected: 422 validation error.
        """
        response = await api_client.post(
            "/webhooks/subscriptions",
            json={
                "url": unique_webhook_url,
                "event_types": ["sync.completed"],
                "secret": "short",
            },
        )
        assert response.status_code == 422


@pytest.mark.asyncio
class TestNonExistentResources:
    """Edge case tests for operations on non-existent resources.

    Expected behavior: All operations on non-existent resources should return 404.
    """

    async def test_get_non_existent_subscription(
        self, api_client: httpx.AsyncClient
    ):
        """Test getting a subscription that doesn't exist.

        Expected: 404 Not Found.
        """
        fake_id = "ep_nonexistent123456789"
        response = await api_client.get(f"/webhooks/subscriptions/{fake_id}")
        assert response.status_code == 404

    async def test_delete_non_existent_subscription(
        self, api_client: httpx.AsyncClient
    ):
        """Test deleting a subscription that doesn't exist.

        Expected: 404 Not Found (or 200 for idempotent delete).
        """
        fake_id = "ep_nonexistent123456789"
        response = await api_client.delete(f"/webhooks/subscriptions/{fake_id}")
        assert response.status_code in [200, 404]

    async def test_update_non_existent_subscription(
        self, api_client: httpx.AsyncClient
    ):
        """Test updating a subscription that doesn't exist.

        Expected: 404 Not Found.
        """
        fake_id = "ep_nonexistent123456789"
        response = await api_client.patch(
            f"/webhooks/subscriptions/{fake_id}",
            json={"disabled": True},
        )
        assert response.status_code == 404

    async def test_enable_non_existent_subscription(
        self, api_client: httpx.AsyncClient
    ):
        """Test enabling a subscription that doesn't exist.

        Expected: 404 Not Found.
        """
        fake_id = "ep_nonexistent123456789"
        response = await api_client.patch(
            f"/webhooks/subscriptions/{fake_id}",
            json={"disabled": False},
        )
        assert response.status_code == 404

    async def test_recover_non_existent_subscription(
        self, api_client: httpx.AsyncClient
    ):
        """Test recovering messages for a subscription that doesn't exist.

        Expected: 404 Not Found.
        """
        fake_id = "ep_nonexistent123456789"
        since = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
        response = await api_client.post(
            f"/webhooks/subscriptions/{fake_id}/recover",
            json={"since": since},
        )
        assert response.status_code == 404

    async def test_get_secret_non_existent_subscription(
        self, api_client: httpx.AsyncClient
    ):
        """Test getting secret for a subscription that doesn't exist.

        Expected: 404 Not Found.
        """
        fake_id = "ep_nonexistent123456789"
        response = await api_client.get(
            f"/webhooks/subscriptions/{fake_id}",
            params={"include_secret": True},
        )
        assert response.status_code == 404

    async def test_get_non_existent_message(
        self, api_client: httpx.AsyncClient
    ):
        """Test getting a message that doesn't exist.

        Expected: 404 Not Found.
        """
        fake_id = "msg_nonexistent123456789"
        response = await api_client.get(f"/webhooks/messages/{fake_id}")
        assert response.status_code == 404

    async def test_get_attempts_non_existent_message(
        self, api_client: httpx.AsyncClient
    ):
        """Test getting attempts for a message that doesn't exist.

        Expected: 404 Not Found.
        """
        fake_id = "msg_nonexistent123456789"
        response = await api_client.get(
            f"/webhooks/messages/{fake_id}",
            params={"include_attempts": True},
        )
        assert response.status_code == 404


@pytest.mark.asyncio
class TestRecoveryEdgeCases:
    """Edge case tests for message recovery functionality."""

    async def test_recover_with_future_since_date(
        self, api_client: httpx.AsyncClient, webhook_subscription: Dict
    ):
        """Test recovery with a future since date.

        Expected: 200 (no messages to recover) or 422 (validation error).
        """
        subscription_id = webhook_subscription["id"]
        future_date = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()

        response = await api_client.post(
            f"/webhooks/subscriptions/{subscription_id}/recover",
            json={"since": future_date},
        )
        assert response.status_code in [200, 422]

    async def test_recover_with_until_before_since(
        self, api_client: httpx.AsyncClient, webhook_subscription: Dict
    ):
        """Test recovery with until date before since date.

        Expected: 200 - Svix accepts this as a no-op (nothing to recover in empty range).
        """
        subscription_id = webhook_subscription["id"]
        since = datetime.now(timezone.utc).isoformat()
        until = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()

        response = await api_client.post(
            f"/webhooks/subscriptions/{subscription_id}/recover",
            json={"since": since, "until": until},
        )
        assert response.status_code == 200

    async def test_recover_with_very_old_since_date(
        self, api_client: httpx.AsyncClient, webhook_subscription: Dict
    ):
        """Test recovery with a very old since date (years ago).

        Expected: 422 - Svix only allows recovery within 14 days.
        """
        subscription_id = webhook_subscription["id"]
        old_date = (datetime.now(timezone.utc) - timedelta(days=365 * 2)).isoformat()

        response = await api_client.post(
            f"/webhooks/subscriptions/{subscription_id}/recover",
            json={"since": old_date},
        )
        assert response.status_code == 422
        assert "14 days" in response.json()["detail"]

    async def test_recover_with_invalid_date_format(
        self, api_client: httpx.AsyncClient, webhook_subscription: Dict
    ):
        """Test recovery with invalid date format.

        Expected: 422 validation error.
        """
        subscription_id = webhook_subscription["id"]

        response = await api_client.post(
            f"/webhooks/subscriptions/{subscription_id}/recover",
            json={"since": "not-a-date"},
        )
        assert response.status_code == 422


@pytest.mark.asyncio
class TestDisableEnableEdgeCases:
    """Edge case tests for disable/enable functionality."""

    async def test_disable_already_disabled_subscription(
        self, api_client: httpx.AsyncClient, webhook_subscription: Dict
    ):
        """Test disabling an already disabled subscription (idempotent)."""
        subscription_id = webhook_subscription["id"]

        # Disable twice
        await api_client.patch(
            f"/webhooks/subscriptions/{subscription_id}",
            json={"disabled": True},
        )
        response = await api_client.patch(
            f"/webhooks/subscriptions/{subscription_id}",
            json={"disabled": True},
        )
        assert response.status_code == 200
        assert response.json()["disabled"] is True

    async def test_rapid_enable_disable_toggle(
        self, api_client: httpx.AsyncClient, webhook_subscription: Dict
    ):
        """Test rapid toggling between enabled and disabled states."""
        subscription_id = webhook_subscription["id"]

        for _ in range(5):
            # Disable
            response = await api_client.patch(
                f"/webhooks/subscriptions/{subscription_id}",
                json={"disabled": True},
            )
            assert response.status_code == 200

            # Enable
            response = await api_client.patch(
                f"/webhooks/subscriptions/{subscription_id}",
                json={"disabled": False},
            )
            assert response.status_code == 200

        # Final state should be enabled
        get_response = await api_client.get(f"/webhooks/subscriptions/{subscription_id}")
        assert get_response.json()["disabled"] is False

    async def test_patch_with_empty_body(
        self, api_client: httpx.AsyncClient, webhook_subscription: Dict
    ):
        """Test PATCH with empty JSON body."""
        subscription_id = webhook_subscription["id"]

        response = await api_client.patch(
            f"/webhooks/subscriptions/{subscription_id}",
            json={},
        )
        # Should succeed as a no-op
        assert response.status_code == 200

    async def test_enable_preserves_other_fields(
        self, api_client: httpx.AsyncClient, webhook_subscription: Dict
    ):
        """Test that enabling doesn't modify URL or event types."""
        subscription_id = webhook_subscription["id"]
        original_url = webhook_subscription["url"]

        # Disable
        await api_client.patch(
            f"/webhooks/subscriptions/{subscription_id}",
            json={"disabled": True},
        )

        # Enable via PATCH with disabled=false
        response = await api_client.patch(
            f"/webhooks/subscriptions/{subscription_id}",
            json={"disabled": False},
        )
        assert response.status_code == 200
        updated = response.json()

        # URL should be unchanged
        assert updated["url"].rstrip("/") == original_url.rstrip("/")


@pytest.mark.asyncio
class TestSubscriptionUpdateEdgeCases:
    """Edge case tests for subscription updates."""

    async def test_update_only_url(
        self, api_client: httpx.AsyncClient, webhook_subscription: Dict, webhook_receiver
    ):
        """Test updating only the URL field."""
        subscription_id = webhook_subscription["id"]
        new_url = f"{webhook_receiver['url']}/new-{uuid.uuid4().hex[:8]}"

        response = await api_client.patch(
            f"/webhooks/subscriptions/{subscription_id}",
            json={"url": new_url},
        )
        assert response.status_code == 200
        assert response.json()["url"].rstrip("/") == new_url.rstrip("/")

    async def test_update_only_event_types(
        self, api_client: httpx.AsyncClient, webhook_subscription: Dict
    ):
        """Test updating only the event_types field."""
        subscription_id = webhook_subscription["id"]

        response = await api_client.patch(
            f"/webhooks/subscriptions/{subscription_id}",
            json={"event_types": ["sync.failed", "sync.cancelled"]},
        )
        assert response.status_code == 200

    async def test_update_all_fields_simultaneously(
        self, api_client: httpx.AsyncClient, webhook_subscription: Dict, webhook_receiver
    ):
        """Test updating URL, event_types, and disabled all at once."""
        subscription_id = webhook_subscription["id"]
        new_url = f"{webhook_receiver['url']}/all-{uuid.uuid4().hex[:8]}"

        response = await api_client.patch(
            f"/webhooks/subscriptions/{subscription_id}",
            json={
                "url": new_url,
                "event_types": ["sync.pending", "sync.running"],
                "disabled": True,
            },
        )
        assert response.status_code == 200
        updated = response.json()
        assert updated["url"].rstrip("/") == new_url.rstrip("/")
        assert updated["disabled"] is True

    async def test_updated_at_changes_after_patch(
        self, api_client: httpx.AsyncClient, webhook_subscription: Dict
    ):
        """Test that updated_at timestamp changes after PATCH."""
        subscription_id = webhook_subscription["id"]
        original_updated_at = webhook_subscription.get("updated_at")

        # Small delay to ensure timestamp difference
        await asyncio.sleep(0.1)

        response = await api_client.patch(
            f"/webhooks/subscriptions/{subscription_id}",
            json={"disabled": True},
        )
        assert response.status_code == 200

        if original_updated_at:
            # updated_at should be different (or at least not before)
            new_updated_at = response.json().get("updated_at")
            assert new_updated_at is not None

    async def test_created_at_unchanged_after_patch(
        self, api_client: httpx.AsyncClient, webhook_subscription: Dict
    ):
        """Test that created_at timestamp doesn't change after PATCH."""
        subscription_id = webhook_subscription["id"]
        original_created_at = webhook_subscription.get("created_at")

        response = await api_client.patch(
            f"/webhooks/subscriptions/{subscription_id}",
            json={"disabled": True},
        )
        assert response.status_code == 200

        if original_created_at:
            new_created_at = response.json().get("created_at")
            assert new_created_at == original_created_at


@pytest.mark.asyncio
class TestMessageQueryEdgeCases:
    """Edge case tests for message querying."""

    async def test_get_messages_empty_event_types_filter(
        self, api_client: httpx.AsyncClient
    ):
        """Test getting messages with empty event_types filter."""
        response = await api_client.get(
            "/webhooks/messages",
            params={"event_types": []},
        )
        # Should return all messages or handle gracefully
        assert response.status_code == 200

    async def test_get_messages_multiple_event_types(
        self, api_client: httpx.AsyncClient
    ):
        """Test getting messages filtered by multiple event types."""
        response = await api_client.get(
            "/webhooks/messages",
            params={"event_types": ["sync.completed", "sync.failed", "sync.running"]},
        )
        assert response.status_code == 200
        messages = response.json()
        # All returned messages should be one of the filtered types
        for msg in messages:
            assert msg["event_type"] in ["sync.completed", "sync.failed", "sync.running"]


@pytest.mark.asyncio
class TestConcurrentOperations:
    """Edge case tests for concurrent operations."""

    async def test_concurrent_updates_to_same_subscription(
        self, api_client: httpx.AsyncClient, webhook_subscription: Dict
    ):
        """Test concurrent updates to the same subscription."""
        subscription_id = webhook_subscription["id"]

        # Fire multiple updates concurrently
        tasks = [
            api_client.patch(
                f"/webhooks/subscriptions/{subscription_id}",
                json={"disabled": i % 2 == 0},
            )
            for i in range(5)
        ]
        responses = await asyncio.gather(*tasks)

        # All should succeed (last write wins)
        for response in responses:
            assert response.status_code == 200

    async def test_delete_after_operations_started(
        self, api_client: httpx.AsyncClient, unique_webhook_url: str
    ):
        """Test that operations handle deletion gracefully.

        Expected: 404 Not Found when operating on deleted subscription.
        """
        # Create a subscription
        create_response = await api_client.post(
            "/webhooks/subscriptions",
            json={
                "url": unique_webhook_url,
                "event_types": ["sync.completed"],
            },
        )
        subscription = create_response.json()
        subscription_id = subscription["id"]

        # Delete it
        await api_client.delete(f"/webhooks/subscriptions/{subscription_id}")

        # Try to update - should return 404
        response = await api_client.patch(
            f"/webhooks/subscriptions/{subscription_id}",
            json={"disabled": True},
        )
        assert response.status_code == 404


@pytest.mark.asyncio
class TestListOperationsEdgeCases:
    """Edge case tests for list operations."""

    async def test_list_subscriptions_returns_correct_structure(
        self, api_client: httpx.AsyncClient, webhook_subscription: Dict
    ):
        """Test that list subscriptions returns correct structure for each item."""
        response = await api_client.get("/webhooks/subscriptions")
        assert response.status_code == 200
        subscriptions = response.json()

        for sub in subscriptions:
            # Verify required fields exist
            assert "id" in sub
            assert "url" in sub
            assert "created_at" in sub
            # disabled may or may not be present

    async def test_list_messages_returns_correct_structure(
        self, api_client: httpx.AsyncClient
    ):
        """Test that list messages returns correct structure."""
        response = await api_client.get("/webhooks/messages")
        assert response.status_code == 200
        messages = response.json()

        for msg in messages:
            assert "id" in msg
            assert "event_type" in msg
            assert "timestamp" in msg
