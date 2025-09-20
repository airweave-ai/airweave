"""Unit tests for sync endpoints."""

import asyncio
import uuid
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException
from fastapi.responses import StreamingResponse

from airweave import crud, schemas
from airweave.api.v1.endpoints import sync
from airweave.core.shared_models import (
    ConnectionStatus,
    IntegrationType,
    SyncJobStatus,
    CollectionStatus,
    SourceConnectionStatus,
)
from airweave.core.sync_service import sync_service

# Fixtures are imported from tests/fixtures/common.py via conftest.py


class TestListSyncs:
    """Tests for the list_syncs endpoint."""

    @pytest.mark.asyncio
    async def test_list_syncs_without_source_connection(self, mock_db, mock_user, mock_sync):
        """Test listing syncs without source connection."""
        # Arrange
        with patch.object(sync_service, "list_syncs", new_callable=AsyncMock) as mock_list_syncs:
            mock_list_syncs.return_value = [mock_sync]

            # Act
            result = await sync.list_syncs(
                db=mock_db, skip=0, limit=100, with_source_connection=False, ctx=mock_user
            )

            # Assert
            mock_list_syncs.assert_called_once_with(
                db=mock_db, ctx=mock_user, skip=0, limit=100, with_source_connection=False
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

        with patch.object(sync_service, "list_syncs", new_callable=AsyncMock) as mock_list_syncs:
            mock_list_syncs.return_value = [mock_sync_with_source]

            # Act
            result = await sync.list_syncs(
                db=mock_db, skip=0, limit=100, with_source_connection=True, ctx=mock_user
            )

            # Assert
            mock_list_syncs.assert_called_once_with(
                db=mock_db, ctx=mock_user, skip=0, limit=100, with_source_connection=True
            )
            assert result == [mock_sync_with_source]


class TestGetSync:
    """Tests for the get_sync endpoint."""

    @pytest.mark.asyncio
    async def test_get_sync_found(self, mock_db, mock_user, mock_sync):
        """Test getting a sync that exists."""
        # Arrange
        with patch.object(sync_service, "get_sync", new_callable=AsyncMock) as mock_get_sync:
            mock_get_sync.return_value = mock_sync
            sync_id = mock_sync.id

            # Act
            result = await sync.get_sync(db=mock_db, sync_id=sync_id, ctx=mock_user)

            # Assert
            mock_get_sync.assert_called_once_with(db=mock_db, sync_id=sync_id, ctx=mock_user)
            assert result == mock_sync

    @pytest.mark.asyncio
    async def test_get_sync_not_found(self, mock_db, mock_user):
        """Test getting a sync that doesn't exist."""
        # Arrange
        sync_id = uuid.uuid4()
        with patch.object(sync_service, "get_sync", new_callable=AsyncMock) as mock_get_sync:
            mock_get_sync.side_effect = HTTPException(status_code=404, detail="Sync not found")

            # Act & Assert
            with pytest.raises(HTTPException) as exc_info:
                await sync.get_sync(db=mock_db, sync_id=sync_id, ctx=mock_user)

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
        source_connection_id = uuid.uuid4()
        collection_id = "test-collection"

        # Create a proper mock source connection with all required fields
        mock_source_connection = MagicMock()
        mock_source_connection.id = uuid.uuid4()
        mock_source_connection.name = "Test Source Connection"
        mock_source_connection.description = "Test description"
        mock_source_connection.short_name = "test-source"
        mock_source_connection.sync_id = uuid.uuid4()
        mock_source_connection.organization_id = uuid.uuid4()
        mock_source_connection.connection_id = uuid.uuid4()
        mock_source_connection.collection = collection_id
        mock_source_connection.readable_collection_id = collection_id
        mock_source_connection.created_by_email = "test@example.com"
        mock_source_connection.modified_by_email = "test@example.com"
        mock_source_connection.created_at = datetime.now()
        mock_source_connection.modified_at = datetime.now()
        mock_source_connection.status = SourceConnectionStatus.ACTIVE
        mock_source_connection.last_sync_job_status = None
        mock_source_connection.last_sync_job_id = None
        mock_source_connection.last_sync_job_error = None
        mock_source_connection.cron_schedule = None
        mock_source_connection.auth_fields = None
        mock_source_connection.config_fields = None

        # Create a proper mock collection object with all required fields
        mock_collection = MagicMock()
        mock_collection.id = uuid.uuid4()
        mock_collection.readable_id = collection_id
        mock_collection.name = "Test Collection"
        mock_collection.organization_id = uuid.uuid4()
        mock_collection.created_by_email = "test@example.com"
        mock_collection.modified_by_email = "test@example.com"
        mock_collection.created_at = datetime.now()
        mock_collection.modified_at = datetime.now()
        mock_collection.status = CollectionStatus.ACTIVE

        sync_in = schemas.SyncCreate(
            name="Test Sync",
            description="Test description",
            source_connection_id=source_connection_id,
            destination_connection_ids=[uuid.uuid4()],
            run_immediately=False,
        )

        with (
            patch.object(
                sync_service, "create_and_run_sync", new_callable=AsyncMock
            ) as mock_create_and_run,
            patch.object(
                crud.source_connection, "get", new_callable=AsyncMock
            ) as mock_get_source_conn,
            patch.object(
                crud.collection, "get_by_readable_id", new_callable=AsyncMock
            ) as mock_get_collection,
        ):
            mock_create_and_run.return_value = (mock_sync, None)  # No sync job created
            mock_get_source_conn.return_value = mock_source_connection
            mock_get_collection.return_value = mock_collection

            # Act
            result = await sync.create_sync(
                db=mock_db,
                sync_in=sync_in,
                ctx=mock_user,
                background_tasks=mock_background_tasks,
            )

            # Assert
            mock_create_and_run.assert_called_once_with(db=mock_db, sync_in=sync_in, ctx=mock_user)
            assert result == mock_sync
            mock_background_tasks.add_task.assert_not_called()

    @pytest.mark.asyncio
    async def test_create_sync_with_run(
        self, mock_db, mock_user, mock_sync, mock_sync_job, mock_background_tasks
    ):
        """Test creating a sync and running it immediately."""
        # Arrange
        source_connection_id = uuid.uuid4()
        collection_id = "test-collection"

        # Create a proper mock source connection with all required fields
        mock_source_connection = MagicMock()
        mock_source_connection.id = uuid.uuid4()
        mock_source_connection.name = "Test Source Connection"
        mock_source_connection.description = "Test description"
        mock_source_connection.short_name = "test-source"
        mock_source_connection.sync_id = uuid.uuid4()
        mock_source_connection.organization_id = uuid.uuid4()
        mock_source_connection.connection_id = uuid.uuid4()
        mock_source_connection.collection = collection_id
        mock_source_connection.readable_collection_id = collection_id
        mock_source_connection.created_by_email = "test@example.com"
        mock_source_connection.modified_by_email = "test@example.com"
        mock_source_connection.created_at = datetime.now()
        mock_source_connection.modified_at = datetime.now()
        mock_source_connection.status = SourceConnectionStatus.ACTIVE
        mock_source_connection.last_sync_job_status = None
        mock_source_connection.last_sync_job_id = None
        mock_source_connection.last_sync_job_error = None
        mock_source_connection.cron_schedule = None
        mock_source_connection.auth_fields = None
        mock_source_connection.config_fields = None

        # Create a proper mock collection object with all required fields
        mock_collection = MagicMock()
        mock_collection.id = uuid.uuid4()
        mock_collection.readable_id = collection_id
        mock_collection.name = "Test Collection"
        mock_collection.organization_id = uuid.uuid4()
        mock_collection.created_by_email = "test@example.com"
        mock_collection.modified_by_email = "test@example.com"
        mock_collection.created_at = datetime.now()
        mock_collection.modified_at = datetime.now()
        mock_collection.status = CollectionStatus.ACTIVE

        mock_sync_dag = MagicMock()

        sync_in = schemas.SyncCreate(
            name="Test Sync",
            description="Test description",
            source_connection_id=source_connection_id,
            destination_connection_ids=[uuid.uuid4()],
            run_immediately=True,
        )

        with (
            patch.object(
                sync_service, "create_and_run_sync", new_callable=AsyncMock
            ) as mock_create_and_run,
            patch.object(sync_service, "get_sync_dag", new_callable=AsyncMock) as mock_get_dag,
            patch.object(
                crud.source_connection, "get", new_callable=AsyncMock
            ) as mock_get_source_conn,
            patch.object(
                crud.collection, "get_by_readable_id", new_callable=AsyncMock
            ) as mock_get_collection,
        ):
            mock_create_and_run.return_value = (mock_sync, mock_sync_job)
            mock_get_dag.return_value = mock_sync_dag
            mock_get_source_conn.return_value = mock_source_connection
            mock_get_collection.return_value = mock_collection

            # Act
            result = await sync.create_sync(
                db=mock_db,
                sync_in=sync_in,
                ctx=mock_user,
                background_tasks=mock_background_tasks,
            )

            # Assert
            mock_create_and_run.assert_called_once_with(db=mock_db, sync_in=sync_in, ctx=mock_user)
            mock_get_dag.assert_called_once_with(db=mock_db, sync_id=mock_sync.id, ctx=mock_user)
            assert result == mock_sync
            mock_background_tasks.add_task.assert_called_once()


class TestDeleteSync:
    """Tests for the delete_sync endpoint."""

    @pytest.mark.asyncio
    async def test_delete_sync_found(self, mock_db, mock_user, mock_sync):
        """Test deleting a sync that exists."""
        # Arrange
        sync_id = mock_sync.id
        with patch.object(sync_service, "delete_sync", new_callable=AsyncMock) as mock_delete_sync:
            mock_delete_sync.return_value = mock_sync

            # Act
            result = await sync.delete_sync(
                db=mock_db, sync_id=sync_id, delete_data=False, ctx=mock_user
            )

            # Assert
            mock_delete_sync.assert_called_once_with(
                db=mock_db, sync_id=sync_id, ctx=mock_user, delete_data=False
            )
            assert result == mock_sync

    @pytest.mark.asyncio
    async def test_delete_sync_with_data(self, mock_db, mock_user, mock_sync):
        """Test deleting a sync with its data."""
        # Arrange
        sync_id = mock_sync.id
        with patch.object(sync_service, "delete_sync", new_callable=AsyncMock) as mock_delete_sync:
            mock_delete_sync.return_value = mock_sync

            # Act
            result = await sync.delete_sync(
                db=mock_db, sync_id=sync_id, delete_data=True, ctx=mock_user
            )

            # Assert
            mock_delete_sync.assert_called_once_with(
                db=mock_db, sync_id=sync_id, ctx=mock_user, delete_data=True
            )
            assert result == mock_sync

    @pytest.mark.asyncio
    async def test_delete_sync_not_found(self, mock_db, mock_user):
        """Test deleting a sync that doesn't exist."""
        # Arrange
        sync_id = uuid.uuid4()
        with patch.object(sync_service, "delete_sync", new_callable=AsyncMock) as mock_delete_sync:
            mock_delete_sync.side_effect = HTTPException(status_code=404, detail="Sync not found")

            # Act & Assert
            with pytest.raises(HTTPException) as exc_info:
                await sync.delete_sync(
                    db=mock_db, sync_id=sync_id, delete_data=False, ctx=mock_user
                )

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
        sync_id = mock_sync.id
        with patch.object(
            sync_service, "trigger_sync_run", new_callable=AsyncMock
        ) as mock_trigger_run:
            mock_trigger_run.return_value = (mock_sync, mock_sync_job, mock_sync_dag)

            # Act
            result = await sync.run_sync(
                db=mock_db,
                sync_id=sync_id,
                ctx=mock_user,
                background_tasks=mock_background_tasks,
            )

            # Assert
            mock_trigger_run.assert_called_once_with(db=mock_db, sync_id=sync_id, ctx=mock_user)
            mock_background_tasks.add_task.assert_called_once()
            assert result == mock_sync_job

    @pytest.mark.asyncio
    async def test_run_sync_not_found(self, mock_db, mock_user, mock_background_tasks):
        """Test running a sync that doesn't exist."""
        # Arrange
        sync_id = uuid.uuid4()
        with patch.object(
            sync_service, "trigger_sync_run", new_callable=AsyncMock
        ) as mock_trigger_run:
            mock_trigger_run.side_effect = HTTPException(status_code=404, detail="Sync not found")

            # Act & Assert
            with pytest.raises(HTTPException) as exc_info:
                await sync.run_sync(
                    db=mock_db,
                    sync_id=sync_id,
                    ctx=mock_user,
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
        sync_id = mock_sync.id
        with patch.object(sync_service, "list_sync_jobs", new_callable=AsyncMock) as mock_list_jobs:
            mock_list_jobs.return_value = [mock_sync_job]

            # Act
            result = await sync.list_sync_jobs(db=mock_db, sync_id=sync_id, ctx=mock_user)

            # Assert
            mock_list_jobs.assert_called_once_with(db=mock_db, ctx=mock_user, sync_id=sync_id)
            assert result == [mock_sync_job]

    @pytest.mark.asyncio
    async def test_list_sync_jobs_sync_not_found(self, mock_db, mock_user):
        """Test listing jobs for a sync that doesn't exist."""
        # Arrange
        sync_id = uuid.uuid4()
        with patch.object(sync_service, "list_sync_jobs", new_callable=AsyncMock) as mock_list_jobs:
            mock_list_jobs.side_effect = HTTPException(status_code=404, detail="Sync not found")

            # Act & Assert
            with pytest.raises(HTTPException) as exc_info:
                await sync.list_sync_jobs(db=mock_db, sync_id=sync_id, ctx=mock_user)

            assert exc_info.value.status_code == 404
            assert exc_info.value.detail == "Sync not found"


class TestGetSyncJob:
    """Tests for the get_sync_job endpoint."""

    @pytest.mark.asyncio
    async def test_get_sync_job_found(self, mock_db, mock_user, mock_sync_job):
        """Test getting a sync job that exists."""
        # Arrange
        sync_id = uuid.uuid4()
        job_id = mock_sync_job.id
        mock_sync_job.sync_id = sync_id

        with patch.object(sync_service, "get_sync_job", new_callable=AsyncMock) as mock_get_job:
            mock_get_job.return_value = mock_sync_job

            # Act
            result = await sync.get_sync_job(
                db=mock_db, sync_id=sync_id, job_id=job_id, ctx=mock_user
            )

            # Assert
            mock_get_job.assert_called_once_with(
                db=mock_db, job_id=job_id, ctx=mock_user, sync_id=sync_id
            )
            assert result == mock_sync_job

    @pytest.mark.asyncio
    async def test_get_sync_job_not_found(self, mock_db, mock_user):
        """Test getting a sync job that doesn't exist."""
        # Arrange
        sync_id = uuid.uuid4()
        job_id = uuid.uuid4()

        with patch.object(sync_service, "get_sync_job", new_callable=AsyncMock) as mock_get_job:
            mock_get_job.side_effect = HTTPException(status_code=404, detail="Sync job not found")

            # Act & Assert
            with pytest.raises(HTTPException) as exc_info:
                await sync.get_sync_job(db=mock_db, sync_id=sync_id, job_id=job_id, ctx=mock_user)

            assert exc_info.value.status_code == 404
            assert exc_info.value.detail == "Sync job not found"

    @pytest.mark.asyncio
    async def test_get_sync_job_wrong_sync(self, mock_db, mock_user, mock_sync_job):
        """Test getting a sync job that belongs to a different sync."""
        # Arrange
        sync_id = uuid.uuid4()
        job_id = mock_sync_job.id

        with patch.object(sync_service, "get_sync_job", new_callable=AsyncMock) as mock_get_job:
            mock_get_job.side_effect = HTTPException(status_code=404, detail="Sync job not found")

            # Act & Assert
            with pytest.raises(HTTPException) as exc_info:
                await sync.get_sync_job(db=mock_db, sync_id=sync_id, job_id=job_id, ctx=mock_user)

            assert exc_info.value.status_code == 404
            assert exc_info.value.detail == "Sync job not found"


class TestSubscribeSyncJob:
    """Tests for the subscribe_sync_job endpoint."""

    @pytest.mark.asyncio
    async def test_subscribe_sync_job_found(self, mock_db, mock_user):
        """Test subscribing to a sync job that exists."""
        # Arrange
        job_id = uuid.uuid4()

        # Create a mock Redis PubSub instance
        mock_pubsub = AsyncMock()

        # Create an async generator for listen()
        async def mock_listen():
            # First yield a subscribe message
            yield {"type": "subscribe", "data": None}
            # Then yield a data message
            test_update = schemas.SyncJobUpdate(
                job_id=job_id,
                status=SyncJobStatus.IN_PROGRESS,
                progress=50,
                message="Test message",
            )
            yield {"type": "message", "data": test_update.model_dump_json()}
            # Stop iteration after these messages

        mock_pubsub.listen = mock_listen
        mock_pubsub.close = AsyncMock()

        with patch(
            "airweave.core.pubsub.core_pubsub.subscribe", new_callable=AsyncMock
        ) as mock_subscribe:
            mock_subscribe.return_value = mock_pubsub

            # Act - Use new signature with ctx dependency injection
            response = await sync.subscribe_sync_job(job_id=job_id, ctx=mock_user)

            # Assert
            mock_subscribe.assert_called_once_with("sync_job", job_id)
            assert isinstance(response, StreamingResponse)
            assert response.media_type == "text/event-stream"
            assert response.headers["Cache-Control"] == "no-cache, no-transform"
            assert response.headers["Connection"] == "keep-alive"
            assert response.headers["X-Accel-Buffering"] == "no"

    @pytest.mark.asyncio
    async def test_subscribe_sync_job_not_found(self, mock_db, mock_user):
        """Test subscribing to a sync job that doesn't exist.

        Note: The current implementation doesn't validate job existence,
        it will create a subscription that waits for messages that may never come.
        """
        # Arrange
        job_id = uuid.uuid4()

        # Create a mock Redis PubSub instance for non-existent job
        mock_pubsub = AsyncMock()

        # Create an async generator that only yields subscription confirmation
        async def mock_listen():
            # Only yield a subscribe message, no data will come
            yield {"type": "subscribe", "data": None}
            # In real scenario, this would wait forever for messages

        mock_pubsub.listen = mock_listen
        mock_pubsub.close = AsyncMock()

        with patch(
            "airweave.core.pubsub.core_pubsub.subscribe", new_callable=AsyncMock
        ) as mock_subscribe:
            # Subscribe will always return a pubsub instance
            mock_subscribe.return_value = mock_pubsub

            # Act - Use new signature with ctx dependency injection
            response = await sync.subscribe_sync_job(job_id=job_id, ctx=mock_user)

            # Assert - it creates a streaming response even for non-existent jobs
            mock_subscribe.assert_called_once_with("sync_job", job_id)
            assert isinstance(response, StreamingResponse)
            assert response.media_type == "text/event-stream"


class TestGetSyncDag:
    """Tests for the get_sync_dag endpoint."""

    @pytest.mark.asyncio
    async def test_get_sync_dag_found(self, mock_db, mock_user, mock_sync_dag):
        """Test getting a sync DAG that exists."""
        # Arrange
        sync_id = mock_sync_dag.sync_id
        with patch.object(sync_service, "get_sync_dag", new_callable=AsyncMock) as mock_get_dag:
            mock_get_dag.return_value = mock_sync_dag

            # Act
            result = await sync.get_sync_dag(sync_id=sync_id, db=mock_db, ctx=mock_user)

            # Assert
            mock_get_dag.assert_called_once_with(db=mock_db, sync_id=sync_id, ctx=mock_user)
            assert result == mock_sync_dag

    @pytest.mark.asyncio
    async def test_get_sync_dag_not_found(self, mock_db, mock_user):
        """Test getting a sync DAG that doesn't exist."""
        # Arrange
        sync_id = uuid.uuid4()
        with patch.object(sync_service, "get_sync_dag", new_callable=AsyncMock) as mock_get_dag:
            mock_get_dag.side_effect = HTTPException(
                status_code=404, detail=f"DAG for sync {sync_id} not found"
            )

            # Act & Assert
            with pytest.raises(HTTPException) as exc_info:
                await sync.get_sync_dag(sync_id=sync_id, db=mock_db, ctx=mock_user)

            assert exc_info.value.status_code == 404
            assert exc_info.value.detail == f"DAG for sync {sync_id} not found"


class TestUpdateSync:
    """Tests for the update_sync endpoint."""

    @pytest.mark.asyncio
    async def test_update_sync_found(self, mock_db, mock_user, mock_sync):
        """Test updating a sync that exists."""
        # Arrange
        sync_id = mock_sync.id
        sync_update = schemas.SyncUpdate(name="Updated Sync")

        with patch.object(sync_service, "update_sync", new_callable=AsyncMock) as mock_update_sync:
            mock_update_sync.return_value = mock_sync

            # Act
            result = await sync.update_sync(
                db=mock_db, sync_id=sync_id, sync_update=sync_update, ctx=mock_user
            )

            # Assert
            mock_update_sync.assert_called_once_with(
                db=mock_db, sync_id=sync_id, sync_update=sync_update, ctx=mock_user
            )
            assert result == mock_sync

    @pytest.mark.asyncio
    async def test_update_sync_not_found(self, mock_db, mock_user):
        """Test updating a sync that doesn't exist."""
        # Arrange
        sync_id = uuid.uuid4()
        sync_update = schemas.SyncUpdate(name="Updated Sync")

        with patch.object(sync_service, "update_sync", new_callable=AsyncMock) as mock_update_sync:
            mock_update_sync.side_effect = HTTPException(status_code=404, detail="Sync not found")

            # Act & Assert
            with pytest.raises(HTTPException) as exc_info:
                await sync.update_sync(
                    db=mock_db, sync_id=sync_id, sync_update=sync_update, ctx=mock_user
                )

            assert exc_info.value.status_code == 404
            assert exc_info.value.detail == "Sync not found"
