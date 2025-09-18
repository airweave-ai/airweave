import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from airweave import crud, schemas
from airweave.api.context import ApiContext
from airweave.core.source_connection_service import source_connection_service
from airweave.core.shared_models import SourceConnectionStatus


@pytest.fixture
def mock_ctx():
    return MagicMock(
        spec=ApiContext,
        organization=MagicMock(id=uuid.uuid4()),
        user=MagicMock(id=uuid.uuid4(), email="test@example.com"),
        logger=MagicMock(),
    )


@pytest.fixture
def mock_db():
    return AsyncMock(spec=AsyncSession)


@pytest.fixture
def source_connection_id():
    return uuid.uuid4()


@pytest.fixture
def mock_source_connection():
    return schemas.SourceConnection(
        id=uuid.uuid4(),
        name="Test Source Connection",
        description="Test description",
        short_name="test_source",
        status=SourceConnectionStatus.ACTIVE,
        sync_id=uuid.uuid4(),
        collection="test-collection",
        connection_id=uuid.uuid4(),
        created_at="2023-01-01T00:00:00",
        modified_at="2023-01-01T00:00:00",
    )


@pytest.mark.asyncio
class TestSourceConnectionService:
    # Tests for delete_source_connection
    async def test_delete_source_connection_without_data(
        self, mock_db, mock_ctx, source_connection_id, mock_source_connection
    ):
        # Arrange
        crud.source_connection.get = AsyncMock(return_value=mock_source_connection)
        crud.source_connection.remove = AsyncMock(return_value=mock_source_connection)

        with patch(
            "airweave.core.source_connection_service.temporal_schedule_service"
        ) as mock_temporal:
            mock_temporal.delete_all_schedules_for_sync = AsyncMock()

            # Act
            result = await source_connection_service.delete_source_connection(
                db=mock_db,
                source_connection_id=source_connection_id,
                ctx=mock_ctx,
                delete_data=False,
            )

            # Assert
            crud.source_connection.get.assert_called_once_with(
                db=mock_db, id=source_connection_id, ctx=mock_ctx
            )
            crud.source_connection.remove.assert_called_once_with(
                db=mock_db, id=source_connection_id, ctx=mock_ctx
            )
            mock_ctx.logger.info.assert_any_call(
                f"Skipping data deletion for source connection {source_connection_id}"
            )
            mock_temporal.delete_all_schedules_for_sync.assert_called_once_with(
                sync_id=mock_source_connection.sync_id, db=mock_db, ctx=mock_ctx
            )
            assert result == mock_source_connection

    async def test_delete_source_connection_with_data(
        self, mock_db, mock_ctx, source_connection_id, mock_source_connection
    ):
        # Arrange
        mock_collection = MagicMock(id=uuid.uuid4())
        crud.source_connection.get = AsyncMock(return_value=mock_source_connection)
        crud.source_connection.remove = AsyncMock(return_value=mock_source_connection)
        crud.collection.get_by_readable_id = AsyncMock(return_value=mock_collection)

        with patch(
            "airweave.core.source_connection_service.temporal_schedule_service"
        ) as mock_temporal, patch(
            "airweave.platform.destinations.qdrant.QdrantDestination"
        ) as mock_qdrant_class:

            mock_temporal.delete_all_schedules_for_sync = AsyncMock()
            mock_qdrant_instance = AsyncMock()
            mock_qdrant_class.create.return_value = mock_qdrant_instance
            mock_qdrant_instance.delete_by_sync_id = AsyncMock()

            # Act
            result = await source_connection_service.delete_source_connection(
                db=mock_db,
                source_connection_id=source_connection_id,
                ctx=mock_ctx,
                delete_data=True,
            )

            # Assert
            crud.source_connection.get.assert_called_once_with(
                db=mock_db, id=source_connection_id, ctx=mock_ctx
            )
            crud.source_connection.remove.assert_called_once_with(
                db=mock_db, id=source_connection_id, ctx=mock_ctx
            )
            crud.collection.get_by_readable_id.assert_called_once_with(
                db=mock_db,
                readable_id=mock_source_connection.readable_collection_id,
                ctx=mock_ctx,
            )
            mock_qdrant_class.create.assert_called_once_with(
                collection_id=mock_collection.id
            )
            mock_qdrant_instance.delete_by_sync_id.assert_called_once_with(
                mock_source_connection.sync_id
            )
            mock_ctx.logger.info.assert_any_call(
                f"Deleting data for source connection {source_connection_id} "
                f"(sync_id: {mock_source_connection.sync_id}) from destinations"
            )
            assert result == mock_source_connection
