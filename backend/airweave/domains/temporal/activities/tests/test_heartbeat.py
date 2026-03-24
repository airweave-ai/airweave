"""Tests for HeartbeatMonitor and heartbeat helpers."""

import asyncio
import json
import time
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

import pytest

from airweave.core.context import BaseContext
from airweave.domains.temporal.activities.heartbeat import (
    REDIS_SNAPSHOT_KEY_PREFIX,
    STACK_DUMP_CHUNK_SIZE,
    STACK_DUMP_INTERVAL_S,
    STALL_THRESHOLD_S,
    HeartbeatMonitor,
    check_redis_snapshot,
    emit_stack_dump,
)

SYNC_ID = UUID("00000000-0000-0000-0000-000000000010")
SYNC_JOB_ID = UUID("00000000-0000-0000-0000-000000000020")

MODULE = "airweave.domains.temporal.activities.heartbeat"


def _make_sync():
    sync = MagicMock()
    sync.id = SYNC_ID
    return sync


def _make_sync_job():
    job = MagicMock()
    job.id = SYNC_JOB_ID
    return job


def _make_ctx():
    from datetime import datetime, timezone

    from airweave import schemas

    org = schemas.Organization(
        id=UUID("00000000-0000-0000-0000-000000000001"),
        name="Test",
        created_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
        modified_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
    )
    return BaseContext(organization=org)


# ── emit_stack_dump() ────────────────────────────────────────────────


@pytest.mark.unit
def test_emit_stack_dump_logs_traces():
    logger = MagicMock()
    with patch(f"{MODULE}.asyncio.all_tasks", return_value=[]):
        emit_stack_dump("test_reason", 120, SYNC_ID, SYNC_JOB_ID, logger)

    assert logger.debug.call_count >= 2
    first_call_args = logger.debug.call_args_list[0]
    assert "STACK_TRACE_DUMP" in first_call_args[0][0]
    assert "part=threads" in first_call_args[0][0]


@pytest.mark.unit
def test_emit_stack_dump_chunks_large_async_traces():
    logger = MagicMock()
    many_tasks = []
    for i in range(100):
        task = MagicMock()
        task.done.return_value = False
        task.get_name.return_value = f"task-{i}"
        coro = MagicMock()
        coro.cr_frame = MagicMock()
        coro.cr_frame.f_code.co_filename = f"/path/to/file_{i}.py"
        coro.cr_frame.f_lineno = i
        coro.cr_frame.f_code.co_name = f"func_{i}"
        task.get_coro.return_value = coro
        many_tasks.append(task)

    with patch(f"{MODULE}.asyncio.all_tasks", return_value=many_tasks):
        emit_stack_dump("test", 300, SYNC_ID, SYNC_JOB_ID, logger)

    assert logger.debug.call_count >= 2


# ── check_redis_snapshot() ──────────────────────────────────────────


@pytest.mark.unit
async def test_check_redis_snapshot_success():
    snapshot = {"inserted": 5, "updated": 3}
    mock_redis = AsyncMock()
    mock_redis.get.return_value = json.dumps(snapshot)

    mock_rc = MagicMock()
    mock_rc.client = mock_redis
    with patch(f"{MODULE}.redis_client", mock_rc):
        result = await check_redis_snapshot(SYNC_JOB_ID)

    assert result == snapshot


@pytest.mark.unit
async def test_check_redis_snapshot_empty():
    mock_redis = AsyncMock()
    mock_redis.get.return_value = None

    mock_rc = MagicMock()
    mock_rc.client = mock_redis
    with patch(f"{MODULE}.redis_client", mock_rc):
        result = await check_redis_snapshot(SYNC_JOB_ID)

    assert result is None


@pytest.mark.unit
async def test_check_redis_snapshot_exception():
    mock_redis = AsyncMock()
    mock_redis.get.side_effect = RuntimeError("redis down")

    mock_rc = MagicMock()
    mock_rc.client = mock_redis
    with patch(f"{MODULE}.redis_client", mock_rc):
        result = await check_redis_snapshot(SYNC_JOB_ID)

    assert result is None


