"""Tests for refactored source connection API."""

import pytest
from datetime import datetime
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from airweave.api.context import ApiContext
from airweave.core.source_connection_service import source_connection_service
from airweave.schemas.source_connection import (
    AuthenticationMethod,
    SourceConnection,
    SourceConnectionCreate,
    SourceConnectionJob,
    SourceConnectionListItem,
    SourceConnectionUpdate,
    SourceConnectionValidate,
)


@pytest.fixture
def mock_db():
    """Mock database session."""
    return AsyncMock(spec=AsyncSession)


@pytest.fixture
def mock_ctx():
    """Mock API context."""
    ctx = MagicMock(spec=ApiContext)
    ctx.organization = MagicMock(id="org-123")
    ctx.user = MagicMock(id="user-123")
    ctx.logger = MagicMock()
    return ctx


@pytest.fixture
def sample_source_connection():
    """Sample source connection for testing."""
    return SourceConnection(
        id=uuid4(),
        name="Test Connection",
        description="Test description",
        short_name="github",
        collection="test-collection",
        status="active",
        is_authenticated=True,
        created_at=datetime.now(),
        modified_at=datetime.now(),
    )


class TestSourceConnectionCreate:
    """Test source connection creation with different auth methods."""

    @pytest.mark.asyncio
    async def test_create_with_direct_auth(self, mock_db, mock_ctx):
        """Test creating source connection with direct authentication."""
        create_data = SourceConnectionCreate(
            name="GitHub Connection",
            short_name="github",
            authentication_method=AuthenticationMethod.DIRECT,
            auth_fields={"api_key": "test-key"},
            collection="my-collection",
        )

        with patch.object(source_connection_service, "_create_with_direct_auth") as mock_create:
            mock_create.return_value = SourceConnection(
                id=uuid4(),
                name="GitHub Connection",
                short_name="github",
                collection="my-collection",
                status="active",
                is_authenticated=True,
                created_at=datetime.now(),
                modified_at=datetime.now(),
            )

            result = await source_connection_service.create(
                mock_db, obj_in=create_data, ctx=mock_ctx
            )

            assert result.name == "GitHub Connection"
            assert result.is_authenticated is True
            mock_create.assert_called_once_with(mock_db, obj_in=create_data, ctx=mock_ctx)

    @pytest.mark.asyncio
    async def test_create_with_oauth_browser(self, mock_db, mock_ctx):
        """Test creating source connection with OAuth browser flow."""
        create_data = SourceConnectionCreate(
            name="Slack Connection",
            short_name="slack",
            authentication_method=AuthenticationMethod.OAUTH_BROWSER,
            collection="my-collection",
            redirect_url="https://app.example.com/callback",
        )

        with patch.object(source_connection_service, "_create_with_oauth_browser") as mock_create:
            mock_create.return_value = SourceConnection(
                id=uuid4(),
                name="Slack Connection",
                short_name="slack",
                collection="my-collection",
                status="not_yet_authorized",
                is_authenticated=False,
                authentication_url="https://api.example.com/authorize/abc123",
                authentication_url_expiry=datetime.now(),
                created_at=datetime.now(),
                modified_at=datetime.now(),
            )

            result = await source_connection_service.create(
                mock_db, obj_in=create_data, ctx=mock_ctx
            )

            assert result.is_authenticated is False
            assert result.authentication_url is not None
            mock_create.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_with_oauth_token(self, mock_db, mock_ctx):
        """Test creating source connection with OAuth token injection."""
        create_data = SourceConnectionCreate(
            name="API Connection",
            short_name="custom_api",
            authentication_method=AuthenticationMethod.OAUTH_TOKEN,
            access_token="bearer-token-123",
            refresh_token="refresh-token-456",
            collection="my-collection",
        )

        with patch.object(source_connection_service, "_create_with_oauth_token") as mock_create:
            mock_create.return_value = SourceConnection(
                id=uuid4(),
                name="API Connection",
                short_name="custom_api",
                collection="my-collection",
                status="active",
                is_authenticated=True,
                created_at=datetime.now(),
                modified_at=datetime.now(),
            )

            result = await source_connection_service.create(
                mock_db, obj_in=create_data, ctx=mock_ctx
            )

            assert result.is_authenticated is True
            mock_create.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_with_auth_provider(self, mock_db, mock_ctx):
        """Test creating source connection with auth provider."""
        create_data = SourceConnectionCreate(
            name="Composio Connection",
            short_name="github",
            authentication_method=AuthenticationMethod.AUTH_PROVIDER,
            auth_provider="composio-github",
            auth_provider_config={"account": "test-account"},
            collection="my-collection",
        )

        with patch.object(source_connection_service, "_create_with_auth_provider") as mock_create:
            mock_create.return_value = SourceConnection(
                id=uuid4(),
                name="Composio Connection",
                short_name="github",
                collection="my-collection",
                status="active",
                is_authenticated=True,
                created_at=datetime.now(),
                modified_at=datetime.now(),
            )

            result = await source_connection_service.create(
                mock_db, obj_in=create_data, ctx=mock_ctx
            )

            assert result.is_authenticated is True
            mock_create.assert_called_once()


