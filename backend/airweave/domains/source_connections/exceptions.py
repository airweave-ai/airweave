"""Source connection domain exceptions."""

from airweave.core.exceptions import BadRequestError, NotFoundException


class SourceConnectionNotFoundError(NotFoundException):
    """Raised when a source connection does not exist."""

    def __init__(self, id):
        super().__init__(f"Source connection not found: {id}")


class CollectionNotFoundError(NotFoundException):
    """Raised when a collection does not exist."""

    def __init__(self, readable_id: str):
        super().__init__(f"Collection not found: {readable_id}")


class InvalidAuthMethodError(BadRequestError):
    """Raised when an unsupported auth method is requested for a source."""

    def __init__(self, method: str, supported: list[str]):
        super().__init__(f"Unsupported auth method: {method}. Supported: {supported}")


class ByocRequiredError(BadRequestError):
    """Raised when a source requires BYOC but no custom credentials were provided."""

    def __init__(self, short_name: str):
        super().__init__(
            f"Source '{short_name}' requires custom OAuth client credentials. "
            f"Please provide client_id and client_secret."
        )


class SyncImmediatelyNotAllowedError(BadRequestError):
    """Raised when sync_immediately is used with OAuth browser flows."""

    def __init__(self):
        super().__init__(
            "OAuth connections cannot use sync_immediately. Sync will start after authentication."
        )


class NoSyncError(BadRequestError):
    """Raised when an operation requires a sync but none exists."""

    def __init__(self, source_connection_id):
        super().__init__(f"Source connection {source_connection_id} has no associated sync")
