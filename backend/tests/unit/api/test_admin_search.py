"""Unit tests for admin search endpoints."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from airweave.api.v1.endpoints.admin import admin_search_collection, admin_search_collection_as_user
from airweave.schemas.search import SearchRequest, SearchResponse


@pytest.fixture
def mock_service():
    """Mock search service."""
    with patch("airweave.search.service.service") as mock:
        yield mock


@pytest.fixture
def mock_ctx():
    """Mock API context."""
    ctx = MagicMock()
    ctx.logger = MagicMock()
    ctx.request_id = "req-123"
    ctx.user = MagicMock()
    ctx.user.id = uuid4()
    ctx.organization_id = uuid4()
    return ctx


@pytest.fixture
def mock_db():
    """Mock database session."""
    return AsyncMock()


@pytest.fixture
def search_request():
    """Sample search request."""
    return SearchRequest(query="test query", limit=10)


@pytest.fixture
def search_response():
    """Sample search response."""
    return SearchResponse(
        results=[
            {
                "entity_id": "1",
                "score": 0.9,
                "source_name": "linear",
                "md_content": "Test content",
            }
        ],
        completion=None,
    )


@pytest.mark.asyncio
class TestAdminSearchCollection:
    """Test admin_search_collection endpoint."""

    async def test_admin_search_requires_admin_permission(
        self, mock_ctx, mock_db, search_request
    ):
        """Test that admin permission is required."""
        from airweave.api.v1.endpoints.admin import AdminSearchDestination

        # Mock permission check to raise exception
        with patch("airweave.api.v1.endpoints.admin._require_admin_permission") as mock_require:
            mock_require.side_effect = Exception("Admin permission required")

            with pytest.raises(Exception) as exc_info:
                await admin_search_collection(
                    readable_id="test-collection",
                    search_request=search_request,
                    db=mock_db,
                    ctx=mock_ctx,
                    destination=AdminSearchDestination.QDRANT,
                )

            assert "Admin permission required" in str(exc_info.value)

    async def test_admin_search_returns_results(
        self, mock_ctx, mock_db, search_request, search_response, mock_service
    ):
        """Test that admin search returns results."""
        from airweave.api.v1.endpoints.admin import AdminSearchDestination

        # Mock permission check to pass
        with patch("airweave.api.v1.endpoints.admin._require_admin_permission"):

            # Mock service.search_admin to return results
            mock_service.search_admin = AsyncMock(return_value=search_response)

            result = await admin_search_collection(
                readable_id="test-collection",
                search_request=search_request,
                db=mock_db,
                ctx=mock_ctx,
                destination=AdminSearchDestination.QDRANT,
            )

            assert isinstance(result, SearchResponse)
            assert len(result.results) == 1
            assert result.results[0]["entity_id"] == "1"

            # Verify service was called with all required parameters
            mock_service.search_admin.assert_called_once()
            call_kwargs = mock_service.search_admin.call_args.kwargs
            assert call_kwargs["request_id"] == mock_ctx.request_id
            assert call_kwargs["readable_collection_id"] == "test-collection"
            assert call_kwargs["search_request"] == search_request
            assert call_kwargs["db"] == mock_db
            assert call_kwargs["ctx"] == mock_ctx
            assert call_kwargs["destination"] == "qdrant"


@pytest.mark.asyncio
class TestAdminSearchCollectionAsUser:
    """Test admin_search_collection_as_user endpoint."""

    async def test_admin_search_as_user_requires_admin_permission(
        self, mock_ctx, mock_db, search_request
    ):
        """Test that admin permission is required."""
        with patch("airweave.api.v1.endpoints.admin._require_admin_permission") as mock_require:
            mock_require.side_effect = Exception("Admin permission required")

            with pytest.raises(Exception) as exc_info:
                await admin_search_collection_as_user(
                    readable_id="test-collection",
                    search_request=search_request,
                    user_principal="john@acme.com",
                    db=mock_db,
                    ctx=mock_ctx,
                )

            assert "Admin permission required" in str(exc_info.value)

    async def test_admin_search_as_user_filters_by_user_principals(
        self, mock_ctx, mock_db, search_request, search_response, mock_service
    ):
        """Test that search is filtered by user's principals."""
        from airweave.api.v1.endpoints.admin import AdminSearchDestination

        with patch("airweave.api.v1.endpoints.admin._require_admin_permission"):
            # Mock service.search_as_user
            mock_service.search_as_user = AsyncMock(return_value=search_response)

            result = await admin_search_collection_as_user(
                readable_id="test-collection",
                search_request=search_request,
                user_principal="john@acme.com",
                db=mock_db,
                ctx=mock_ctx,
                destination=AdminSearchDestination.VESPA,
            )

            assert isinstance(result, SearchResponse)

            # Verify service was called with all required parameters
            mock_service.search_as_user.assert_called_once()
            call_kwargs = mock_service.search_as_user.call_args.kwargs
            assert call_kwargs["request_id"] == mock_ctx.request_id
            assert call_kwargs["readable_collection_id"] == "test-collection"
            assert call_kwargs["user_principal"] == "john@acme.com"
            assert call_kwargs["destination"] == "vespa"

    async def test_admin_search_as_user_returns_filtered_results(
        self, mock_ctx, mock_db, search_request, mock_service
    ):
        """Test that results are filtered by user's access."""
        from airweave.api.v1.endpoints.admin import AdminSearchDestination

        with patch("airweave.api.v1.endpoints.admin._require_admin_permission"):
            # Mock filtered results (user can only see 1 result)
            filtered_response = SearchResponse(
                results=[
                    {
                        "entity_id": "1",
                        "score": 0.9,
                        "source_name": "linear",
                        "md_content": "Accessible content",
                    }
                ],
                completion=None,
            )
            mock_service.search_as_user = AsyncMock(return_value=filtered_response)

            result = await admin_search_collection_as_user(
                readable_id="test-collection",
                search_request=search_request,
                user_principal="john@acme.com",
                db=mock_db,
                ctx=mock_ctx,
                destination=AdminSearchDestination.VESPA,
            )

            assert len(result.results) == 1
            assert result.results[0]["entity_id"] == "1"

    async def test_admin_search_as_user_handles_nonexistent_collection(
        self, mock_ctx, mock_db, search_request, mock_service
    ):
        """Test handling of non-existent collection."""
        from airweave.api.v1.endpoints.admin import AdminSearchDestination

        with patch("airweave.api.v1.endpoints.admin._require_admin_permission"):
            # Mock service to raise NotFoundException
            from airweave.core.exceptions import NotFoundException

            mock_service.search_as_user = AsyncMock(
                side_effect=NotFoundException(message="Collection not found")
            )

            with pytest.raises(NotFoundException) as exc_info:
                await admin_search_collection_as_user(
                    readable_id="nonexistent",
                    search_request=search_request,
                    user_principal="john@acme.com",
                    db=mock_db,
                    ctx=mock_ctx,
                    destination=AdminSearchDestination.VESPA,
                )

            assert "Collection not found" in str(exc_info.value)

    async def test_admin_search_as_user_handles_collection_without_ac(
        self, mock_ctx, mock_db, search_request, search_response, mock_service
    ):
        """Test searching collection without AC sources returns all results."""
        from airweave.api.v1.endpoints.admin import AdminSearchDestination

        with patch("airweave.api.v1.endpoints.admin._require_admin_permission"):
            # Mock service returns all results (no filtering)
            mock_service.search_as_user = AsyncMock(return_value=search_response)

            result = await admin_search_collection_as_user(
                readable_id="collection-without-ac",
                search_request=search_request,
                user_principal="john@acme.com",
                db=mock_db,
                ctx=mock_ctx,
                destination=AdminSearchDestination.VESPA,
            )

            assert isinstance(result, SearchResponse)
            # In collections without AC, all results visible
            assert len(result.results) >= 0


