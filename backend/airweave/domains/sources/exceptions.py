"""Source domain exceptions."""

from airweave.core.exceptions import NotFoundException


class SourceNotFoundError(NotFoundException):
    """Raised when a source with the given short_name does not exist or is hidden."""

    def __init__(self, short_name: str):
        self.short_name = short_name
        super().__init__(f"Source not found: {short_name}")
