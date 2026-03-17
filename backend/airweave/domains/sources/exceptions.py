"""Source domain exceptions.

Hierarchy
---------
NotFoundException
└── SourceNotFoundError          — source short_name not in registry

SourceError (AirweaveException)  — base for ALL source runtime errors
├── SourceCreationError          — source_class.create() failed
├── SourceValidationError        — source.validate() returned False / raised
│
│   Runtime errors (during generate_entities / search / ACL / browse / tool calls)
├── SourceAuthError              — 401 after token refresh attempt → abort sync
│   └── SourceTokenRefreshError  — token refresh itself failed
├── SourceRateLimitError         — 429 from upstream API → retry with backoff
├── SourceServerError            — upstream server error (5xx / timeout / connection)
│
│   Per-entity errors (skip the entity, continue the sync)
├── SourceEntityError            — base for single-entity failures
│   ├── SourceEntityForbiddenError   — 403 on one entity
│   ├── SourceEntityNotFoundError    — 404 on one entity
│   └── SourceEntitySkippedError     — source decided to skip (too large, unsupported, etc.)
│
│   File download errors
└── SourceFileDownloadError      — file download failed for an entity
"""

from typing import Optional

from airweave.core.exceptions import (
    AirweaveException,
    NotFoundException,
)

# ---------------------------------------------------------------------------
# Lifecycle exceptions (registry / creation / validation)
# ---------------------------------------------------------------------------


class SourceNotFoundError(NotFoundException):
    """Raised when a source with the given short_name does not exist or is hidden."""

    def __init__(self, short_name: str):
        """Create a new SourceNotFoundError.

        Args:
            short_name: The source short_name that was not found.
        """
        self.short_name = short_name
        super().__init__(f"Source not found: {short_name}")


# ---------------------------------------------------------------------------
# Runtime base
# ---------------------------------------------------------------------------


class SourceError(AirweaveException):
    """Base for all source runtime errors.

    Every subclass carries source_short_name so the pipeline and
    orchestrator can log and route without inspecting the message.
    """

    def __init__(self, message: str, *, source_short_name: str = ""):
        """Create a new SourceError.

        Args:
            message: Human-readable error description.
            source_short_name: Identifier of the source that raised the error.
        """
        self.source_short_name = source_short_name
        super().__init__(message)


# ---------------------------------------------------------------------------
# Lifecycle errors (inherit from SourceError so callers can catch broadly)
# ---------------------------------------------------------------------------


class SourceCreationError(SourceError):
    """source_class.create() failed (bad credentials, missing fields, etc.)."""

    def __init__(self, short_name: str, reason: str):
        """Create a new SourceCreationError.

        Args:
            short_name: Source identifier.
            reason: Why creation failed.
        """
        self.short_name = short_name
        self.reason = reason
        super().__init__(
            f"Failed to create source '{short_name}': {reason}",
            source_short_name=short_name,
        )


class SourceValidationError(SourceError):
    """source.validate() returned False or raised."""

    def __init__(self, short_name: str, reason: str):
        """Create a new SourceValidationError.

        Args:
            short_name: Source identifier.
            reason: Why validation failed.
        """
        self.short_name = short_name
        self.reason = reason
        super().__init__(
            f"Validation failed for source '{short_name}': {reason}",
            source_short_name=short_name,
        )


# ---------------------------------------------------------------------------
# Auth errors
# ---------------------------------------------------------------------------


class SourceAuthError(SourceError):
    """401 Unauthorized after token refresh attempt.

    The pipeline should abort the sync — credentials are invalid or revoked.
    """

    def __init__(
        self,
        message: str = "Authentication failed after token refresh",
        *,
        source_short_name: str = "",
        status_code: int = 401,
    ):
        """Create a new SourceAuthError.

        Args:
            message: Human-readable error description.
            source_short_name: Source identifier.
            status_code: HTTP status code that triggered this (usually 401).
        """
        self.status_code = status_code
        super().__init__(message, source_short_name=source_short_name)


class SourceTokenRefreshError(SourceAuthError):
    """Token refresh failed — the underlying OAuth or auth-provider call did not succeed.

    Raised by TokenProvider implementations when refresh is attempted but fails.
    Subclass of SourceAuthError so pipelines that catch auth errors broadly
    will also catch refresh failures.
    """

    def __init__(
        self,
        message: str = "Token refresh failed",
        *,
        source_short_name: str = "",
    ):
        """Create a new SourceTokenRefreshError.

        Args:
            message: Human-readable error description.
            source_short_name: Source identifier.
        """
        super().__init__(message, source_short_name=source_short_name, status_code=401)


