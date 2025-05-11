"""The logging configuration module."""

import logging
import sys
from typing import Optional


class _ContextualLogger(logging.LoggerAdapter):
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

        # Initialize custom_dimensions if it doesn't exist
        if "custom_dimensions" not in kwargs["extra"]:
            kwargs["extra"]["custom_dimensions"] = {}

        # Merge dimensions
        if self.dimensions:
            kwargs["extra"]["custom_dimensions"].update(self.dimensions)

        return msg, kwargs

    def with_prefix(self, prefix: str) -> "_ContextualLogger":
        """Create a new logger with an additional prefix while maintaining dimensions.

        Args:
        ----
            prefix (str): The prefix to add

        Returns:
        -------
            _ContextualLogger: New logger instance with updated prefix

        """
        return _ContextualLogger(self.logger, prefix, self.dimensions)

    def with_context(self, **dimensions: str | int | float | bool) -> "_ContextualLogger":
        """Create a new logger with additional context dimensions.

        Args:
        ----
            dimensions: Keyword arguments to add to dimensions

        Returns:
        -------
            _ContextualLogger: New logger instance with updated dimensions

        """
        new_dimensions = {**self.dimensions, **dimensions}
        return _ContextualLogger(self.logger, self.prefix, new_dimensions)


class LoggerConfigurator:
    """Configures loggers with support for dimensions and prefixes.

    The base context is injected into endpoints and worker runs, at the context dependency injection
    level, such as api context or arq context.

    These dimensions contain information about the context of the log message, such as
    context_base (api, arq), user_id, request_id, polling_job_id, trigger_run_id, etc.

    This can then be augmented with additional dimensions, such as type of operation (flow
    generation, flow execution, etc), or error type (validation, parsing, etc).

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
    ) -> _ContextualLogger:
        """Configure and return a logger with the given name and initial context.

        Args:
        ----
            name (str): Logger name (typically __name__)
            dimensions (Optional[dict]): Initial custom dimensions
            prefix (str): Initial prefix for log messages

        Returns:
        -------
            _ContextualLogger: Configured logger with context support

        """
        logger = logging.getLogger(name)
        logger.setLevel(logging.INFO)

        # Add more handlers here if needed (perhaps as config options for open source users)

        # Add StreamHandler if not already added
        if not any(isinstance(handler, logging.StreamHandler) for handler in logger.handlers):
            stream_handler = logging.StreamHandler(sys.stdout)  # Explicitly use stdout
            logger.addHandler(stream_handler)

        return _ContextualLogger(logger, prefix, dimensions)


# Default logger instance
logger = LoggerConfigurator.configure_logger(__name__)