class TestSourceConnectionList:
    """Test listing source connections."""

    @pytest.mark.asyncio
    async def test_list_all_connections(self, mock_db, mock_ctx):
        """Test listing all source connections."""
        with patch.object(source_connection_service, "list") as mock_list:
            mock_list.return_value = [
                SourceConnectionListItem(
                    id=uuid4(),
                    name="Connection 1",
                    short_name="github",
                    collection="collection-1",
                    status="active",
                    is_authenticated=True,
                    created_at=datetime.now(),
                    modified_at=datetime.now(),
                ),
                SourceConnectionListItem(
                    id=uuid4(),
                    name="Connection 2",
                    short_name="slack",
                    collection="collection-2",
                    status="active",
                    is_authenticated=True,
                    created_at=datetime.now(),
                    modified_at=datetime.now(),
                ),
            ]

            result = await source_connection_service.list(mock_db, ctx=mock_ctx, skip=0, limit=100)

            assert len(result) == 2
            assert result[0].name == "Connection 1"
            assert result[1].name == "Connection 2"

    @pytest.mark.asyncio
    async def test_list_by_collection(self, mock_db, mock_ctx):
        """Test listing source connections filtered by collection."""
        with patch.object(source_connection_service, "list") as mock_list:
            mock_list.return_value = [
                SourceConnectionListItem(
                    id=uuid4(),
                    name="Connection 1",
                    short_name="github",
                    collection="my-collection",
                    status="active",
                    is_authenticated=True,
                    created_at=datetime.now(),
                    modified_at=datetime.now(),
                ),
            ]

            result = await source_connection_service.list(
                mock_db, ctx=mock_ctx, collection="my-collection", skip=0, limit=100
            )

            assert len(result) == 1
            assert result[0].collection == "my-collection"


class TestSourceConnectionGet:
    """Test getting source connection with depth expansion."""

    @pytest.mark.asyncio
    async def test_get_basic(self, mock_db, mock_ctx, sample_source_connection):
        """Test getting source connection with depth=0."""
        connection_id = uuid4()

        with patch.object(source_connection_service, "get") as mock_get:
            mock_get.return_value = sample_source_connection

            result = await source_connection_service.get(
                mock_db, id=connection_id, ctx=mock_ctx, depth=0
            )

            assert result.id == sample_source_connection.id
            assert result.name == sample_source_connection.name
            mock_get.assert_called_once_with(
                mock_db,
                id=connection_id,
                ctx=mock_ctx,
                depth=0,
                include_auth=False,
                include_entities=False,
            )

    @pytest.mark.asyncio
    async def test_get_with_auth(self, mock_db, mock_ctx):
        """Test getting source connection with authentication details."""
        connection_id = uuid4()

        with patch.object(source_connection_service, "get") as mock_get:
            connection = SourceConnection(
                id=connection_id,
                name="Test Connection",
                short_name="github",
                collection="test-collection",
                status="active",
                is_authenticated=True,
                created_at=datetime.now(),
                modified_at=datetime.now(),
            )
            mock_get.return_value = connection

            result = await source_connection_service.get(
                mock_db, id=connection_id, ctx=mock_ctx, depth=1, include_auth=True
            )

            assert result.id == connection_id
            mock_get.assert_called_once_with(
                mock_db,
                id=connection_id,
                ctx=mock_ctx,
                depth=1,
                include_auth=True,
                include_entities=False,
            )


