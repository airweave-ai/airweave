"""Integration tests for the SyncService class."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from airweave import schemas
from airweave.core.shared_models import SyncJobStatus
from airweave.db.unit_of_work import UnitOfWork
from airweave.platform.sync.context import SyncContext
from airweave.core.sync_service import SyncService


@pytest.fixture
def complete_uow():
    """Create a more complete unit of work for integration testing."""
    mock = MagicMock(spec=UnitOfWork)
    mock.session = AsyncMock(spec=AsyncSession)
    mock.commit = AsyncMock()
    mock.rollback = AsyncMock()
    mock.__aenter__ = AsyncMock(return_value=mock)
    mock.__aexit__ = AsyncMock(return_value=None)
    return mock


@pytest.mark.asyncio
class TestSyncServiceIntegration:
    """Integration tests for SyncService."""

    async def test_create_and_run_sync_flow(self, mock_db, mock_user, complete_uow, mock_sync_dag):
        """Test the full flow of creating and running a sync."""
        # Arrange
        sync_id = uuid.uuid4()

        # Mock the crud and DAG operations
        with (
            patch("airweave.crud.sync.create") as mock_create_sync,
            patch("airweave.core.dag_service.dag_service.create_initial_dag") as mock_create_dag,
            patch("airweave.core.sync_service.get_db_context") as mock_get_db_context,
            patch(
                "airweave.core.sync_service.SyncContextFactory.create"
            ) as mock_create_context,
            patch("airweave.core.sync_service.sync_orchestrator.run") as mock_run,
        ):
            # Setup mocks for create
            mock_sync = MagicMock(spec=schemas.Sync)
            mock_sync.id = sync_id
            mock_sync.name = "Test Integration Sync"
            mock_create_sync.return_value = mock_sync
            mock_create_dag.return_value = mock_sync_dag

            # Setup mocks for run
            mock_db_context = AsyncMock()
            mock_db_context.__aenter__.return_value = mock_db
            mock_get_db_context.return_value = mock_db_context

            mock_sync_context = MagicMock(spec=SyncContext)
            mock_create_context.return_value = mock_sync_context

            mock_run.return_value = mock_sync  # Return the same sync

            # Create sync request
            sync_create = schemas.SyncCreate(
                name="Test Integration Sync",
                description="Integration test description",
                source_connection_id=uuid.uuid4(),
                destination_connection_ids=[uuid.uuid4()],
            )

            # Create sync job
            sync_job = schemas.SyncJob(
                id=uuid.uuid4(),
                sync_id=sync_id,
                status=SyncJobStatus.PENDING,
                progress=0,
                error=None,
                started_at=None,
                completed_at=None,
                created_at="2023-01-01T00:00:00",
                updated_at="2023-01-01T00:00:00",
                organization_id=uuid.uuid4(),
                created_by_email="test@example.com",
                modified_by_email="test@example.com",
                modified_at="2023-01-01T00:00:00",
                entities_detected=0,
                entities_inserted=0,
                entities_deleted=0,
                entities_skipped=0,
            )

            # Act - first create the sync
            service = SyncService()
            created_sync = await service.create(
                db=mock_db,
                sync=sync_create,
                current_user=mock_user,
                uow=complete_uow,
            )

            # Act - then run the sync
            run_result = await service.run(
                sync=created_sync,
                sync_job=sync_job,
                dag=mock_sync_dag,
                current_user=mock_user,
            )

            # Assert - Verify the flow
            # Creation assertions
            mock_create_sync.assert_called_once()
            complete_uow.session.flush.assert_called_once()
            mock_create_dag.assert_called_once_with(
                db=mock_db, sync_id=sync_id, current_user=mock_user, uow=complete_uow
            )

            # Run assertions
            mock_get_db_context.assert_called_once()
            mock_create_context.assert_called_once_with(
                mock_db, created_sync, sync_job, mock_sync_dag, mock_user
            )
            mock_run.assert_called_once_with(mock_sync_context)

            # Final result assertions
            assert created_sync.id == sync_id
            assert run_result == mock_sync

    async def test_sync_service_error_recovery(
        self, mock_db, mock_user, complete_uow, mock_sync, mock_sync_job, mock_sync_dag
    ):
        """Test error recovery during a sync run."""
        # Arrange - simulate an error during sync
        test_error = Exception("Integration test error")

        # Mock required components
        with (
            patch("airweave.core.sync_service.get_db_context") as mock_get_db_context,
            patch(
                "airweave.core.sync_service.SyncContextFactory.create"
            ) as mock_create_context,
            patch("airweave.core.sync_service.logger.error") as mock_logger_error,
            patch("airweave.core.sync_service.sync_job_service.update_status") as mock_update_status,
        ):
            mock_db_context = AsyncMock()
            mock_db_context.__aenter__.return_value = mock_db
            mock_get_db_context.return_value = mock_db_context

            mock_update_status.return_value = None

            # Simulate error during context creation
            mock_create_context.side_effect = test_error

            # Act & Assert
            service = SyncService()
            with pytest.raises(Exception) as excinfo:
                await service.run(
                    sync=mock_sync,
                    sync_job=mock_sync_job,
                    dag=mock_sync_dag,
                    current_user=mock_user,
                )

            # Verify error was handled correctly
            assert excinfo.value == test_error
            mock_logger_error.assert_called_once()
            assert "Error during sync" in mock_logger_error.call_args[0][0]