# ---------------------------------------------------------------------------
# Rate limiting
# ---------------------------------------------------------------------------


class SourceRateLimitError(SourceError):
    """429 Too Many Requests from the upstream API.

    The retry decorator / pipeline should wait ``retry_after`` seconds
    before retrying the request.
    """

    def __init__(
        self,
        *,
        retry_after: float,
        source_short_name: str = "",
        message: Optional[str] = None,
    ):
        """Create a new SourceRateLimitError.

        Args:
            retry_after: Seconds to wait before retrying.
            source_short_name: Source identifier.
            message: Optional custom message.
        """
        self.retry_after = retry_after
        msg = message or f"Rate limited — retry after {retry_after:.1f}s"
        super().__init__(msg, source_short_name=source_short_name)


# ---------------------------------------------------------------------------
# Upstream server errors
# ---------------------------------------------------------------------------


class SourceServerError(SourceError):
    """Upstream server error (5xx, timeout, connection reset, or other non-auth failure)."""

    def __init__(
        self,
        message: str = "Upstream server error",
        *,
        source_short_name: str = "",
        status_code: Optional[int] = None,
    ):
        """Create a new SourceServerError.

        Args:
            message: Human-readable error description.
            source_short_name: Source identifier.
            status_code: HTTP status code if applicable.
        """
        self.status_code = status_code
        super().__init__(message, source_short_name=source_short_name)


SourceTemporaryError = SourceServerError
SourcePermanentError = SourceServerError


# ---------------------------------------------------------------------------
# Per-entity errors (skip the entity, continue the sync)
# ---------------------------------------------------------------------------


class SourceEntityError(SourceError):
    """Base for errors tied to a single entity.

    The pipeline should skip this entity and continue processing.
    """

    def __init__(
        self,
        message: str,
        *,
        source_short_name: str = "",
        entity_id: str = "",
    ):
        """Create a new SourceEntityError.

        Args:
            message: Human-readable error description.
            source_short_name: Source identifier.
            entity_id: ID of the entity that failed.
        """
        self.entity_id = entity_id
        super().__init__(message, source_short_name=source_short_name)


class SourceEntityForbiddenError(SourceEntityError):
    """403 Forbidden when accessing a specific entity.

    Common cause: the OAuth token lacks permission for this particular
    resource (e.g. a private channel the bot isn't in). Skip and continue.
    """

    pass


class SourceEntityNotFoundError(SourceEntityError):
    """404 Not Found for a specific entity.

    The entity was deleted or moved between listing and fetching. Skip.
    """

    pass


class SourceEntitySkippedError(SourceEntityError):
    """Source intentionally skipped an entity (too large, unsupported type, etc.).

    Not an error per se, but the pipeline should count it as skipped.
    """

    def __init__(
        self,
        message: str = "Entity skipped by source",
        *,
        source_short_name: str = "",
        entity_id: str = "",
        reason: str = "",
    ):
        """Create a new SourceEntitySkippedError.

        Args:
            message: Human-readable error description.
            source_short_name: Source identifier.
            entity_id: ID of the entity that was skipped.
            reason: Why the entity was skipped.
        """
        self.reason = reason
        super().__init__(message, source_short_name=source_short_name, entity_id=entity_id)


# ---------------------------------------------------------------------------
# File download errors
# ---------------------------------------------------------------------------


class SourceFileDownloadError(SourceEntityError):
    """File download failed for an entity.

    Treated as a per-entity skip — the sync continues.
    """

    def __init__(
        self,
        message: str = "File download failed",
        *,
        source_short_name: str = "",
        status_code: Optional[int] = None,
        entity_id: str = "",
        file_url: str = "",
    ):
        """Create a new SourceFileDownloadError.

        Args:
            message: Human-readable error description.
            source_short_name: Source identifier.
            status_code: HTTP status code if applicable.
            entity_id: ID of the entity whose file failed to download.
            file_url: URL that was attempted.
        """
        self.file_url = file_url
        super().__init__(message, source_short_name=source_short_name, entity_id=entity_id)
