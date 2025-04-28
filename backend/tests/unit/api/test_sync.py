"""Unit tests for sync endpoints."""

import asyncio
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException
from fastapi.responses import StreamingResponse

from airweave import crud, schemas
from airweave.api.v1.endpoints import sync
from airweave.core.shared_models import ConnectionStatus, IntegrationType, SyncJobStatus
from airweave.db.unit_of_work import UnitOfWork
from airweave.platform.sync.pubsub import sync_pubsub
from airweave.platform.sync.service import sync_service

# Fixtures are imported from tests/fixtures/common.py via conftest.py


class TestListSyncs:
    """Tests for the list_syncs endpoint."""

    @pytest.mark.asyncio
    async def test_list_syncs_without_source_connection(self, mock_db, mock_user, mock_sync):
        """Test listing syncs without source connection."""
        # Arrange
        crud.sync.get_all_for_user = AsyncMock(return_value=[mock_sync])

        # Act
        result = await sync.list_syncs(
            db=mock_db, skip=0, limit=100, with_source_connection=False, user=mock_user
        )

        # Assert
        crud.sync.get_all_for_user.assert_called_once_with(
            db=mock_db, current_user=mock_user, skip=0, limit=100
        )
        assert result == [mock_sync]

    @pytest.mark.asyncio
    async def test_list_syncs_with_source_connection(self, mock_db, mock_user, mock_sync):
        """Test listing syncs with source connection."""
        # Arrange
        mock_sync_with_source = schemas.SyncWithSourceConnection(
            **mock_sync.model_dump(),
            source_connection=schemas.Connection(
                id=uuid.uuid4(),
                name="Test Source",
                short_name="test",
                integration_type=IntegrationType.SOURCE,
                status=ConnectionStatus.ACTIVE,
                organization_id=uuid.uuid4(),
                created_by_email="test@example.com",
                modified_by_email="test@example.com",
            ),
        )
        crud.sync.get_all_syncs_join_with_source_connection = AsyncMock(
            return_value=[mock_sync_with_source]
        )

        # Act
        result = await sync.list_syncs(
            db=mock_db, skip=0, limit=100, with_source_connection=True, user=mock_user
        )

        # Assert
        crud.sync.get_all_syncs_join_with_source_connection.assert_called_once_with(
            db=mock_db, current_user=mock_user
        )
        assert result == [mock_sync_with_source]


class TestGetSync:
    """Tests for the get_sync endpoint."""

    @pytest.mark.asyncio
    async def test_get_sync_found(self, mock_db, mock_user, mock_sync):
        """Test getting a sync that exists."""
        # Arrange
        crud.sync.get = AsyncMock(return_value=mock_sync)
        sync_id = mock_sync.id

        # Act
        result = await sync.get_sync(db=mock_db, sync_id=sync_id, user=mock_user)

        # Assert
        crud.sync.get.assert_called_once_with(db=mock_db, id=sync_id, current_user=mock_user)
        assert result == mock_sync

    @pytest.mark.asyncio
    async def test_get_sync_not_found(self, mock_db, mock_user):
        """Test getting a sync that doesn't exist."""
        # Arrange
        crud.sync.get = AsyncMock(return_value=None)
        sync_id = uuid.uuid4()

        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            await sync.get_sync(db=mock_db, sync_id=sync_id, user=mock_user)

        assert exc_info.value.status_code == 404
        assert exc_info.value.detail == "Sync not found"


