"""Error classifier for search request failures.

Maps exceptions to SearchErrorCategory with safe user-facing messages.
Pure function — no I/O, no database access.
"""

from __future__ import annotations

from pydantic import ValidationError

from airweave.core.exceptions import (
    CollectionNotFoundException,
    InvalidInputError,
)
from airweave.domains.embedders.exceptions import EmbedderError
from airweave.domains.search.adapters.vector_db.exceptions import VectorDBError
from airweave.domains.search.exceptions import FederatedSearchError
from airweave.domains.search.types.errors import (
    SEARCH_USER_ERROR_CATEGORIES,
    SearchErrorCategory,
    SearchErrorClassification,
)
from airweave.domains.sources.exceptions import SourceAuthError, SourceCreationError

_USER_MESSAGES: dict[SearchErrorCategory, str] = {
    SearchErrorCategory.COLLECTION_NOT_FOUND: (
        "Collection not found. Check the collection name and try again."
    ),
    SearchErrorCategory.NO_SOURCES: (
        "This collection has no sources. Add a source connection before searching."
    ),
    SearchErrorCategory.INVALID_REQUEST: ("Invalid request. Check your parameters and try again."),
    SearchErrorCategory.SOURCE_AUTH_EXPIRED: ("A connected source requires re-authentication."),
    SearchErrorCategory.VECTOR_DB_ERROR: (
        "Search infrastructure temporarily unavailable. Please try again."
    ),
    SearchErrorCategory.EMBEDDING_ERROR: (
        "Search infrastructure temporarily unavailable. Please try again."
    ),
    SearchErrorCategory.LLM_ERROR: ("AI service temporarily unavailable. Please try again."),
    SearchErrorCategory.FEDERATED_SOURCE_ERROR: (
        "A connected source is temporarily unavailable. Please try again."
    ),
    SearchErrorCategory.INTERNAL_ERROR: ("An unexpected error occurred. Please try again."),
}


def classify_search_error(exc: Exception) -> SearchErrorClassification:
    """Classify a search exception into a category with a safe user message.

    Args:
        exc: The exception that caused the search failure.

    Returns:
        SearchErrorClassification with category, user_message, and is_user_error flag.
    """
    # Collection not found
    if isinstance(exc, CollectionNotFoundException):
        return _make(SearchErrorCategory.COLLECTION_NOT_FOUND)

    # Invalid input — distinguish "no sources" from general validation errors
    if isinstance(exc, InvalidInputError):
        if "no sources" in str(exc).lower():
            return _make(SearchErrorCategory.NO_SOURCES)
        return _make(SearchErrorCategory.INVALID_REQUEST)

    # Pydantic validation errors (e.g., bad filters, wrong parameter types)
    if isinstance(exc, ValidationError):
        return _make(SearchErrorCategory.INVALID_REQUEST)

    # Source auth/creation errors (federated search sources)
    if isinstance(exc, (SourceAuthError, SourceCreationError)):
        return _make(SearchErrorCategory.SOURCE_AUTH_EXPIRED)

    # Federated search error — inspect inner errors to classify accurately.
    # If all inner errors are auth/creation errors, the root cause is the user's
    # credentials, not our infrastructure. Otherwise it's a transient source failure.
    if isinstance(exc, FederatedSearchError):
        return _classify_federated(exc)

    # Vector DB errors (Vespa failures)
    if isinstance(exc, VectorDBError):
        return _make(SearchErrorCategory.VECTOR_DB_ERROR)

    # Embedding errors
    if isinstance(exc, EmbedderError):
        return _make(SearchErrorCategory.EMBEDDING_ERROR)

    # Catch-all for unexpected errors
    return _make(SearchErrorCategory.INTERNAL_ERROR)


def _classify_federated(exc: FederatedSearchError) -> SearchErrorClassification:
    """Classify a FederatedSearchError by inspecting its inner errors.

    If every inner error is an auth/creation error, the root cause is the
    user's credentials — classify as SOURCE_AUTH_EXPIRED (user error).
    Otherwise, at least one source failed for infrastructure reasons —
    classify as FEDERATED_SOURCE_ERROR (internal, transient).
    """
    if exc.source_errors and all(
        isinstance(inner, (SourceAuthError, SourceCreationError)) for _, inner in exc.source_errors
    ):
        return _make(SearchErrorCategory.SOURCE_AUTH_EXPIRED)
    return _make(SearchErrorCategory.FEDERATED_SOURCE_ERROR)


def _make(category: SearchErrorCategory) -> SearchErrorClassification:
    """Build a SearchErrorClassification from a category."""
    return SearchErrorClassification(
        category=category,
        user_message=_USER_MESSAGES[category],
        is_user_error=category in SEARCH_USER_ERROR_CATEGORIES,
    )