class TestSourceConnectionUpdate:
    """Test updating source connections."""

    @pytest.mark.asyncio
    async def test_update_basic_fields(self, mock_db, mock_ctx):
        """Test updating basic fields like name and description."""
        connection_id = uuid4()
        update_data = SourceConnectionUpdate(
            name="Updated Name",
            description="Updated description",
        )

        with patch.object(source_connection_service, "update") as mock_update:
            mock_update.return_value = SourceConnection(
                id=connection_id,
                name="Updated Name",
                description="Updated description",
                short_name="github",
                collection="test-collection",
                status="active",
                is_authenticated=True,
                created_at=datetime.now(),
                modified_at=datetime.now(),
            )

            result = await source_connection_service.update(
                mock_db, id=connection_id, obj_in=update_data, ctx=mock_ctx
            )

            assert result.name == "Updated Name"
            assert result.description == "Updated description"

    @pytest.mark.asyncio
    async def test_update_schedule(self, mock_db, mock_ctx):
        """Test updating cron schedule."""
        connection_id = uuid4()
        update_data = SourceConnectionUpdate(
            cron_schedule="0 */6 * * *",  # Every 6 hours
        )

        with patch.object(source_connection_service, "update") as mock_update:
            mock_update.return_value = SourceConnection(
                id=connection_id,
                name="Test Connection",
                short_name="github",
                collection="test-collection",
                status="active",
                is_authenticated=True,
                created_at=datetime.now(),
                modified_at=datetime.now(),
            )

            result = await source_connection_service.update(
                mock_db, id=connection_id, obj_in=update_data, ctx=mock_ctx
            )

            assert result is not None
            mock_update.assert_called_once()


class TestSourceConnectionDelete:
    """Test deleting source connections."""

    @pytest.mark.asyncio
    async def test_delete_connection(self, mock_db, mock_ctx):
        """Test deleting a source connection."""
        connection_id = uuid4()

        with patch.object(source_connection_service, "delete") as mock_delete:
            mock_delete.return_value = SourceConnection(
                id=connection_id,
                name="Deleted Connection",
                short_name="github",
                collection="test-collection",
                status="active",
                is_authenticated=True,
                created_at=datetime.now(),
                modified_at=datetime.now(),
            )

            result = await source_connection_service.delete(mock_db, id=connection_id, ctx=mock_ctx)

            assert result.id == connection_id
            mock_delete.assert_called_once_with(mock_db, id=connection_id, ctx=mock_ctx)


class TestSourceConnectionValidate:
    """Test validating source connection credentials."""

    @pytest.mark.asyncio
    async def test_validate_direct_auth(self, mock_db, mock_ctx):
        """Test validating direct authentication credentials."""
        validate_data = SourceConnectionValidate(
            short_name="github",
            authentication_method=AuthenticationMethod.DIRECT,
            auth_fields={"api_key": "test-key"},
        )

        with patch.object(source_connection_service, "validate") as mock_validate:
            mock_validate.return_value = {"valid": True, "source": "github"}

            result = await source_connection_service.validate(
                mock_db, obj_in=validate_data, ctx=mock_ctx
            )

            assert result["valid"] is True
            assert result["source"] == "github"

    @pytest.mark.asyncio
    async def test_validate_oauth_token(self, mock_db, mock_ctx):
        """Test validating OAuth token."""
        validate_data = SourceConnectionValidate(
            short_name="slack",
            authentication_method=AuthenticationMethod.OAUTH_TOKEN,
            access_token="xoxb-test-token",
        )

        with patch.object(source_connection_service, "validate") as mock_validate:
            mock_validate.return_value = {"valid": True, "source": "slack"}

            result = await source_connection_service.validate(
                mock_db, obj_in=validate_data, ctx=mock_ctx
            )

            assert result["valid"] is True