class TestCreateSync:
    """Tests for the create_sync endpoint."""

    @pytest.mark.asyncio
    async def test_create_sync_without_run(
        self, mock_db, mock_user, mock_sync, mock_background_tasks
    ):
        """Test creating a sync without running it immediately."""
        # Arrange
        mock_uow_context = AsyncMock(spec=UnitOfWork)
        mock_uow = AsyncMock()
        mock_uow_context.__aenter__.return_value = mock_uow
        mock_uow.session = mock_db

        with patch("airweave.api.v1.endpoints.sync.UnitOfWork", return_value=mock_uow_context):
            sync_service.create = AsyncMock(return_value=mock_sync)
            sync_in = schemas.SyncCreate(
                name="Test Sync",
                description="Test description",
                source_connection_id=uuid.uuid4(),
                destination_connection_ids=[uuid.uuid4()],
                run_immediately=False,
            )

            # Act
            result = await sync.create_sync(
                db=mock_db,
                sync_in=sync_in,
                user=mock_user,
                background_tasks=mock_background_tasks,
            )

            # Assert
            sync_service.create.assert_called_once()
            mock_uow.commit.assert_called_once()
            assert result == mock_sync
            mock_background_tasks.add_task.assert_not_called()

    @pytest.mark.asyncio
    async def test_create_sync_with_run(
        self, mock_db, mock_user, mock_sync, mock_sync_job, mock_background_tasks
    ):
        """Test creating a sync and running it immediately."""
        # Arrange
        mock_uow_context = AsyncMock(spec=UnitOfWork)
        mock_uow = AsyncMock()
        mock_uow_context.__aenter__.return_value = mock_uow
        mock_uow.session = mock_db

        with patch("airweave.api.v1.endpoints.sync.UnitOfWork", return_value=mock_uow_context):
            sync_service.create = AsyncMock(return_value=mock_sync)
            crud.sync_job.create = AsyncMock(return_value=mock_sync_job)

            sync_in = schemas.SyncCreate(
                name="Test Sync",
                description="Test description",
                source_connection_id=uuid.uuid4(),
                destination_connection_ids=[uuid.uuid4()],
                run_immediately=True,
            )

            # Act
            result = await sync.create_sync(
                db=mock_db,
                sync_in=sync_in,
                user=mock_user,
                background_tasks=mock_background_tasks,
            )

            # Assert
            sync_service.create.assert_called_once()
            crud.sync_job.create.assert_called_once()
            mock_uow.commit.assert_called()
            mock_db.refresh.assert_called()
            assert result == mock_sync
            mock_background_tasks.add_task.assert_called_once()


class TestDeleteSync:
    """Tests for the delete_sync endpoint."""

    @pytest.mark.asyncio
    async def test_delete_sync_found(self, mock_db, mock_user, mock_sync):
        """Test deleting a sync that exists."""
        # Arrange
        crud.sync.get = AsyncMock(return_value=mock_sync)
        crud.sync.remove = AsyncMock(return_value=mock_sync)
        sync_id = mock_sync.id

        # Act
        result = await sync.delete_sync(
            db=mock_db, sync_id=sync_id, delete_data=False, user=mock_user
        )

        # Assert
        crud.sync.get.assert_called_once_with(db=mock_db, id=sync_id, current_user=mock_user)
        crud.sync.remove.assert_called_once_with(db=mock_db, id=sync_id, current_user=mock_user)
        assert result == mock_sync

    @pytest.mark.asyncio
    async def test_delete_sync_with_data(self, mock_db, mock_user, mock_sync):
        """Test deleting a sync with its data."""
        # Arrange
        crud.sync.get = AsyncMock(return_value=mock_sync)
        crud.sync.remove = AsyncMock(return_value=mock_sync)
        sync_id = mock_sync.id

        # Act
        result = await sync.delete_sync(
            db=mock_db, sync_id=sync_id, delete_data=True, user=mock_user
        )

        # Assert
        crud.sync.get.assert_called_once_with(db=mock_db, id=sync_id, current_user=mock_user)
        crud.sync.remove.assert_called_once_with(db=mock_db, id=sync_id, current_user=mock_user)
        assert result == mock_sync

    @pytest.mark.asyncio
    async def test_delete_sync_not_found(self, mock_db, mock_user):
        """Test deleting a sync that doesn't exist."""
        # Arrange
        crud.sync.get = AsyncMock(return_value=None)
        sync_id = uuid.uuid4()

        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            await sync.delete_sync(db=mock_db, sync_id=sync_id, delete_data=False, user=mock_user)

        assert exc_info.value.status_code == 404
        assert exc_info.value.detail == "Sync not found"


class TestRunSync:
    """Tests for the run_sync endpoint."""

    @pytest.mark.asyncio
    async def test_run_sync_found(
        self, mock_db, mock_user, mock_sync, mock_sync_job, mock_sync_dag, mock_background_tasks
    ):
        """Test running a sync that exists."""
        # Arrange
        crud.sync.get = AsyncMock(return_value=mock_sync)
        crud.sync_job.create = AsyncMock(return_value=mock_sync_job)
        crud.sync_dag.get_by_sync_id = AsyncMock(return_value=mock_sync_dag)
        sync_id = mock_sync.id

        # Act
        result = await sync.run_sync(
            db=mock_db,
            sync_id=sync_id,
            user=mock_user,
            background_tasks=mock_background_tasks,
        )

        # Assert
        crud.sync.get.assert_called_once_with(
            db=mock_db, id=sync_id, current_user=mock_user, with_connections=True
        )
        crud.sync_job.create.assert_called_once()
        mock_background_tasks.add_task.assert_called_once()
        assert result == mock_sync_job

    @pytest.mark.asyncio
    async def test_run_sync_not_found(self, mock_db, mock_user, mock_background_tasks):
        """Test running a sync that doesn't exist."""
        # Arrange
        crud.sync.get = AsyncMock(return_value=None)
        sync_id = uuid.uuid4()

        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            await sync.run_sync(
                db=mock_db,
                sync_id=sync_id,
                user=mock_user,
                background_tasks=mock_background_tasks,
            )

        assert exc_info.value.status_code == 404
        assert exc_info.value.detail == "Sync not found"


