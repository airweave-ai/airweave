#!/usr/bin/env python3
# test_multiple.py
from __future__ import annotations

import argparse
import asyncio
import contextlib  # <-- keep at module level to avoid UnboundLocalError
import sys
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

# Make repo root importable (same as test.py behavior)
sys.path.insert(0, str(Path(__file__).parent.parent))

# Optional .env support
try:
    from dotenv import load_dotenv  # type: ignore
except Exception:
    load_dotenv = None  # .env is optional; we warn below

from rich.console import Console
from rich.progress import (
    Progress,
    SpinnerColumn,
    TextColumn,
    BarColumn,
    TaskProgressColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)
from rich.table import Table

# Import the single-run entrypoint and event bus
from test import run_test  # noqa: E402
from monke.core import events  # noqa: E402

from monke.utils.composio_polyfill import connect_composio_provider_polyfill

import os


@dataclass
class RunState:
    run_id: str
    config_path: Path
    name: str
    task_id: Optional[int] = None
    total_units: Optional[int] = None  # setup + steps + cleanup
    completed_units: int = 0
    started_at: float = field(default_factory=time.perf_counter)
    finished_at: Optional[float] = None
    success: Optional[bool] = None
    last_phase: str = "pending"


def _resolve_config_paths(configs: List[str]) -> List[Path]:
    """
    Resolve config paths similarly to test.py:
    - If relative, treat as relative to this file's directory.
    - Validate existence.
    """
    base_dir = Path(__file__).parent
    resolved: List[Path] = []
    for c in configs:
        p = Path(c)
        if not p.is_absolute():
            p = (base_dir / p).resolve()
        if not p.exists():
            raise FileNotFoundError(f"Config file not found: {p}")
        resolved.append(p)
    return resolved


async def _event_listener(
    q: asyncio.Queue,
    progress: Progress,
    runs: Dict[str, RunState],
) -> None:
    """
    Consume Monke structured events and update Rich progress bars in real-time.
    """
    while True:
        ev = await q.get()
        try:
            ev_type = ev.get("type")
            rid = ev.get("run_id")
            if not rid or rid not in runs:
                continue
            rs = runs[rid]

            # Ensure task exists
            if rs.task_id is None:
                rs.task_id = progress.add_task(
                    f"[bold]{rs.name}[/] • starting…",
                    total=None,  # we will set real total on flow_started
                    visible=True,
                )

            # Update based on event type
            if ev_type == "flow_started":
                steps = ev.get("steps", []) or []
                total = len(steps) + 2  # setup + steps + cleanup
                rs.total_units = total
                rs.completed_units = 0
                progress.update(
                    rs.task_id,
                    total=total,
                    completed=0,
                    description=f"[bold]{rs.name}[/] • setup",
                )

            elif ev_type == "setup_completed":
                rs.completed_units += 1
                progress.update(rs.task_id, completed=rs.completed_units)

            elif ev_type == "step_started":
                step = ev.get("step") or ""
                progress.update(rs.task_id, description=f"[bold]{rs.name}[/] • {step}")

            elif ev_type == "step_completed":
                rs.completed_units += 1
                progress.update(rs.task_id, completed=rs.completed_units)

            elif ev_type == "step_failed":
                step = ev.get("step") or ""
                rs.completed_units += 1
                progress.update(
                    rs.task_id,
                    completed=rs.completed_units,
                    description=f"[bold red]{rs.name}[/] • FAILED: {step}",
                )

            elif ev_type == "cleanup_started":
                progress.update(rs.task_id, description=f"[bold]{rs.name}[/] • cleanup")

            elif ev_type == "cleanup_completed":
                # mark as fully complete if we know the total
                if rs.total_units is not None:
                    rs.completed_units = rs.total_units
                else:
                    rs.completed_units += 1
                progress.update(rs.task_id, completed=rs.completed_units)

            elif ev_type == "flow_completed":
                # We'll finalize style based on the actual success flag when the run coroutine returns.
                if rs.total_units is not None:
                    progress.update(
                        rs.task_id,
                        completed=rs.total_units,
                        description=f"[bold]{rs.name}[/] • done",
                    )
                else:
                    progress.update(
                        rs.task_id,
                        description=f"[bold]{rs.name}[/] • done",
                    )

        finally:
            q.task_done()


async def _run_one(
    rs: RunState,
) -> RunState:
    """
    Wrap single-run execution to measure duration and success,
    delegating to test.run_test(config, run_id).
    """
    success = await run_test(str(rs.config_path), run_id=rs.run_id)
    rs.success = bool(success)
    rs.finished_at = time.perf_counter()
    return rs


