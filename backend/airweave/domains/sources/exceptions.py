"""Source domain exceptions."""

from airweave.core.exceptions import NotFoundException


class SourceNotFoundError(NotFoundException):
    """Raised when a source with the given short_name does not exist or is hidden."""

    def __init__(self, short_name: str):
        self.short_name = short_name
        super().__init__(f"Source not found: {short_name}")


class SourceCreationError(Exception):
    """Raised when source_class.create() fails (bad credential format, missing fields, etc.)."""

    def __init__(self, short_name: str, reason: str):
        self.short_name = short_name
        self.reason = reason
        super().__init__(f"Failed to create source '{short_name}': {reason}")


class SourceValidationError(Exception):
    """Raised when source.validate() fails or returns False."""

    def __init__(self, short_name: str, reason: str):
        self.short_name = short_name
        self.reason = reason
        super().__init__(f"Validation failed for source '{short_name}': {reason}")
