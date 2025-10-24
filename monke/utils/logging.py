"""Logging utilities for monke."""

import logging
import os
from typing import Optional

from rich.console import Console
from rich.logging import RichHandler


def get_logger(name: str, level: Optional[str] = None) -> logging.Logger:
    """Get a logger with rich formatting.

    Args:
        name: Logger name
        level: Log level (default: INFO)

    Returns:
        Configured logger
    """
    logger = logging.getLogger(name)

    # Avoid adding handlers multiple times
    if logger.handlers:
        return logger

    # Set log level
    log_level = getattr(logging, level.upper()) if level else logging.INFO
    logger.setLevel(log_level)

    # Check if we're in CI environment
    is_ci = os.getenv("CI") == "true" or os.getenv("GITHUB_ACTIONS") == "true"

    if is_ci:
        # In CI, use a wider console width and disable terminal forcing to prevent truncation
        console = Console(width=120, force_terminal=False)
        rich_handler = RichHandler(
            console=console,
            show_time=True,
            show_path=False,
            markup=True,
            rich_tracebacks=True,
            show_level=True,
        )
    else:
        # In local development, use full terminal width
        console = Console(width=None, force_terminal=True)
        rich_handler = RichHandler(
            console=console,
            show_time=True,
            show_path=False,
            markup=True,
            rich_tracebacks=True,
        )

    # Set formatter
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    rich_handler.setFormatter(formatter)

    # Add handler
    logger.addHandler(rich_handler)

    # Allow propagation so server-side collectors (e.g., per-run handler) can capture logs
    logger.propagate = True

    return logger
