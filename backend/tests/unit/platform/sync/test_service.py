"""Unit tests for the SyncService class."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from airweave import schemas
from airweave.db.unit_of_work import UnitOfWork
from airweave.core.sync_service import SyncService, sync_service


@pytest.fixture
def mock_uow():
    """Create a mock unit of work."""
    mock = MagicMock(spec=UnitOfWork)
    mock.session = AsyncMock(spec=AsyncSession)
    return mock


class TestSyncServiceCreate:
    """Tests for the SyncService.create method."""

    @pytest.mark.asyncio
    async def test_create_success(self, mock_db, mock_user, mock_uow):
        """Test successful sync creation."""
        # Arrange
        sync_id = uuid.uuid4()

        # Mock crud.sync.create
        with patch("airweave.crud.sync.create") as mock_create:
            mock_sync = MagicMock(spec=schemas.Sync)
            mock_sync.id = sync_id
            mock_create.return_value = mock_sync

            # Mock dag_service.create_initial_dag
            with patch(
                "airweave.core.dag_service.dag_service.create_initial_dag"
            ) as mock_create_dag:
                mock_create_dag.return_value = MagicMock(spec=schemas.SyncDag)

                # Create sync input
                sync_create = schemas.SyncCreate(
                    name="Test Sync",
                    description="Test description",
                    source_connection_id=uuid.uuid4(),
                    destination_connection_ids=[uuid.uuid4()],
                )

                # Act
                service = SyncService()
                result = await service.create(
                    db=mock_db,
                    sync=sync_create,
                    current_user=mock_user,
                    uow=mock_uow,
                )

                # Assert
                mock_create.assert_called_once_with(
                    db=mock_db,
                    obj_in=sync_create,
                    current_user=mock_user,
                    uow=mock_uow,
                )
                mock_uow.session.flush.assert_called_once()
                mock_create_dag.assert_called_once_with(
                    db=mock_db,
                    sync_id=sync_id,
                    current_user=mock_user,
                    uow=mock_uow,
                )
                assert result == mock_sync


class TestSyncServiceRun:
    """Tests for the SyncService.run method."""

    @pytest.mark.asyncio
    async def test_run_success(self, mock_sync, mock_sync_job, mock_sync_dag, mock_user):
        """Test successful sync run."""
        # Arrange
        mock_db_context = AsyncMock()
        mock_db = AsyncMock(spec=AsyncSession)
        mock_db_context.__aenter__.return_value = mock_db

        mock_sync_context = MagicMock()
        mock_sync_result = MagicMock(spec=schemas.Sync)

        # Mock get_db_context
        with patch("airweave.core.sync_service.get_db_context") as mock_get_db_context:
            mock_get_db_context.return_value = mock_db_context

            # Mock SyncContextFactory.create
            with patch(
                "airweave.core.sync_service.SyncContextFactory.create"
            ) as mock_create_context:
                mock_create_context.return_value = mock_sync_context

                # Mock sync_orchestrator.run
                with patch("airweave.core.sync_service.sync_orchestrator.run") as mock_run:
                    mock_run.return_value = mock_sync_result

                    # Act
                    service = SyncService()
                    result = await service.run(
                        sync=mock_sync,
                        sync_job=mock_sync_job,
                        dag=mock_sync_dag,
                        current_user=mock_user,
                    )

                    # Assert
                    mock_get_db_context.assert_called_once()
                    mock_create_context.assert_called_once_with(
                        mock_db, mock_sync, mock_sync_job, mock_sync_dag, mock_user
                    )
                    mock_run.assert_called_once_with(mock_sync_context)
                    assert result == mock_sync_result

    @pytest.mark.asyncio
    async def test_run_error_handling(self, mock_sync, mock_sync_job, mock_sync_dag, mock_user):
        """Test error handling during sync run."""
        # Arrange
        mock_db_context = AsyncMock()
        mock_db = AsyncMock(spec=AsyncSession)
        mock_db_context.__aenter__.return_value = mock_db
        test_error = Exception("Test error")

        # Mock get_db_context
        with patch("airweave.core.sync_service.get_db_context") as mock_get_db_context:
            mock_get_db_context.return_value = mock_db_context

            # Mock SyncContextFactory.create to raise an exception
            with patch(
                "airweave.core.sync_service.SyncContextFactory.create"
            ) as mock_create_context:
                mock_create_context.side_effect = test_error

                # Mock logger.error
                with patch("airweave.core.sync_service.logger.error") as mock_logger_error:
                    # Act & Assert
                    with patch("airweave.core.sync_service.sync_job_service.update_status") as mock_update_status:
                        mock_update_status.return_value = None
                        service = SyncService()
                        with pytest.raises(Exception) as excinfo:
                            await service.run(
                                sync=mock_sync,
                                sync_job=mock_sync_job,
                                dag=mock_sync_dag,
                                current_user=mock_user,
                            )

                    # Verify the exception was logged and re-raised
                    assert excinfo.value == test_error
                    mock_logger_error.assert_called_once()
                    assert "Error during sync" in mock_logger_error.call_args[0][0]


class TestSyncServiceSingleton:
    """Tests for the SyncService singleton instance."""

    def test_singleton_instance(self):
        """Test that sync_service is an instance of SyncService."""
        assert isinstance(sync_service, SyncService)
