#!/usr/bin/env python3
"""
CI runner for a single Monke config that:
- loads env vars from monke/env.test via python-dotenv,
- disables console logging,
- writes Rich-formatted logs to a file,
- runs exactly one config (perfect for matrix legs).

Usage:
  python ci_run_single.py --config monke/configs/gmail.yaml --log-file logs/gmail.rich.log
  # To also mirror logs to console (optional):
  # python ci_run_single.py --config ... --log-file ... --console
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
from pathlib import Path

from monke.utils.composio_polyfill import connect_composio_provider_polyfill

# --- Load environment BEFORE importing any monke modules ----------------------
# We want env vars available to any monke imports/initializers.
ENV_PATH = (Path(__file__).parent / "monke" / "env.test").resolve()
try:
    from dotenv import load_dotenv  # type: ignore

    if ENV_PATH.exists():
        # Do not override already-set env vars by default (safer in CI).
        load_dotenv(dotenv_path=ENV_PATH, override=False)
    else:
        print(f"[ci_run_single] Warning: env file not found at {ENV_PATH}", file=sys.stderr)
except ImportError:
    print(
        "[ci_run_single] Warning: python-dotenv not installed; skipping env loading.\n"
        "Install with: pip install python-dotenv",
        file=sys.stderr,
    )

# --- Configure logging BEFORE importing monke modules -------------------------
from rich.console import Console
from rich.logging import RichHandler

# Patch monke's get_logger so it doesn't add console handlers per logger
import importlib

monke_logging = importlib.import_module("monke.utils.logging")


# We'll attach handlers only to the root logger; all monke loggers will propagate.
def _patched_get_logger(name: str, level: str | None = None) -> logging.Logger:
    logger = logging.getLogger(name)
    if level:
        try:
            logger.setLevel(getattr(logging, level.upper()))
        except Exception:
            pass
    logger.propagate = True  # rely on root handlers only
    return logger


monke_logging.get_logger = _patched_get_logger  # type: ignore[attr-defined]

# Now safe to import Monke's test runner
from monke.test import run_test  # noqa: E402


def _configure_root_logging(
    log_file: Path, enable_console: bool = False, level: str = "INFO"
) -> None:
    """
    Replace any existing handlers with:
      - a Rich handler writing to `log_file` (always),
      - (optional) a Rich console handler if `enable_console` is True.
    """
    root = logging.getLogger()
    # Clear handlers to avoid double logging
    for h in list(root.handlers):
        root.removeHandler(h)

    root.setLevel(getattr(logging, level.upper(), logging.INFO))

    log_file.parent.mkdir(parents=True, exist_ok=True)
    f = log_file.open("w", encoding="utf-8")

    # Rich to file (uses a Console bound to the file)
    file_console = Console(file=f, force_terminal=True, color_system=None, width=140)
    file_handler = RichHandler(
        console=file_console,
        show_time=True,
        show_path=False,
        markup=True,
        rich_tracebacks=True,
    )
    file_handler.setLevel(root.level)
    root.addHandler(file_handler)

    # Optional mirrored console logs (default off)
    if enable_console:
        console_handler = RichHandler(
            show_time=True,
            show_path=False,
            markup=True,
            rich_tracebacks=True,
        )
        console_handler.setLevel(root.level)
        root.addHandler(console_handler)


async def _amain() -> int:
    _connect_response = await connect_composio_provider_polyfill(
        os.getenv("DM_AUTH_PROVIDER_API_KEY")
    )

    os.environ["DM_AUTH_PROVIDER_ID"] = _connect_response["readable_id"]

    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True, help="Path to monke config YAML")
    parser.add_argument("--log-file", required=True, help="Where to write Rich-formatted logs")
    parser.add_argument("--console", action="store_true", help="Also echo logs to console")
    parser.add_argument("--run-id", default=None, help="Optional custom run id")
    args = parser.parse_args()

    cfg = Path(args.config)
    if not cfg.is_absolute():
        # Resolve relative to this script
        cfg = (Path(__file__).parent / cfg).resolve()

    _configure_root_logging(Path(args.log_file), enable_console=args.console)

    # Helpful context for downstream code
    os.environ.setdefault("CI", "true")

    # Kick off the test
    ok = await run_test(str(cfg), run_id=args.run_id)
    return 0 if ok else 1


def main() -> None:
    try:
        raise SystemExit(asyncio.run(_amain()))
    except KeyboardInterrupt:
        print("Interrupted.", file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
