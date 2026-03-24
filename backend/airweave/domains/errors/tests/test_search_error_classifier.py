"""Tests for search_error_classifier.classify_search_error()."""

import pytest

from airweave.core.exceptions import (
    CollectionNotFoundException,
    InvalidInputError,
)
from airweave.domains.search.types.errors import SearchErrorCategory
from airweave.domains.embedders.exceptions import EmbedderError
from airweave.domains.errors.search_error_classifier import classify_search_error
from airweave.domains.search.adapters.vector_db.exceptions import VectorDBError
from airweave.domains.search.exceptions import FederatedSearchError
from airweave.domains.sources.exceptions import SourceAuthError, SourceCreationError


# ---------------------------------------------------------------------------
# User errors — is_user_error=True
# ---------------------------------------------------------------------------


class TestUserErrors:
    """User errors should be classified with is_user_error=True."""

    def test_collection_not_found(self) -> None:
        exc = CollectionNotFoundException("Collection 'foo' not found")
        result = classify_search_error(exc)
        assert result.category == SearchErrorCategory.COLLECTION_NOT_FOUND
        assert result.is_user_error is True

    def test_invalid_input_no_sources(self) -> None:
        exc = InvalidInputError("Collection 'foo' has no sources.")
        result = classify_search_error(exc)
        assert result.category == SearchErrorCategory.NO_SOURCES
        assert result.is_user_error is True

    def test_invalid_input_no_sources_case_insensitive(self) -> None:
        exc = InvalidInputError("No Sources connected to this collection")
        result = classify_search_error(exc)
        assert result.category == SearchErrorCategory.NO_SOURCES
        assert result.is_user_error is True

    def test_invalid_input_other(self) -> None:
        exc = InvalidInputError("Limit must be positive")
        result = classify_search_error(exc)
        assert result.category == SearchErrorCategory.INVALID_REQUEST
        assert result.is_user_error is True

    def test_pydantic_validation_error(self) -> None:
        from pydantic import BaseModel, ValidationError

        class Dummy(BaseModel):
            x: int

        with pytest.raises(ValidationError) as exc_info:
            Dummy(x="not_an_int")  # type: ignore[arg-type]

        result = classify_search_error(exc_info.value)
        assert result.category == SearchErrorCategory.INVALID_REQUEST
        assert result.is_user_error is True

    def test_source_auth_error(self) -> None:
        exc = SourceAuthError(
            "401 Unauthorized",
            source_short_name="slack",
            status_code=401,
            token_provider_kind="oauth",
        )
        result = classify_search_error(exc)
        assert result.category == SearchErrorCategory.SOURCE_AUTH_EXPIRED
        assert result.is_user_error is True

    def test_source_creation_error(self) -> None:
        exc = SourceCreationError("slack", reason="bad credentials")
        result = classify_search_error(exc)
        assert result.category == SearchErrorCategory.SOURCE_AUTH_EXPIRED
        assert result.is_user_error is True


# ---------------------------------------------------------------------------
# Internal errors — is_user_error=False
# ---------------------------------------------------------------------------


class TestInternalErrors:
    """Internal errors should be classified with is_user_error=False."""

    def test_federated_search_error(self) -> None:
        exc = FederatedSearchError([("slack", RuntimeError("timeout"))])
        result = classify_search_error(exc)
        assert result.category == SearchErrorCategory.FEDERATED_SOURCE_ERROR
        assert result.is_user_error is False

    def test_federated_search_error_all_auth_inner(self) -> None:
        """All inner errors are auth → SOURCE_AUTH_EXPIRED (user error)."""
        inner = SourceAuthError(
            "401", source_short_name="slack", status_code=401, token_provider_kind="oauth"
        )
        exc = FederatedSearchError([("slack", inner)])
        result = classify_search_error(exc)
        assert result.category == SearchErrorCategory.SOURCE_AUTH_EXPIRED
        assert result.is_user_error is True

    def test_federated_search_error_mixed_inner(self) -> None:
        """Mix of auth + other errors → FEDERATED_SOURCE_ERROR (internal)."""
        auth = SourceAuthError(
            "401", source_short_name="slack", status_code=401, token_provider_kind="oauth"
        )
        timeout = RuntimeError("connection timeout")
        exc = FederatedSearchError([("slack", auth), ("github", timeout)])
        result = classify_search_error(exc)
        assert result.category == SearchErrorCategory.FEDERATED_SOURCE_ERROR
        assert result.is_user_error is False

    def test_vector_db_error(self) -> None:
        exc = VectorDBError("Vespa query compilation failed")
        result = classify_search_error(exc)
        assert result.category == SearchErrorCategory.VECTOR_DB_ERROR
        assert result.is_user_error is False

    def test_embedder_error(self) -> None:
        exc = EmbedderError("Embedding service timeout")
        result = classify_search_error(exc)
        assert result.category == SearchErrorCategory.EMBEDDING_ERROR
        assert result.is_user_error is False

    def test_unknown_exception(self) -> None:
        exc = RuntimeError("something unexpected")
        result = classify_search_error(exc)
        assert result.category == SearchErrorCategory.INTERNAL_ERROR
        assert result.is_user_error is False

    def test_generic_exception(self) -> None:
        exc = Exception("generic failure")
        result = classify_search_error(exc)
        assert result.category == SearchErrorCategory.INTERNAL_ERROR
        assert result.is_user_error is False


# ---------------------------------------------------------------------------
# User messages
# ---------------------------------------------------------------------------


class TestUserMessages:
    """Every classification should have a non-empty user_message."""

    @pytest.mark.parametrize(
        "exc",
        [
            CollectionNotFoundException("not found"),
            InvalidInputError("has no sources"),
            InvalidInputError("bad param"),
            SourceAuthError("401", source_short_name="x", status_code=401, token_provider_kind="o"),
            FederatedSearchError([("x", RuntimeError("err"))]),
            VectorDBError("err"),
            EmbedderError("err"),
            RuntimeError("err"),
        ],
    )
    def test_user_message_is_non_empty(self, exc: Exception) -> None:
        result = classify_search_error(exc)
        assert result.user_message
        assert len(result.user_message) > 10