# ── HeartbeatMonitor ────────────────────────────────────────────────


@pytest.mark.unit
async def test_heartbeat_monitor_completes_on_task_done():
    sync = _make_sync()
    sync_job = _make_sync_job()
    ctx = _make_ctx()

    monitor = HeartbeatMonitor(sync, sync_job, ctx)

    async def quick_task():
        return "done"

    task = asyncio.create_task(quick_task())
    with patch(f"{MODULE}.activity") as mock_activity:
        await monitor.run(task)


@pytest.mark.unit
async def test_heartbeat_monitor_heartbeats_while_waiting():
    sync = _make_sync()
    sync_job = _make_sync_job()
    ctx = _make_ctx()

    monitor = HeartbeatMonitor(sync, sync_job, ctx)

    call_count = 0

    async def slow_task():
        nonlocal call_count
        while call_count < 3:
            await asyncio.sleep(0.01)

    task = asyncio.create_task(slow_task())

    original_wait = asyncio.wait

    async def fast_wait(tasks, **kwargs):
        nonlocal call_count
        call_count += 1
        return await original_wait(tasks, timeout=0.05)

    with (
        patch(f"{MODULE}.activity") as mock_activity,
        patch(f"{MODULE}.asyncio.wait", side_effect=fast_wait),
        patch.object(monitor, "_check_progress", new_callable=AsyncMock),
    ):
        await monitor.run(task)

    assert call_count >= 3


@pytest.mark.unit
async def test_heartbeat_monitor_check_progress_updates_snapshot():
    sync = _make_sync()
    sync_job = _make_sync_job()
    ctx = _make_ctx()

    monitor = HeartbeatMonitor(sync, sync_job, ctx)
    monitor._start = time.time()
    monitor._last_redis_check = monitor._start - 60

    snapshot = {"last_update_timestamp": "2025-06-01T00:00:00", "inserted": 10}

    with patch(f"{MODULE}.check_redis_snapshot", new_callable=AsyncMock, return_value=snapshot):
        await monitor._check_progress(time.time(), 120)

    assert monitor._last_snapshot == snapshot
    assert monitor._last_known_timestamp == "2025-06-01T00:00:00"
    assert monitor._stall_start is None


@pytest.mark.unit
async def test_heartbeat_monitor_check_progress_no_change_starts_stall():
    sync = _make_sync()
    sync_job = _make_sync_job()
    ctx = _make_ctx()

    monitor = HeartbeatMonitor(sync, sync_job, ctx)
    monitor._start = time.time() - 400
    monitor._last_redis_check = monitor._start
    monitor._last_known_timestamp = "2025-06-01T00:00:00"

    snapshot = {"last_update_timestamp": "2025-06-01T00:00:00", "inserted": 10}

    now = time.time()
    with patch(f"{MODULE}.check_redis_snapshot", new_callable=AsyncMock, return_value=snapshot):
        await monitor._check_progress(now, 400)

    assert monitor._stall_start == now


@pytest.mark.unit
async def test_heartbeat_monitor_check_progress_none_result():
    sync = _make_sync()
    sync_job = _make_sync_job()
    ctx = _make_ctx()

    monitor = HeartbeatMonitor(sync, sync_job, ctx)
    monitor._start = time.time()
    monitor._last_redis_check = monitor._start - 60

    with patch(f"{MODULE}.check_redis_snapshot", new_callable=AsyncMock, return_value=None):
        await monitor._check_progress(time.time(), 120)


@pytest.mark.unit
def test_detect_stall_emits_dump():
    sync = _make_sync()
    sync_job = _make_sync_job()
    ctx = _make_ctx()

    monitor = HeartbeatMonitor(sync, sync_job, ctx)
    now = time.time()
    monitor._stall_start = now - STALL_THRESHOLD_S - 10

    with patch(f"{MODULE}.emit_stack_dump") as mock_dump:
        monitor._detect_stall(now, 600)

    mock_dump.assert_called_once()
    assert monitor._stall_dump_emitted is True


