"""Development runner to hot-reload Temporal worker and optionally attach debugger.

Starts the worker with optional debugpy support. Set AIRWEAVE_WORKER_DEBUG=true to enable.
"""

import os
import shlex
import sys
from pathlib import Path

from watchfiles import run_process


def build_worker_command() -> list[str]:
    """Return the command list to start the worker, optionally under debugpy."""
    enable_debug = os.getenv("AIRWEAVE_WORKER_DEBUG", "false").lower() == "true"

    if enable_debug:
        port = os.getenv("AIRWEAVE_DEBUGPY_WORKER_PORT", "5679")
        wait_for_client = os.getenv("AIRWEAVE_DEBUGPY_WAIT_FOR_CLIENT", "false").lower() == "true"

        cmd = [
            sys.executable,
            "-m",
            "debugpy",
            "--listen",
            f"127.0.0.1:{port}",
        ]

        if wait_for_client:
            cmd.append("--wait-for-client")

        cmd.extend(["-m", "airweave.platform.temporal.worker"])
    else:
        # Run directly without debugpy
        cmd = [sys.executable, "-m", "airweave.platform.temporal.worker"]

    return cmd


if __name__ == "__main__":
    backend_dir = Path(__file__).resolve().parents[1]
    preferred_watch = backend_dir / "backend" / "airweave"
    if preferred_watch.exists():
        watch_paths = [str(preferred_watch)]
    else:
        fallback = backend_dir / "backend"
        print(
            f"[dev] Watch path not found: {preferred_watch}. Falling back to {fallback}.",
            flush=True,
        )
        watch_paths = [str(fallback)]
    cmd = build_worker_command()
    cmd_str = shlex.join(cmd)
    print("[dev] Starting Temporal worker:", cmd_str, flush=True)
    run_process(*watch_paths, target=cmd_str, target_type="command")
