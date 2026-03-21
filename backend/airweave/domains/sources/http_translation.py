"""Map ``SourceError`` hierarchy to HTTP responses for credential validation flows."""

from __future__ import annotations

from fastapi import HTTPException

from airweave.domains.sources.exceptions import (
    SourceAuthError,
    SourceCreationError,
    SourceError,
    SourceNotFoundError,
    SourceRateLimitError,
    SourceServerError,
    SourceValidationError,
)


def http_exception_for_credential_validation(
    exc: Exception,
    *,
    source_short_name: str,
) -> HTTPException:
    """Translate domain exceptions from ``SourceLifecycleService.validate`` to HTTP.

    Used when checking credentials before persisting (OAuth callback, token injection,
    direct auth). Does not leak raw upstream error bodies for auth failures.

    Args:
        exc: Exception raised by ``validate()`` or registry lookup.
        source_short_name: Source identifier for user-facing messages.

    Returns:
        ``HTTPException`` with an appropriate status code and detail string.
    """
    if isinstance(exc, SourceNotFoundError):
        return HTTPException(status_code=404, detail=str(exc))

    if isinstance(exc, (SourceCreationError, SourceValidationError)):
        return HTTPException(status_code=400, detail=str(exc))

    if isinstance(exc, SourceAuthError):
        return HTTPException(
            status_code=400,
            detail=(
                f"Invalid or revoked OAuth access token for source '{source_short_name}'. "
                "Verify the token with the provider and try again."
            ),
        )

    if isinstance(exc, SourceRateLimitError):
        retry_int = max(1, int(exc.retry_after))
        return HTTPException(
            status_code=429,
            detail=str(exc),
            headers={"Retry-After": str(retry_int)},
        )

    if isinstance(exc, SourceServerError):
        return HTTPException(
            status_code=502,
            detail=(
                f"The provider for '{source_short_name}' returned an error while validating "
                "credentials. Please try again later."
            ),
        )

    if isinstance(exc, SourceError):
        return HTTPException(status_code=400, detail=str(exc))

    return HTTPException(
        status_code=500,
        detail="Unexpected error while validating credentials.",
    )
