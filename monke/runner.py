#!/usr/bin/env python3
"""Unified Monke Test Runner - One runner for all scenarios."""

import argparse
import asyncio
import os
import sys
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Any

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Optional .env support
try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

from monke.core import events
from monke.core.runner import TestRunner
from monke.utils.logging import get_logger, setup_file_logging

# Check if we're in CI environment
IS_CI = os.getenv("CI") == "true" or os.getenv("GITHUB_ACTIONS") == "true"
IS_INTERACTIVE = sys.stdout.isatty() and not IS_CI

# Only import Rich if we're in interactive mode
if IS_INTERACTIVE:
    try:
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

        HAS_RICH = True
    except ImportError:
        HAS_RICH = False
else:
    HAS_RICH = False


@dataclass
class RunState:
    """State for a single test run."""

    run_id: str
    config_path: Path
    name: str
    task_id: Optional[int] = None
    total_units: Optional[int] = None
    completed_units: int = 0
    started_at: float = field(default_factory=time.perf_counter)
    finished_at: Optional[float] = None
    success: Optional[bool] = None
    last_phase: str = "pending"
    errors: List[str] = field(default_factory=list)


async def run_single_test(config_path: str, run_id: str) -> bool:
    """Run a single test configuration."""
    logger = get_logger("monke_runner")
    logger.info(f"🚀 Running test: {config_path}")

    try:
        runner = TestRunner(config_path, run_id=run_id)
        results = await runner.run_tests()

        success = all(r.success for r in results)

        if success:
            logger.info(f"✅ Test passed: {Path(config_path).stem}")
        else:
            logger.error(f"❌ Test failed: {Path(config_path).stem}")
            for result in results:
                if not result.success:
                    for error in result.errors:
                        logger.error(f"  • {error}")

        return success
    except Exception as e:
        logger.error(f"❌ Test error: {e}")
        return False


async def event_listener(q: asyncio.Queue, progress: Any, runs: Dict[str, RunState]) -> None:
    """Listen to events and update progress bars (Rich UI only)."""
    while True:
        ev = await q.get()
        try:
            ev_type = ev.get("type")
            rid = ev.get("run_id")
            if not rid or rid not in runs:
                continue

            rs = runs[rid]

            # Update progress based on event type
            if rs.task_id is not None and progress:
                if ev_type == "flow_started":
                    total = ev.get("total_steps", 10)
                    rs.total_units = total
                    progress.update(
                        rs.task_id,
                        total=total,
                        description=f"[bold]{rs.name}[/] • starting...",
                    )
                elif ev_type == "step_started":
                    step_name = ev.get("step_name", "step")
                    progress.update(
                        rs.task_id,
                        description=f"[bold]{rs.name}[/] • {step_name}",
                        advance=0,
                    )
                elif ev_type == "step_completed":
                    rs.completed_units += 1
                    progress.update(rs.task_id, advance=1)
                elif ev_type == "step_failed":
                    rs.completed_units += 1
                    error = ev.get("error", "Unknown error")
                    rs.errors.append(error)
                    progress.update(
                        rs.task_id,
                        advance=1,
                        description=f"[bold red]{rs.name}[/] • failed",
                    )
                elif ev_type in ("flow_completed", "flow_failed"):
                    if rs.total_units:
                        progress.update(rs.task_id, completed=rs.total_units)
        finally:
            q.task_done()