async def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run multiple Monke tests concurrently with a live Rich progress UI."
    )
    parser.add_argument(
        "--configs",
        nargs="+",
        required=True,
        help="List of config YAMLs (e.g., configs/notion.yaml configs/github.yaml)",
    )
    parser.add_argument(
        "--run-id-prefix",
        default="batch-",
        help="Prefix for generated run IDs (default: batch-)",
    )
    parser.add_argument(
        "--env",
        default="env.test",
        help="Path to environment file to load once for all runs (default: env.test)",
    )
    parser.add_argument(
        "--max-concurrency",
        type=int,
        default=0,
        help="Optional cap on concurrent runs (0 = no cap, run all at once).",
    )
    args = parser.parse_args()

    # Load environment variables ONCE (shared across runs/process).
    if load_dotenv:
        env_path = (Path(__file__).parent / args.env).resolve()
        if env_path.exists():
            load_dotenv(env_path, override=True)
            print(f"✅ Loaded environment from {env_path}")
        else:
            print(f"⚠️  No environment file at {env_path}, using system environment")
    else:
        print("⚠️  Using system environment variables (install python-dotenv for .env support)")

    # Resolve and validate config paths
    config_paths = _resolve_config_paths(args.configs)
    if not config_paths:
        print("❌ No valid configs provided")
        sys.exit(1)

    print(os.getenv("DM_AUTH_PROVIDER_API_KEY"))

    _connect_response = await connect_composio_provider_polyfill(
        os.getenv("DM_AUTH_PROVIDER_API_KEY")
    )

    os.environ["DM_AUTH_PROVIDER_ID"] = _connect_response["readable_id"]

    # Build per-run state
    runs: Dict[str, RunState] = {}
    for p in config_paths:
        stem = p.stem
        short = uuid.uuid4().hex[:6]
        run_id = f"{args.run_id_prefix}{stem}-{short}"
        runs[run_id] = RunState(
            run_id=run_id,
            config_path=p,
            name=stem,
        )

    console = Console()

    # Prepare Rich progress layout
    progress = Progress(
        SpinnerColumn(),
        TextColumn("{task.description}"),
        BarColumn(),
        TaskProgressColumn(),  # e.g., 3/7
        TimeElapsedColumn(),
        TimeRemainingColumn(),
        expand=True,
        console=console,
    )

    # Subscribe to the in-process Monke event bus
    q = events.subscribe()

    # Partition runs if a cap is set
    run_list = list(runs.values())
    if args.max_concurrency and args.max_concurrency > 0:
        chunks = [
            run_list[i : i + args.max_concurrency]
            for i in range(0, len(run_list), args.max_concurrency)
        ]
    else:
        chunks = [run_list]

    all_results: List[RunState] = []

    try:
        with progress:
            # Create placeholder tasks so the UI shows immediately
            for rs in runs.values():
                rs.task_id = progress.add_task(
                    f"[bold]{rs.name}[/] • starting…",
                    total=None,
                    visible=True,
                )

            # Start event listener
            listener = asyncio.create_task(_event_listener(q, progress, runs))

            # Execute runs (maybe in waves, if capped)
            for cohort in chunks:
                tasks = [asyncio.create_task(_run_one(rs)) for rs in cohort]
                finished = await asyncio.gather(*tasks, return_exceptions=False)
                all_results.extend(finished)

                # Reflect final state in the progress bars
                for rs in finished:
                    # Ensure we have a visible final description & completion status
                    desc_ok = f"[bold green]{rs.name}[/] • ✅ success"
                    desc_fail = f"[bold red]{rs.name}[/] • ❌ failed"
                    if rs.task_id is not None:
                        if rs.success:
                            progress.update(
                                rs.task_id,
                                description=desc_ok,
                                completed=(
                                    runs[rs.run_id].total_units or runs[rs.run_id].completed_units
                                ),
                            )
                        else:
                            # Mark complete, but red
                            total = runs[rs.run_id].total_units or runs[rs.run_id].completed_units
                            progress.update(
                                rs.task_id,
                                description=desc_fail,
                                completed=total,
                            )

            # Drain any remaining events quickly
            await asyncio.sleep(0.05)
            try:
                while True:
                    q.get_nowait()
                    q.task_done()
            except asyncio.QueueEmpty:
                pass

            # Stop listener
            listener.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await listener

    finally:
        events.unsubscribe(q)

    # Print a compact summary table
    table = Table(title="Concurrent Test Summary", show_lines=False)
    table.add_column("Run ID", overflow="fold")
    table.add_column("Config")
    table.add_column("Status")
    table.add_column("Duration (s)", justify="right")

    for rs in all_results:
        dur = (rs.finished_at - rs.started_at) if (rs.finished_at and rs.started_at) else 0.0
        status = "[green]success[/]" if rs.success else "[red]failed[/]"
        table.add_row(rs.run_id, rs.config_path.name, status, f"{dur:.2f}")

    console.print()
    console.print(table)

    # Exit code: 0 only if all succeeded
    if not all(r.success for r in all_results):
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