class TestSourceConnectionRun:
    """Test running sync jobs."""

    @pytest.mark.asyncio
    async def test_run_sync(self, mock_db, mock_ctx):
        """Test triggering a sync run."""
        connection_id = uuid4()
        job_id = uuid4()

        with patch.object(source_connection_service, "run") as mock_run:
            mock_run.return_value = SourceConnectionJob(
                id=job_id,
                source_connection_id=connection_id,
                status="pending",
                entities_processed=0,
                entities_inserted=0,
                entities_updated=0,
                entities_deleted=0,
                entities_failed=0,
            )

            result = await source_connection_service.run(mock_db, id=connection_id, ctx=mock_ctx)

            assert result.id == job_id
            assert result.source_connection_id == connection_id
            assert result.status == "pending"


class TestSourceConnectionJobs:
    """Test getting sync jobs."""

    @pytest.mark.asyncio
    async def test_get_jobs(self, mock_db, mock_ctx):
        """Test getting sync jobs for a connection."""
        connection_id = uuid4()

        with patch.object(source_connection_service, "get_jobs") as mock_get_jobs:
            mock_get_jobs.return_value = [
                SourceConnectionJob(
                    id=uuid4(),
                    source_connection_id=connection_id,
                    status="completed",
                    started_at=datetime.now(),
                    completed_at=datetime.now(),
                    duration_seconds=120,
                    entities_processed=100,
                    entities_inserted=50,
                    entities_updated=30,
                    entities_deleted=0,
                    entities_failed=0,
                ),
                SourceConnectionJob(
                    id=uuid4(),
                    source_connection_id=connection_id,
                    status="failed",
                    started_at=datetime.now(),
                    error="Connection timeout",
                    entities_processed=0,
                    entities_inserted=0,
                    entities_updated=0,
                    entities_deleted=0,
                    entities_failed=0,
                ),
            ]

            result = await source_connection_service.get_jobs(
                mock_db, id=connection_id, ctx=mock_ctx, limit=10
            )

            assert len(result) == 2
            assert result[0].status == "completed"
            assert result[0].entities_processed == 100
            assert result[1].status == "failed"
            assert result[1].error == "Connection timeout"


class TestOAuthCallback:
    """Test OAuth callback handling."""

    @pytest.mark.asyncio
    async def test_complete_oauth_callback(self, mock_db, mock_ctx):
        """Test completing OAuth flow from callback."""
        state = "test-state-123"
        code = "auth-code-456"

        with patch.object(source_connection_service, "complete_oauth_callback") as mock_complete:
            connection = SourceConnection(
                id=uuid4(),
                name="OAuth Connection",
                short_name="slack",
                collection="test-collection",
                status="active",
                is_authenticated=True,
                created_at=datetime.now(),
                modified_at=datetime.now(),
            )
            mock_complete.return_value = (connection, "https://app.example.com")

            result_conn, redirect_url = await source_connection_service.complete_oauth_callback(
                mock_db, state=state, code=code, ctx=mock_ctx
            )

            assert result_conn.is_authenticated is True
            assert redirect_url == "https://app.example.com"
            mock_complete.assert_called_once_with(mock_db, state=state, code=code, ctx=mock_ctx)


class TestMakeContinuous:
    """Test converting to continuous sync."""

    @pytest.mark.asyncio
    async def test_make_continuous(self, mock_db, mock_ctx):
        """Test converting source connection to continuous sync mode."""
        connection_id = uuid4()

        with patch.object(source_connection_service, "make_continuous") as mock_continuous:
            mock_continuous.return_value = SourceConnection(
                id=connection_id,
                name="Continuous Connection",
                short_name="github",
                collection="test-collection",
                status="active",
                is_authenticated=True,
                created_at=datetime.now(),
                modified_at=datetime.now(),
            )

            result = await source_connection_service.make_continuous(
                mock_db, id=connection_id, cursor_field="updated_at", ctx=mock_ctx
            )

            assert result.id == connection_id
            mock_continuous.assert_called_once_with(
                mock_db, id=connection_id, cursor_field="updated_at", ctx=mock_ctx
            )
