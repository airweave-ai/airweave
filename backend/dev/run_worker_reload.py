"""Development runner to hot-reload Temporal worker and attach debugger.

Starts the worker under debugpy on a fixed port so VS Code can attach reliably.
"""

import os
import shlex
import sys
from pathlib import Path

from watchfiles import run_process


def build_worker_command() -> list[str]:
    """Return the command list to start the worker under debugpy on a fixed port."""
    port = os.getenv("AIRWEAVE_DEBUGPY_WORKER_PORT", "5679")
    return [
        sys.executable,
        "-m",
        "debugpy",
        "--listen",
        f"127.0.0.1:{port}",
        "--wait-for-client",
        "-m",
        "airweave.platform.temporal.worker",
    ]


if __name__ == "__main__":
    backend_dir = Path(__file__).resolve().parents[1]
    preferred_watch = backend_dir / "airweave"
    if preferred_watch.exists():
        watch_paths = [str(preferred_watch)]
    else:
        print(
            f"[dev] Watch path not found: {preferred_watch}. Falling back to backend root.",
            flush=True,
        )
        watch_paths = [str(backend_dir)]
    cmd = build_worker_command()
    cmd_str = shlex.join(cmd)
    print("[dev] Starting Temporal worker:", cmd_str, flush=True)
    run_process(*watch_paths, target=cmd_str, target_type="command")