@pytest.mark.unit
def test_detect_stall_no_stall_start():
    sync = _make_sync()
    sync_job = _make_sync_job()
    ctx = _make_ctx()

    monitor = HeartbeatMonitor(sync, sync_job, ctx)
    monitor._stall_start = None

    with patch(f"{MODULE}.emit_stack_dump") as mock_dump:
        monitor._detect_stall(time.time(), 600)

    mock_dump.assert_not_called()


@pytest.mark.unit
def test_detect_stall_already_emitted():
    sync = _make_sync()
    sync_job = _make_sync_job()
    ctx = _make_ctx()

    monitor = HeartbeatMonitor(sync, sync_job, ctx)
    monitor._stall_start = time.time() - STALL_THRESHOLD_S - 10
    monitor._stall_dump_emitted = True

    with patch(f"{MODULE}.emit_stack_dump") as mock_dump:
        monitor._detect_stall(time.time(), 600)

    mock_dump.assert_not_called()


@pytest.mark.unit
def test_maybe_periodic_dump_emits_when_interval_passed():
    sync = _make_sync()
    sync_job = _make_sync_job()
    ctx = _make_ctx()

    monitor = HeartbeatMonitor(sync, sync_job, ctx)
    now = time.time()
    monitor._last_stack_dump = now - STACK_DUMP_INTERVAL_S - 10

    with patch(f"{MODULE}.emit_stack_dump") as mock_dump:
        monitor._maybe_periodic_dump(now, STACK_DUMP_INTERVAL_S + 10)

    mock_dump.assert_called_once()
    assert monitor._last_stack_dump == now


@pytest.mark.unit
def test_maybe_periodic_dump_skips_when_too_soon():
    sync = _make_sync()
    sync_job = _make_sync_job()
    ctx = _make_ctx()

    monitor = HeartbeatMonitor(sync, sync_job, ctx)
    now = time.time()
    monitor._last_stack_dump = now - 10

    with patch(f"{MODULE}.emit_stack_dump") as mock_dump:
        monitor._maybe_periodic_dump(now, 20)

    mock_dump.assert_not_called()


@pytest.mark.unit
def test_build_heartbeat_basic():
    sync = _make_sync()
    sync_job = _make_sync_job()
    ctx = _make_ctx()

    monitor = HeartbeatMonitor(sync, sync_job, ctx)
    data = monitor._build_heartbeat(120, time.time())

    assert data["phase"] == "syncing"
    assert data["elapsed_s"] == 120
    assert "last_progress_at" not in data
    assert "stall_s" not in data


@pytest.mark.unit
def test_build_heartbeat_with_snapshot_and_stall():
    sync = _make_sync()
    sync_job = _make_sync_job()
    ctx = _make_ctx()

    monitor = HeartbeatMonitor(sync, sync_job, ctx)
    monitor._last_known_timestamp = "2025-06-01T00:00:00"
    monitor._last_snapshot = {"inserted": 5, "updated": 3, "deleted": 1, "kept": 2}
    now = time.time()
    monitor._stall_start = now - 60

    data = monitor._build_heartbeat(300, now)

    assert data["last_progress_at"] == "2025-06-01T00:00:00"
    assert data["inserted"] == 5
    assert data["updated"] == 3
    assert data["deleted"] == 1
    assert data["kept"] == 2
    assert data["stall_s"] == 60


@pytest.mark.unit
async def test_heartbeat_monitor_check_progress_skips_when_too_soon():
    sync = _make_sync()
    sync_job = _make_sync_job()
    ctx = _make_ctx()

    monitor = HeartbeatMonitor(sync, sync_job, ctx)
    now = time.time()
    monitor._last_redis_check = now - 5

    with patch(f"{MODULE}.check_redis_snapshot", new_callable=AsyncMock) as mock_check:
        await monitor._check_progress(now, 120)

    mock_check.assert_not_called()