class TestListSyncJobs:
    """Tests for the list_sync_jobs endpoint."""

    @pytest.mark.asyncio
    async def test_list_sync_jobs_found(self, mock_db, mock_user, mock_sync, mock_sync_job):
        """Test listing jobs for a sync that exists."""
        # Arrange
        crud.sync.get = AsyncMock(return_value=mock_sync)
        crud.sync_job.get_all_by_sync_id = AsyncMock(return_value=[mock_sync_job])
        sync_id = mock_sync.id

        # Act
        result = await sync.list_sync_jobs(db=mock_db, sync_id=sync_id, user=mock_user)

        # Assert
        crud.sync.get.assert_called_once_with(db=mock_db, id=sync_id, current_user=mock_user)
        crud.sync_job.get_all_by_sync_id.assert_called_once_with(db=mock_db, sync_id=sync_id)
        assert result == [mock_sync_job]

    @pytest.mark.asyncio
    async def test_list_sync_jobs_sync_not_found(self, mock_db, mock_user):
        """Test listing jobs for a sync that doesn't exist."""
        # Arrange
        crud.sync.get = AsyncMock(return_value=None)
        sync_id = uuid.uuid4()

        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            await sync.list_sync_jobs(db=mock_db, sync_id=sync_id, user=mock_user)

        assert exc_info.value.status_code == 404
        assert exc_info.value.detail == "Sync not found"


class TestGetSyncJob:
    """Tests for the get_sync_job endpoint."""

    @pytest.mark.asyncio
    async def test_get_sync_job_found(self, mock_db, mock_user, mock_sync_job):
        """Test getting a sync job that exists."""
        # Arrange
        sync_id = uuid.uuid4()
        mock_sync_job.sync_id = sync_id
        crud.sync_job.get = AsyncMock(return_value=mock_sync_job)
        job_id = mock_sync_job.id

        # Act
        result = await sync.get_sync_job(db=mock_db, sync_id=sync_id, job_id=job_id, user=mock_user)

        # Assert
        crud.sync_job.get.assert_called_once_with(db=mock_db, id=job_id, current_user=mock_user)
        assert result == mock_sync_job

    @pytest.mark.asyncio
    async def test_get_sync_job_not_found(self, mock_db, mock_user):
        """Test getting a sync job that doesn't exist."""
        # Arrange
        crud.sync_job.get = AsyncMock(return_value=None)
        sync_id = uuid.uuid4()
        job_id = uuid.uuid4()

        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            await sync.get_sync_job(db=mock_db, sync_id=sync_id, job_id=job_id, user=mock_user)

        assert exc_info.value.status_code == 404
        assert exc_info.value.detail == "Sync job not found"

    @pytest.mark.asyncio
    async def test_get_sync_job_wrong_sync(self, mock_db, mock_user, mock_sync_job):
        """Test getting a sync job that belongs to a different sync."""
        # Arrange
        sync_id = uuid.uuid4()
        wrong_sync_id = uuid.uuid4()
        mock_sync_job.sync_id = wrong_sync_id
        crud.sync_job.get = AsyncMock(return_value=mock_sync_job)
        job_id = mock_sync_job.id

        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            await sync.get_sync_job(db=mock_db, sync_id=sync_id, job_id=job_id, user=mock_user)

        assert exc_info.value.status_code == 404
        assert exc_info.value.detail == "Sync job not found"


