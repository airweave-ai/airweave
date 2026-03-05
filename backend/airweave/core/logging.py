"""The logging configuration module."""

import json
import logging
import sys
from datetime import datetime
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from airweave.core.context import BaseContext


class JSONFormatter(logging.Formatter):
    """Custom JSON formatter for structured logging.

    Formats log records as JSON with support for custom dimensions,
    making logs compatible with Azure Log Analytics, Prometheus, and Grafana.
    """

    def __init__(self):
        """Initialize the formatter with a module path cache."""
        super().__init__()
        self._module_cache = {}

    def _get_module_path(self, record: logging.LogRecord) -> str:
        """Extract the full module path from the log record.

        Args:
        ----
            record (logging.LogRecord): The log record

        Returns:
        -------
            str: Full module path (e.g., 'airweave.integrations.qdrant')

        """
        # Check cache first
        pathname = record.pathname
        if pathname in self._module_cache:
            return self._module_cache[pathname]

        try:
            # Simple string manipulation - find "airweave" in the path
            if "airweave" in pathname:
                # Split by path separator and find where airweave starts
                parts = pathname.replace("\\", "/").split("/")

                # Find the last occurrence of 'airweave' (in case it appears multiple times)
                airweave_indices = [i for i, part in enumerate(parts) if part == "airweave"]
                if airweave_indices:
                    # Take the last occurrence
                    start_idx = airweave_indices[-1]
                    module_parts = parts[start_idx:]

                    # Remove .py extension from last part
                    if module_parts and module_parts[-1].endswith(".py"):
                        module_parts[-1] = module_parts[-1][:-3]

                    module_path = ".".join(module_parts)
                    self._module_cache[pathname] = module_path
                    return module_path

            # Fallback to simple module name
            module_path = record.module
            self._module_cache[pathname] = module_path
            return module_path

        except Exception:
            # If anything goes wrong, use the simple module name
            return record.module

    def format(self, record: logging.LogRecord) -> str:
        """Format the log record as JSON.

        Args:
        ----
            record (logging.LogRecord): The log record to format

        Returns:
        -------
            str: JSON-formatted log message

        """
        # Base log structure
        log_entry = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": self._get_module_path(record),
            "function": record.funcName,
            "line": record.lineno,
        }

        # Add custom dimensions if they exist
        if hasattr(record, "custom_dimensions") and record.custom_dimensions:
            log_entry["custom_dimensions"] = record.custom_dimensions

        # Add any other extra fields (excluding custom_dimensions to avoid duplication)
        if hasattr(record, "__dict__"):
            for key, value in record.__dict__.items():
                if key not in {
                    "name",
                    "msg",
                    "args",
                    "levelname",
                    "levelno",
                    "pathname",
                    "filename",
                    "module",
                    "lineno",
                    "funcName",
                    "created",
                    "msecs",
                    "relativeCreated",
                    "thread",
                    "threadName",
                    "processName",
                    "process",
                    "getMessage",
                    "custom_dimensions",
                    "exc_info",
                    "exc_text",
                    "stack_info",
                }:
                    # Only add serializable values
                    try:
                        json.dumps(value)
                        log_entry[key] = value
                    except (TypeError, ValueError):
                        log_entry[key] = str(value)

        # Add exception info if present
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_entry, default=str)


