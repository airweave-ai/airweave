"""Heartbeat monitor for sync activities.

Polls a running sync task, sends Temporal heartbeats with progress data,
detects stalls via Redis snapshots, and emits stack dumps for debugging.
"""

from __future__ import annotations

import asyncio
import json
import sys
import time
import traceback
from typing import Any
from uuid import UUID

from temporalio import activity

from airweave.core.context import BaseContext
from airweave.core.redis_client import redis_client
from airweave.schemas import Sync, SyncJob

STACK_DUMP_INTERVAL_S = 600
STACK_DUMP_CHUNK_SIZE = 12_000
STALL_THRESHOLD_S = 300
REDIS_CHECK_INTERVAL_S = 30
REDIS_SNAPSHOT_KEY_PREFIX = "sync_progress_snapshot"


def emit_stack_dump(
    reason: str,
    elapsed_s: int,
    sync_id: UUID,
    sync_job_id: UUID,
    logger: Any,
) -> None:
    """Capture thread + async-task stack traces and log them in chunks."""
    traces: list[str] = []
    for thread_id, frame in sys._current_frames().items():
        traces.append(f"\n=== Thread {thread_id} ===")
        traces.append("".join(traceback.format_stack(frame)))
    all_tasks = asyncio.all_tasks()
    traces.append(f"\n=== Async Tasks ({len(all_tasks)} total) ===")
    for task in all_tasks:
        if not task.done():
            task_name = task.get_name()
            coro = task.get_coro()
            if hasattr(coro, "cr_frame") and coro.cr_frame:
                frame = coro.cr_frame
                traces.append(f"\nTask: {task_name}")
                loc = f"{frame.f_code.co_filename}:{frame.f_lineno}"
                traces.append(f"  at {loc} in {frame.f_code.co_name}")

    thread_parts: list[str] = []
    async_parts: list[str] = []
    in_async = False
    for trace in traces:
        if "=== Async Tasks" in trace:
            in_async = True
        (async_parts if in_async else thread_parts).append(trace)

    base_extra = {
        "elapsed_seconds": elapsed_s,
        "sync_id": str(sync_id),
        "sync_job_id": str(sync_job_id),
    }

    logger.debug(
        f"[STACK_TRACE_DUMP] sync={sync_id} "
        f"sync_job={sync_job_id} elapsed={elapsed_s}s "
        f"reason={reason} part=threads",
        extra={**base_extra, "stack_traces": "".join(thread_parts)},
    )

    async_str = "".join(async_parts)
    chunk_idx = 0
    for i in range(0, max(len(async_str), 1), STACK_DUMP_CHUNK_SIZE):
        chunk_idx += 1
        logger.debug(
            f"[STACK_TRACE_DUMP] sync={sync_id} "
            f"sync_job={sync_job_id} elapsed={elapsed_s}s "
            f"reason={reason} part=async_tasks chunk={chunk_idx}",
            extra={
                **base_extra,
                "stack_traces": async_str[i : i + STACK_DUMP_CHUNK_SIZE],
                "chunk": chunk_idx,
            },
        )