class TestSubscribeSyncJob:
    """Tests for the subscribe_sync_job endpoint."""

    @pytest.mark.asyncio
    async def test_subscribe_sync_job_found(self, mock_user):
        """Test subscribing to a sync job that exists."""
        # Arrange
        job_id = uuid.uuid4()
        mock_queue = asyncio.Queue()

        # Add a test message to the queue
        test_update = schemas.SyncJobUpdate(
            job_id=job_id,
            status=SyncJobStatus.IN_PROGRESS,
            progress=50,
            message="Test message",
        )
        await mock_queue.put(test_update)

        sync_pubsub.subscribe = AsyncMock(return_value=mock_queue)
        sync_pubsub.unsubscribe = MagicMock()

        # Create a properly authenticated mock request with token
        mock_request = MagicMock()
        mock_request.query_params.get.return_value = "test-token"

        # Temporarily disable auth requirement for testing
        with patch("airweave.api.v1.endpoints.sync.settings.AUTH_ENABLED", False):
            # Act
            response = await sync.subscribe_sync_job(job_id=job_id, request=mock_request)

            # Assert
            sync_pubsub.subscribe.assert_called_once_with(job_id)
            assert isinstance(response, StreamingResponse)
            assert response.media_type == "text/event-stream"
            assert response.headers["Cache-Control"] == "no-cache"
            assert response.headers["Connection"] == "keep-alive"
            assert response.headers["X-Accel-Buffering"] == "no"

    @pytest.mark.asyncio
    async def test_subscribe_sync_job_not_found(self, mock_user):
        """Test subscribing to a sync job that doesn't exist."""
        # Arrange
        job_id = uuid.uuid4()
        sync_pubsub.subscribe = AsyncMock(return_value=None)

        # Create a properly authenticated mock request with token
        mock_request = MagicMock()
        mock_request.query_params.get.return_value = "test-token"

        # Temporarily disable auth requirement for testing
        with patch("airweave.api.v1.endpoints.sync.settings.AUTH_ENABLED", False):
            # Act & Assert
            with pytest.raises(HTTPException) as exc_info:
                await sync.subscribe_sync_job(job_id=job_id, request=mock_request)

            assert exc_info.value.status_code == 404
            assert exc_info.value.detail == "Sync job not found or completed"
            sync_pubsub.subscribe.assert_called_once_with(job_id)


class TestGetSyncDag:
    """Tests for the get_sync_dag endpoint."""

    @pytest.mark.asyncio
    async def test_get_sync_dag_found(self, mock_db, mock_user, mock_sync_dag):
        """Test getting a sync DAG that exists."""
        # Arrange
        crud.sync_dag.get_by_sync_id = AsyncMock(return_value=mock_sync_dag)
        sync_id = mock_sync_dag.sync_id

        # Act
        result = await sync.get_sync_dag(sync_id=sync_id, db=mock_db, user=mock_user)

        # Assert
        crud.sync_dag.get_by_sync_id.assert_called_once_with(
            db=mock_db, sync_id=sync_id, current_user=mock_user
        )
        assert result == mock_sync_dag

    @pytest.mark.asyncio
    async def test_get_sync_dag_not_found(self, mock_db, mock_user):
        """Test getting a sync DAG that doesn't exist."""
        # Arrange
        crud.sync_dag.get_by_sync_id = AsyncMock(return_value=None)
        sync_id = uuid.uuid4()

        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            await sync.get_sync_dag(sync_id=sync_id, db=mock_db, user=mock_user)

        assert exc_info.value.status_code == 404
        assert exc_info.value.detail == f"DAG for sync {sync_id} not found"


class TestUpdateSync:
    """Tests for the update_sync endpoint."""

    @pytest.mark.asyncio
    async def test_update_sync_found(self, mock_db, mock_user, mock_sync):
        """Test updating a sync that exists."""
        # Arrange
        crud.sync.get = AsyncMock(return_value=mock_sync)
        crud.sync.update = AsyncMock(return_value=mock_sync)
        sync_id = mock_sync.id
        sync_update = schemas.SyncUpdate(name="Updated Sync")

        # Act
        result = await sync.update_sync(
            db=mock_db, sync_id=sync_id, sync_update=sync_update, user=mock_user
        )

        # Assert
        assert result == mock_sync

    @pytest.mark.asyncio
    async def test_update_sync_not_found(self, mock_db, mock_user):
        """Test updating a sync that doesn't exist."""
        # Arrange
        crud.sync.get = AsyncMock(return_value=None)
        sync_id = uuid.uuid4()
        sync_update = schemas.SyncUpdate(name="Updated Sync")

        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            await sync.update_sync(
                db=mock_db, sync_id=sync_id, sync_update=sync_update, user=mock_user
            )

        assert exc_info.value.status_code == 404
        assert exc_info.value.detail == "Sync not found"