class ContextualLogger(logging.LoggerAdapter):
    """A LoggerAdapter that supports both custom dimensions and prefixes."""

    def __init__(
        self,
        logger: logging.Logger,
        prefix: str = "",
        dimensions: Optional[dict] = None,
    ) -> None:
        """Initialize the contextual logger.

        Args:
        ----
            logger (logging.Logger): Base logger instance
            dimensions (Optional[dict]): Custom dimensions for structured logging
            prefix (str): Optional prefix for log messages

        """
        super().__init__(logger, {})
        self.prefix = prefix
        self.dimensions = dimensions or {}

    def from_ctx(self, ctx: "BaseContext") -> "ContextualLogger":
        """Create a new logger with additional context from a BaseContext object."""
        new_dimensions = self.dimensions.copy()
        new_dimensions["organization_id"] = str(ctx.organization.id)
        new_dimensions["auth_method"] = ctx.auth_method

        if ctx.user_id:
            new_dimensions["user_id"] = str(ctx.user_id)
        if ctx.tracking_email:
            new_dimensions["user_email"] = ctx.tracking_email

        return ContextualLogger(self.logger, self.prefix, new_dimensions)

    def process(self, msg: str, kwargs: dict) -> tuple[str, dict]:
        """Process the log message and keywords.

        Args:
        ----
            msg (str): The log message
            kwargs (dict): The logging keywords

        Returns:
        -------
            Tuple[str, dict]: Processed message and keywords

        """
        if self.prefix:
            msg = f"{self.prefix}{msg}"

        # Initialize extra if it doesn't exist
        if "extra" not in kwargs:
            kwargs["extra"] = {}

        # Add custom dimensions directly to the record
        if self.dimensions:
            kwargs["extra"]["custom_dimensions"] = {
                **kwargs["extra"].get("custom_dimensions", {}),
                **self.dimensions,
            }

        return msg, kwargs

    def with_prefix(self, prefix: str) -> "ContextualLogger":
        """Create a new logger with an additional prefix while maintaining dimensions.

        Args:
        ----
            prefix (str): The prefix to add

        Returns:
        -------
            ContextualLogger: New logger instance with updated prefix

        """
        return ContextualLogger(self.logger, prefix, self.dimensions)

    def with_context(self, **dimensions: str | int | float | bool) -> "ContextualLogger":
        """Create a new logger with additional context dimensions.

        Args:
        ----
            dimensions: Keyword arguments to add to dimensions

        Returns:
        -------
            ContextualLogger: New logger instance with updated dimensions

        """
        new_dimensions = {**self.dimensions, **dimensions}
        return ContextualLogger(self.logger, self.prefix, new_dimensions)


class LoggerConfigurator:
    """Configures loggers with support for dimensions and prefixes.

    The base context is injected into endpoints and worker runs, at the context dependency injection
    level, such as api context or arq context.

    These dimensions contain information about the context of the log message, such as
    context_base (api, arq), user_id, request_id, polling_job_id, trigger_run_id, etc.

    This can then be augmented with additional dimensions, such as type of operation (flow
    generation, flow execution, etc), or error type (validation, parsing, etc).

    Configuration:
    -------------
    Uses settings from airweave.core.config:
    - Automatically uses text format when LOCAL_DEVELOPMENT=True, JSON format otherwise
    - LOG_LEVEL: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)

    Examples:
    --------
    Create base logger with component context:
    ```python
    logger = LoggerConfigurator.configure_logger(
        __name__, dimensions={"component": "flow_generator"}
    )
    # Log a message with the base context
    logger.info("Starting flow generation")
    ```

    Add operation context:
    ```python
    logger.with_context(operation="generate_flow").info("Starting flow generation")
    ```

    Chain multiple contexts:
    ```python
    detail_logger = logger.with_context(operation="validate").with_context(
        user_id="123", request_id="456"
    )
    detail_logger.info("Starting validation")
    ```

    Mix contexts and prefix:
    ```python
    error_logger = logger.with_context(error_type="validation", severity="high").with_prefix(
        "ERROR: "
    )
    ```

    """

    @staticmethod
    def configure_logger(
        name: str,
        prefix: str = "",
        dimensions: Optional[dict] = None,
    ) -> ContextualLogger:
        """Configure and return a logger with the given name and initial context.

        Args:
        ----
            name (str): Logger name (typically __name__)
            dimensions (Optional[dict]): Initial custom dimensions
            prefix (str): Initial prefix for log messages

        Returns:
        -------
            ContextualLogger: Configured logger with context support

        """
        logger = logging.getLogger(name)

        from airweave.core.config import settings

        log_level = settings.LOG_LEVEL.upper()
        logger.setLevel(getattr(logging, log_level, logging.INFO))

        logger.propagate = False

        if hasattr(logger, "_airweave_configured"):
            return ContextualLogger(logger, prefix, dimensions)

        logger.handlers.clear()

        stream_handler = logging.StreamHandler(sys.stdout)

        # Use text format only for local development, JSON everywhere else
        if settings.LOCAL_DEVELOPMENT:
            formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        else:
            formatter = JSONFormatter()

        stream_handler.setFormatter(formatter)
        logger.addHandler(stream_handler)

        logger._airweave_configured = True

        return ContextualLogger(logger, prefix, dimensions)


# Default logger instance
logger = LoggerConfigurator.configure_logger(__name__)