class HeartbeatMonitor:
    """Polls a sync task and sends Temporal heartbeats with progress data.

    Monitors Redis for entity-processing snapshots. When no progress is
    detected for ``STALL_THRESHOLD_S`` seconds, emits a stack dump.
    Periodic stack dumps fire every ``STACK_DUMP_INTERVAL_S`` seconds
    regardless of stall state.
    """

    def __init__(self, sync: Sync, sync_job: SyncJob, ctx: BaseContext) -> None:  # noqa: D107
        self._sync = sync
        self._sync_job = sync_job
        self._ctx = ctx

        self._start: float = 0.0
        self._last_stack_dump: float = 0.0
        self._last_redis_check: float = 0.0
        self._last_known_timestamp: str | None = None
        self._last_snapshot: dict[str, Any] = {}
        self._stall_start: float | None = None
        self._stall_dump_emitted: bool = False

    async def run(self, sync_task: asyncio.Task[Any]) -> None:
        """Block until *sync_task* completes, heartbeating every second.

        Raises whatever *sync_task* raises (via ``await sync_task``).
        """
        self._start = time.time()
        self._last_stack_dump = self._start
        self._last_redis_check = self._start

        while True:
            done, _ = await asyncio.wait({sync_task}, timeout=1)
            if sync_task in done:
                await sync_task
                return

            now = time.time()
            elapsed = int(now - self._start)

            await self._check_progress(now, elapsed)
            self._maybe_periodic_dump(now, elapsed)

            heartbeat_data = self._build_heartbeat(elapsed, now)
            self._ctx.logger.debug("HEARTBEAT: Sync in progress")
            activity.heartbeat(heartbeat_data)

    async def _check_progress(self, now: float, elapsed: int) -> None:
        """Check Redis for progress and detect stalls. Mutates self."""
        if (now - self._last_redis_check) < REDIS_CHECK_INTERVAL_S:
            return

        self._last_redis_check = now
        snapshot_result = await check_redis_snapshot(self._sync_job.id)
        if snapshot_result is None:
            self._detect_stall(now, elapsed)
            return

        self._last_snapshot = snapshot_result
        current_ts = self._last_snapshot.get("last_update_timestamp")
        if current_ts != self._last_known_timestamp:
            self._last_known_timestamp = current_ts
            self._stall_start = None
            self._stall_dump_emitted = False
        elif self._stall_start is None:
            self._stall_start = now

        self._detect_stall(now, elapsed)

    def _detect_stall(self, now: float, elapsed: int) -> None:
        """Emit a stack dump if stalled past the threshold."""
        if (
            self._stall_start is not None
            and not self._stall_dump_emitted
            and (now - self._stall_start) >= STALL_THRESHOLD_S
        ):
            stall_seconds = int(now - self._stall_start)
            self._ctx.logger.warning(
                f"[STALL_DETECTED] sync={self._sync.id} "
                f"sync_job={self._sync_job.id} "
                f"no entity progress for {stall_seconds}s"
            )
            emit_stack_dump("stall", elapsed, self._sync.id, self._sync_job.id, self._ctx.logger)
            self._stall_dump_emitted = True

    def _maybe_periodic_dump(self, now: float, elapsed: int) -> None:
        """Emit a periodic stack dump if enough time has passed."""
        past_interval = elapsed > STACK_DUMP_INTERVAL_S
        if past_interval and (now - self._last_stack_dump) >= STACK_DUMP_INTERVAL_S:
            emit_stack_dump("periodic", elapsed, self._sync.id, self._sync_job.id, self._ctx.logger)
            self._last_stack_dump = now

    def _build_heartbeat(self, elapsed: int, now: float) -> dict[str, Any]:
        """Assemble heartbeat payload from current state."""
        data: dict[str, Any] = {
            "phase": "syncing",
            "elapsed_s": elapsed,
        }
        if self._last_known_timestamp:
            data["last_progress_at"] = self._last_known_timestamp
        if self._last_snapshot:
            data["inserted"] = self._last_snapshot.get("inserted", 0)
            data["updated"] = self._last_snapshot.get("updated", 0)
            data["deleted"] = self._last_snapshot.get("deleted", 0)
            data["kept"] = self._last_snapshot.get("kept", 0)
        if self._stall_start is not None:
            data["stall_s"] = int(now - self._stall_start)
        return data


async def check_redis_snapshot(sync_job_id: UUID) -> dict[str, Any] | None:
    """Fetch the progress snapshot from Redis. Returns None on any failure."""
    try:
        snapshot_key = f"{REDIS_SNAPSHOT_KEY_PREFIX}:{sync_job_id}"
        snapshot_raw = await redis_client.client.get(snapshot_key)
        if snapshot_raw:
            return json.loads(snapshot_raw)
    except Exception:
        pass
    return None