async def run_parallel_with_ui(runs: Dict[str, RunState], max_concurrency: int) -> List[RunState]:
    """Run tests in parallel with Rich progress UI."""
    # Use explicit large width for CI environments (GitHub Actions defaults to 80 otherwise)
    console = Console(width=200, force_terminal=True)
    progress = Progress(
        SpinnerColumn(),
        TextColumn("{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        TimeElapsedColumn(),
        TimeRemainingColumn(),
        expand=True,
        console=console,
    )

    # Subscribe to events
    q = events.subscribe()

    # Partition runs if concurrency is limited
    run_list = list(runs.values())
    if max_concurrency > 0:
        chunks = [
            run_list[i : i + max_concurrency] for i in range(0, len(run_list), max_concurrency)
        ]
    else:
        chunks = [run_list]

    all_results = []

    try:
        with progress:
            # Create progress tasks
            for rs in runs.values():
                rs.task_id = progress.add_task(
                    f"[bold]{rs.name}[/] • pending",
                    total=None,
                    visible=True,
                )

            # Start event listener
            listener = asyncio.create_task(event_listener(q, progress, runs))

            # Run tests in waves
            for cohort in chunks:
                tasks = []
                for rs in cohort:
                    task = asyncio.create_task(run_single_test(str(rs.config_path), rs.run_id))
                    tasks.append((rs, task))

                # Wait for completion
                for rs, task in tasks:
                    rs.success = await task
                    rs.finished_at = time.perf_counter()
                    all_results.append(rs)

                    # Update progress bar
                    if rs.task_id is not None:
                        status = "✅ success" if rs.success else "❌ failed"
                        color = "green" if rs.success else "red"
                        progress.update(
                            rs.task_id,
                            description=f"[bold {color}]{rs.name}[/] • {status}",
                            completed=rs.total_units or rs.completed_units,
                        )

            # Stop listener
            listener.cancel()
            await asyncio.sleep(0.1)
    finally:
        events.unsubscribe(q)

    # Print summary table
    table = Table(title="Test Results", show_lines=False)
    table.add_column("Connector")
    table.add_column("Status")
    table.add_column("Duration", justify="right")

    for rs in all_results:
        duration = rs.finished_at - rs.started_at if rs.finished_at else 0
        status = "[green]PASSED[/]" if rs.success else "[red]FAILED[/]"
        table.add_row(rs.name, status, f"{duration:.2f}s")

    console.print()
    console.print(table)

    return all_results


async def run_parallel_simple(runs: Dict[str, RunState], max_concurrency: int) -> List[RunState]:
    """Run tests in parallel with simple console output (for CI)."""
    logger = get_logger("monke_runner")

    run_list = list(runs.values())
    if max_concurrency > 0:
        chunks = [
            run_list[i : i + max_concurrency] for i in range(0, len(run_list), max_concurrency)
        ]
    else:
        chunks = [run_list]

    all_results = []

    for i, cohort in enumerate(chunks, 1):
        if len(chunks) > 1:
            logger.info(f"Running batch {i}/{len(chunks)} ({len(cohort)} tests)")

        tasks = []
        for rs in cohort:
            logger.info(f"▶ Starting: {rs.name}")
            task = asyncio.create_task(run_single_test(str(rs.config_path), rs.run_id))
            tasks.append((rs, task))

        # Wait for completion
        for rs, task in tasks:
            rs.success = await task
            rs.finished_at = time.perf_counter()
            all_results.append(rs)

    # Print summary
    logger.info("\n" + "=" * 50)
    logger.info("Test Summary:")
    logger.info("=" * 50)

    passed = sum(1 for r in all_results if r.success)
    failed = sum(1 for r in all_results if not r.success)

    for rs in all_results:
        duration = rs.finished_at - rs.started_at if rs.finished_at else 0
        status = "✅ PASSED" if rs.success else "❌ FAILED"
        logger.info(f"{rs.name}: {status} ({duration:.2f}s)")

    logger.info(f"\nTotal: {passed} passed, {failed} failed")

    return all_results


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Unified Monke Test Runner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s github                    # Run single test
  %(prog)s github asana notion       # Run multiple tests in parallel
  %(prog)s --all                     # Run all tests
  %(prog)s --changed                 # Run tests for changed connectors
        """,
    )

    parser.add_argument(
        "connectors",
        nargs="*",
        help="Connector names to test (e.g., github asana notion)",
    )
    parser.add_argument("--all", "-a", action="store_true", help="Run all available tests")
    parser.add_argument(
        "--changed",
        "-c",
        action="store_true",
        help="Run tests for changed connectors (git diff vs main)",
    )
    parser.add_argument(
        "--max-concurrency",
        type=int,
        default=int(os.getenv("MONKE_MAX_PARALLEL", "5")),
        help="Maximum parallel tests (default: 5)",
    )
    parser.add_argument("--env", default=".env", help="Environment file (default: .env)")
    parser.add_argument(
        "--run-id-prefix", default="test-", help="Prefix for run IDs (default: test-)"
    )
    parser.add_argument("--no-ui", action="store_true", help="Disable Rich UI even if available")

    args = parser.parse_args()

     # Set up file logging
    log_dir = setup_file_logging()
    print(f"📝 Logs will be written to: {log_dir}/monke.log")

    # Load environment variables (if not in CI)
    if load_dotenv and not IS_CI:
        env_path = Path(__file__).parent / args.env
        if env_path.exists():
            load_dotenv(env_path, override=True)
            print(f"✅ Loaded environment from {env_path}")

    # Determine which configs to run
    configs = []

    if args.all:
        # Run all available configs
        config_dir = Path(__file__).parent / "configs"
        configs = sorted(config_dir.glob("*.yaml"))
    elif args.changed:
        # Detect changed connectors
        # This would need git diff logic - simplified for now
        print("Change detection not implemented in unified runner yet")
        sys.exit(1)
    elif args.connectors:
        # Run specific connectors
        config_dir = Path(__file__).parent / "configs"
        for name in args.connectors:
            config_path = config_dir / f"{name}.yaml"
            if config_path.exists():
                configs.append(config_path)
            else:
                print(f"❌ Config not found: {name}")
                sys.exit(1)
    else:
        print("❌ No tests specified. Use connector names, --all, or --changed")
        sys.exit(1)

    if not configs:
        print("❌ No configs to run")
        sys.exit(1)

    # Handle Composio auth if API key is provided
    if os.getenv("MONKE_COMPOSIO_API_KEY"):
        from monke.utils.composio_polyfill import connect_composio_provider_polyfill

        response = await connect_composio_provider_polyfill(os.getenv("MONKE_COMPOSIO_API_KEY"))
        os.environ["MONKE_COMPOSIO_PROVIDER_ID"] = response["readable_id"]

    # Build run states
    runs = {}
    for config_path in configs:
        stem = config_path.stem
        short = uuid.uuid4().hex[:6]
        run_id = f"{args.run_id_prefix}{stem}-{short}"
        runs[run_id] = RunState(
            run_id=run_id,
            config_path=config_path,
            name=stem,
        )

    # Run tests
    print(f"\n🐒 Running {len(runs)} test(s)")

    if len(runs) == 1:
        # Single test - just run it directly
        rs = list(runs.values())[0]
        success = await run_single_test(str(rs.config_path), rs.run_id)
        sys.exit(0 if success else 1)
    else:
        # Multiple tests - run in parallel
        if HAS_RICH and IS_INTERACTIVE and not args.no_ui:
            results = await run_parallel_with_ui(runs, args.max_concurrency)
        else:
            results = await run_parallel_simple(runs, args.max_concurrency)

        # Exit with appropriate code
        all_passed = all(r.success for r in results)
        sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    asyncio.run(main())
