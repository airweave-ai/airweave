"""Error classification types for the search domain."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import FrozenSet


class SearchErrorCategory(str, Enum):
    """Error categories for search request failures.

    User errors (4xx) should not emit SearchFailedEvent.
    Internal errors (5xx) should emit SearchFailedEvent for monitoring.
    """

    # User errors (4xx)
    COLLECTION_NOT_FOUND = "collection_not_found"
    NO_SOURCES = "no_sources"
    INVALID_REQUEST = "invalid_request"
    SOURCE_AUTH_EXPIRED = "source_auth_expired"

    # Internal errors (5xx)
    VECTOR_DB_ERROR = "vector_db_error"
    EMBEDDING_ERROR = "embedding_error"
    LLM_ERROR = "llm_error"
    FEDERATED_SOURCE_ERROR = "federated_source_error"
    INTERNAL_ERROR = "internal_error"


SEARCH_USER_ERROR_CATEGORIES: FrozenSet[SearchErrorCategory] = frozenset(
    {
        SearchErrorCategory.COLLECTION_NOT_FOUND,
        SearchErrorCategory.NO_SOURCES,
        SearchErrorCategory.INVALID_REQUEST,
        SearchErrorCategory.SOURCE_AUTH_EXPIRED,
    }
)


@dataclass(frozen=True, slots=True)
class SearchErrorClassification:
    """Result of classify_search_error(): category, safe message, and user-error flag."""

    category: SearchErrorCategory
    user_message: str
    is_user_error: bool
