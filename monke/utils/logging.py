"""Logging utilities for monke."""

import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.logging import RichHandler

# Global log directory for the current run
_log_dir: Optional[Path] = None


def setup_file_logging() -> Path:
    """Set up file logging for the current run.
    Creates a timestamped log directory and configures the root logger
    to write to a file in that directory.
    Returns:
        Path to the log directory
    """
    global _log_dir

    # Create log directory with timestamp
    log_base = Path(__file__).parent.parent / "logs"
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    _log_dir = log_base / timestamp
    _log_dir.mkdir(parents=True, exist_ok=True)

    # Write latest pointer
    (log_base / ".latest").write_text(timestamp)

    # Configure root logger with file handler
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)

    # Add file handler
    file_handler = logging.FileHandler(_log_dir / "monke.log")
    file_handler.setLevel(logging.DEBUG)
    file_formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    file_handler.setFormatter(file_formatter)
    root_logger.addHandler(file_handler)

    return _log_dir


def get_log_dir() -> Optional[Path]:
    """Get the current log directory."""
    return _log_dir


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

    # Create rich handler with full terminal width
    # Use explicit large width for CI environments (GitHub Actions defaults to 80 otherwise)
    console = Console(width=200, force_terminal=True)
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
