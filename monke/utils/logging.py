"""Logging utilities for monke."""

import logging
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

    # Create rich handler
    console = Console()
    rich_handler = RichHandler(
        console=console, show_time=True, show_path=False, markup=True, rich_tracebacks=True
    )

    # Set formatter
    formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    rich_handler.setFormatter(formatter)

    # Add handler
    logger.addHandler(rich_handler)

    # Allow propagation so server-side collectors (e.g., per-run handler) can capture logs
    logger.propagate = True

    return logger