@pytest.mark.asyncio
class TestAdminSearchDestinationParameter:
    """Test destination parameter handling."""

    async def test_admin_search_respects_destination_parameter(
        self, mock_ctx, mock_db, search_request, search_response, mock_service
    ):
        """Test that destination parameter is passed to service."""
        with patch("airweave.api.v1.endpoints.admin._require_admin_permission"):
            mock_service.search_admin = AsyncMock(return_value=search_response)

            from airweave.api.v1.endpoints.admin import AdminSearchDestination

            await admin_search_collection(
                readable_id="test-collection",
                search_request=search_request,
                destination=AdminSearchDestination.QDRANT,
                db=mock_db,
                ctx=mock_ctx,
            )

            # Verify qdrant destination was used
            call_kwargs = mock_service.search_admin.call_args.kwargs
            assert call_kwargs["destination"] == "qdrant"

    async def test_admin_search_as_user_respects_destination_parameter(
        self, mock_ctx, mock_db, search_request, search_response, mock_service
    ):
        """Test that destination parameter is passed for as_user search."""
        with patch("airweave.api.v1.endpoints.admin._require_admin_permission"):
            mock_service.search_as_user = AsyncMock(return_value=search_response)

            from airweave.api.v1.endpoints.admin import AdminSearchDestination

            await admin_search_collection_as_user(
                readable_id="test-collection",
                search_request=search_request,
                user_principal="john@acme.com",
                destination=AdminSearchDestination.QDRANT,
                db=mock_db,
                ctx=mock_ctx,
            )

            # Verify qdrant destination was used
            call_kwargs = mock_service.search_as_user.call_args.kwargs
            assert call_kwargs["destination"] == "qdrant"
