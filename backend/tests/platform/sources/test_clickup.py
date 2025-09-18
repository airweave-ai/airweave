"""Tests for ClickUp source implementation."""

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest
import httpx

from airweave.platform.configs.auth import ClickUpAuthConfig
from airweave.platform.entities.clickup import (
    ClickUpCommentEntity,
    ClickUpListEntity,
    ClickUpSpaceEntity,
    ClickUpTaskEntity,
    ClickUpWorkspaceEntity,
)
from airweave.platform.sources.clickup import ClickUpSource


class TestClickUpSource:
    """Tests for the ClickUpSource connector."""

    @pytest.fixture
    def mock_credentials(self):
        """Create mock ClickUp credentials."""
        return ClickUpAuthConfig(access_token="cu_test_token_123")

    @pytest.fixture
    def clickup_source(self, mock_credentials):
        """Create a ClickUpSource instance for testing."""
        return ClickUpSource()

    @pytest.fixture
    async def configured_source(self, mock_credentials):
        """Create a configured ClickUpSource instance."""
        return await ClickUpSource.create(mock_credentials)

    @pytest.fixture
    def mock_workspace_data(self):
        """Mock workspace data from ClickUp API."""
        return {
            "id": "workspace_123",
            "name": "Test Workspace",
            "color": "#ff6b6b",
            "avatar": "https://example.com/avatar.png",
            "members": [
                {"id": "user_1", "username": "john_doe", "email": "john@example.com"}
            ]
        }

    @pytest.fixture
    def mock_space_data(self):
        """Mock space data from ClickUp API."""
        return {
            "id": "space_456",
            "name": "Development Space",
            "color": "#4ecdc4",
            "private": False,
            "avatar": "https://example.com/space_avatar.png",
            "multiple_assignees": True,
            "features": {"due_dates": {"enabled": True}},
            "members": [
                {"id": "user_1", "username": "john_doe"}
            ]
        }

    @pytest.fixture
    def mock_list_data(self):
        """Mock list data from ClickUp API."""
        return {
            "id": "list_789",
            "name": "Sprint Backlog",
            "content": "Tasks for current sprint",
            "orderindex": 1,
            "priority": {"priority": "high", "color": "#ff6b6b"},
            "assignee": {"id": "user_1", "username": "john_doe"},
            "task_count": 5,
            "due_date": "1640995200000",
            "due_date_time": True,
            "start_date": "1640908800000", 
            "start_date_time": True,
            "archived": False,
            "statuses": [
                {"status": "to do", "color": "#d3d3d3"},
                {"status": "in progress", "color": "#4ecdc4"}
            ]
        }

    @pytest.fixture
    def mock_task_data(self):
        """Mock task data from ClickUp API."""
        return {
            "id": "task_101112",
            "custom_id": "TASK-001",
            "name": "Implement user authentication",
            "description": "Add OAuth2 authentication to the application",
            "text_content": "Add OAuth2 authentication to the application",
            "status": {"status": "in progress", "color": "#4ecdc4"},
            "priority": {"priority": "high", "color": "#ff6b6b"},
            "assignees": [{"id": "user_1", "username": "john_doe"}],
            "watchers": [{"id": "user_2", "username": "jane_smith"}],
            "creator": {"id": "user_1", "username": "john_doe"},
            "date_created": "1640908800000",
            "date_updated": "1640995200000",
            "date_closed": None,
            "due_date": "1641081600000",
            "start_date": "1640908800000",
            "time_estimate": 7200000,  # 2 hours in milliseconds
            "time_spent": 3600000,     # 1 hour in milliseconds
            "orderindex": "1",
            "archived": False,
            "custom_fields": [
                {"id": "cf_1", "name": "Story Points", "value": "5"}
            ],
            "tags": [
                {"name": "backend", "tag_bg": "#ff6b6b"}
            ],
            "parent": None,
            "dependencies": [],
            "linked_tasks": [],
            "url": "https://app.clickup.com/t/task_101112"
        }

    @pytest.fixture
    def mock_comment_data(self):
        """Mock comment data from ClickUp API."""
        return {
            "id": "comment_131415",
            "comment_text": "This looks good, but we need to add error handling",
            "user": {"id": "user_2", "username": "jane_smith"},
            "date": "1640995200000",
            "type": "comment",
            "resolved": False,
            "parent": None,
            "replies": []
        }

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_create_instance(self, mock_credentials):
        """Test creating a ClickUpSource instance."""
        source = await ClickUpSource.create(mock_credentials)
        
        assert isinstance(source, ClickUpSource)
        assert source.access_token == "cu_test_token_123"

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_create_instance_with_config(self, mock_credentials):
        """Test creating a ClickUpSource instance with configuration."""
        config = {"some_setting": "value"}
        source = await ClickUpSource.create(mock_credentials, config)
        
        assert isinstance(source, ClickUpSource)
        assert source.access_token == "cu_test_token_123"

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_make_request_success(self, configured_source):
        """Test successful API request."""
        mock_response = {"teams": [{"id": "123", "name": "Test Team"}]}
        
        with patch("httpx.AsyncClient.get") as mock_get:
            mock_response_obj = MagicMock()
            mock_response_obj.json.return_value = mock_response
            mock_response_obj.raise_for_status.return_value = None
            mock_get.return_value = mock_response_obj
            
            async with httpx.AsyncClient() as client:
                result = await configured_source._make_request(client, "/team")
            
            assert result == mock_response
            mock_get.assert_called_once()
            
            # Verify headers
            call_args = mock_get.call_args
            headers = call_args[1]["headers"]
            assert headers["Authorization"] == "Bearer cu_test_token_123"
            assert headers["Content-Type"] == "application/json"

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_make_request_with_retry(self, configured_source):
        """Test API request with retry logic."""
        with patch("httpx.AsyncClient.get") as mock_get:
            # First call fails, second succeeds
            mock_response_obj = MagicMock()
            mock_response_obj.json.return_value = {"success": True}
            mock_response_obj.raise_for_status.side_effect = [
                httpx.HTTPStatusError("Server Error", request=MagicMock(), response=MagicMock()),
                None  # Second call succeeds
            ]
            mock_get.return_value = mock_response_obj
            
            async with httpx.AsyncClient() as client:
                result = await configured_source._make_request(client, "/team")
            
            assert result == {"success": True}
            assert mock_get.call_count == 2

    @pytest.mark.unit
    def test_create_workspace_entity(self, clickup_source, mock_workspace_data):
        """Test creating a workspace entity from API data."""
        entity = clickup_source._create_workspace_entity(mock_workspace_data)
        
        assert isinstance(entity, ClickUpWorkspaceEntity)
        assert entity.clickup_id == "workspace_123"
        assert entity.name == "Test Workspace"
        assert entity.color == "#ff6b6b"
        assert entity.avatar == "https://example.com/avatar.png"
        assert len(entity.members) == 1
        assert entity.members[0]["username"] == "john_doe"
        
        # Check breadcrumbs
        assert len(entity.breadcrumbs) == 1
        assert entity.breadcrumbs[0].name == "Test Workspace"
        assert entity.breadcrumbs[0].entity_id == "workspace_123"

    @pytest.mark.unit
    def test_create_space_entity(self, clickup_source, mock_space_data, mock_workspace_data):
        """Test creating a space entity from API data."""
        entity = clickup_source._create_space_entity(mock_space_data, mock_workspace_data)
        
        assert isinstance(entity, ClickUpSpaceEntity)
        assert entity.clickup_id == "space_456"
        assert entity.name == "Development Space"
        assert entity.workspace_id == "workspace_123"
        assert entity.workspace_name == "Test Workspace"
        assert entity.private is False
        assert entity.multiple_assignees is True
        
        # Check breadcrumbs
        assert len(entity.breadcrumbs) == 2
        assert entity.breadcrumbs[0].name == "Test Workspace"
        assert entity.breadcrumbs[1].name == "Development Space"

    @pytest.mark.unit
    def test_create_list_entity(self, clickup_source, mock_list_data, mock_space_data, mock_workspace_data):
        """Test creating a list entity from API data."""
        entity = clickup_source._create_list_entity(
            mock_list_data, None, mock_space_data, mock_workspace_data
        )
        
        assert isinstance(entity, ClickUpListEntity)
        assert entity.clickup_id == "list_789"
        assert entity.name == "Sprint Backlog"
        assert entity.content == "Tasks for current sprint"
        assert entity.folder_id is None  # Folderless list
        assert entity.space_id == "space_456"
        assert entity.workspace_id == "workspace_123"
        assert entity.task_count == 5
        assert entity.archived is False
        
        # Check breadcrumbs for folderless list
        assert len(entity.breadcrumbs) == 3
        assert entity.breadcrumbs[2].name == "Sprint Backlog"

    @pytest.mark.unit
    def test_create_task_entity(self, clickup_source, mock_task_data, mock_list_data, mock_space_data, mock_workspace_data):
        """Test creating a task entity from API data."""
        entity = clickup_source._create_task_entity(
            mock_task_data, mock_list_data, None, mock_space_data, mock_workspace_data
        )
        
        assert isinstance(entity, ClickUpTaskEntity)
        assert entity.clickup_id == "task_101112"
        assert entity.custom_id == "TASK-001"
        assert entity.name == "Implement user authentication"
        assert entity.description == "Add OAuth2 authentication to the application"
        assert entity.list_id == "list_789"
        assert entity.list_name == "Sprint Backlog"
        assert entity.folder_id is None
        assert entity.space_id == "space_456"
        assert entity.workspace_id == "workspace_123"
        
        # Check datetime handling
        assert entity.date_created is not None
        assert isinstance(entity.date_created, datetime)
        assert entity.date_updated is not None
        assert entity.date_closed is None
        
        # Check other fields
        assert len(entity.assignees) == 1
        assert len(entity.custom_fields) == 1
        assert len(entity.tags) == 1
        assert entity.time_estimate == 7200000
        assert entity.time_spent == 3600000
        assert entity.url == "https://app.clickup.com/t/task_101112"

    @pytest.mark.unit
    def test_create_comment_entity(self, clickup_source, mock_comment_data, mock_task_data, mock_list_data, mock_space_data, mock_workspace_data):
        """Test creating a comment entity from API data."""
        entity = clickup_source._create_comment_entity(
            mock_comment_data, mock_task_data, mock_list_data, mock_space_data, mock_workspace_data
        )
        
        assert isinstance(entity, ClickUpCommentEntity)
        assert entity.clickup_id == "comment_131415"
        assert entity.comment_text == "This looks good, but we need to add error handling"
        assert entity.task_id == "task_101112"
        assert entity.task_name == "Implement user authentication"
        assert entity.list_id == "list_789"
        assert entity.space_id == "space_456"
        assert entity.workspace_id == "workspace_123"
        assert entity.resolved is False
        assert entity.parent_comment_id is None
        
        # Check datetime handling
        assert entity.date is not None
        assert isinstance(entity.date, datetime)
        
        # Check user info
        assert entity.user["username"] == "jane_smith"
        
        # Check breadcrumbs
        assert len(entity.breadcrumbs) == 5
        assert entity.breadcrumbs[-1].name == "Comment comment_131415"

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_get_workspaces(self, configured_source):
        """Test fetching workspaces."""
        mock_response = {
            "teams": [
                {"id": "workspace_1", "name": "Workspace 1"},
                {"id": "workspace_2", "name": "Workspace 2"}
            ]
        }
        
        with patch.object(configured_source, "_make_request", return_value=mock_response) as mock_request:
            async with httpx.AsyncClient() as client:
                workspaces = await configured_source._get_workspaces(client)
            
            assert len(workspaces) == 2
            assert workspaces[0]["name"] == "Workspace 1"
            mock_request.assert_called_once_with(client, "/team")

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_get_spaces(self, configured_source):
        """Test fetching spaces for a workspace."""
        mock_response = {
            "spaces": [
                {"id": "space_1", "name": "Space 1"},
                {"id": "space_2", "name": "Space 2"}
            ]
        }
        
        with patch.object(configured_source, "_make_request", return_value=mock_response) as mock_request:
            async with httpx.AsyncClient() as client:
                spaces = await configured_source._get_spaces(client, "workspace_123")
            
            assert len(spaces) == 2
            assert spaces[0]["name"] == "Space 1"
            mock_request.assert_called_once_with(client, "/team/workspace_123/space")

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_get_lists_with_folder(self, configured_source):
        """Test fetching lists within a folder."""
        mock_response = {
            "lists": [
                {"id": "list_1", "name": "List 1"},
                {"id": "list_2", "name": "List 2"}
            ]
        }
        
        with patch.object(configured_source, "_make_request", return_value=mock_response) as mock_request:
            async with httpx.AsyncClient() as client:
                lists = await configured_source._get_lists(client, folder_id="folder_123")
            
            assert len(lists) == 2
            assert lists[0]["name"] == "List 1"
            mock_request.assert_called_once_with(client, "/folder/folder_123/list")

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_get_lists_folderless(self, configured_source):
        """Test fetching folderless lists within a space."""
        mock_response = {
            "lists": [
                {"id": "list_1", "name": "Folderless List 1"}
            ]
        }
        
        with patch.object(configured_source, "_make_request", return_value=mock_response) as mock_request:
            async with httpx.AsyncClient() as client:
                lists = await configured_source._get_lists(client, space_id="space_123")
            
            assert len(lists) == 1
            assert lists[0]["name"] == "Folderless List 1"
            mock_request.assert_called_once_with(client, "/space/space_123/list")

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_get_lists_invalid_params(self, configured_source):
        """Test that get_lists raises error with invalid parameters."""
        async with httpx.AsyncClient() as client:
            with pytest.raises(ValueError, match="Either folder_id or space_id must be provided"):
                await configured_source._get_lists(client)

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_get_tasks_with_pagination(self, configured_source):
        """Test fetching tasks with pagination."""
        mock_response = {
            "tasks": [
                {"id": "task_1", "name": "Task 1"},
                {"id": "task_2", "name": "Task 2"}
            ],
            "last_page": False
        }
        
        expected_params = {
            "archived": "false",
            "page": 0,
            "order_by": "created",
            "reverse": "true",
            "include_closed": "true"
        }
        
        with patch.object(configured_source, "_make_request", return_value=mock_response) as mock_request:
            async with httpx.AsyncClient() as client:
                response = await configured_source._get_tasks(client, "list_123", page=0)
            
            assert len(response["tasks"]) == 2
            assert response["last_page"] is False
            mock_request.assert_called_once_with(client, "/list/list_123/task", expected_params)

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_get_task_comments(self, configured_source):
        """Test fetching comments for a task."""
        mock_response = {
            "comments": [
                {"id": "comment_1", "comment_text": "First comment"},
                {"id": "comment_2", "comment_text": "Second comment"}
            ]
        }
        
        with patch.object(configured_source, "_make_request", return_value=mock_response) as mock_request:
            async with httpx.AsyncClient() as client:
                comments = await configured_source._get_task_comments(client, "task_123")
            
            assert len(comments) == 2
            assert comments[0]["comment_text"] == "First comment"
            mock_request.assert_called_once_with(client, "/task/task_123/comment")

    @pytest.mark.unit 
    def test_datetime_parsing_edge_cases(self, clickup_source):
        """Test datetime parsing with edge cases."""
        task_data = {
            "id": "task_test",
            "name": "Test Task",
            "date_created": "invalid_timestamp",  # Invalid timestamp
            "date_updated": None,  # None value
            "date_closed": "1640995200000"  # Valid timestamp
        }
        
        # Create minimal required data
        list_data = {"id": "list_1", "name": "Test List"}
        space_data = {"id": "space_1", "name": "Test Space"}
        workspace_data = {"id": "workspace_1", "name": "Test Workspace"}
        
        entity = clickup_source._create_task_entity(
            task_data, list_data, None, space_data, workspace_data
        )
        
        # Invalid timestamp should result in None
        assert entity.date_created is None
        assert entity.date_updated is None
        # Valid timestamp should parse correctly
        assert entity.date_closed is not None
        assert isinstance(entity.date_closed, datetime)

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_sync_method_structure(self, configured_source):
        """Test that sync method has correct structure and is async generator."""
        import inspect
        
        # Check that sync method exists and is async generator
        assert hasattr(configured_source, 'sync')
        sync_method = getattr(configured_source, 'sync')
        assert inspect.iscoroutinefunction(sync_method)
        
        # Check return annotation indicates AsyncGenerator
        sig = inspect.signature(sync_method)
        return_annotation = str(sig.return_annotation)
        assert 'AsyncGenerator' in return_annotation or 'typing.AsyncGenerator' in return_annotation

    @pytest.mark.unit
    def test_source_decorator_attributes(self):
        """Test that ClickUpSource has correct decorator attributes."""
        # Test that the source decorator has set the correct attributes
        assert hasattr(ClickUpSource, '_is_source')
        assert ClickUpSource._is_source is True
        assert hasattr(ClickUpSource, '_name')
        assert ClickUpSource._name == "ClickUp"
        assert hasattr(ClickUpSource, '_short_name')
        assert ClickUpSource._short_name == "clickup"
        assert hasattr(ClickUpSource, '_labels')
        assert "Project Management" in ClickUpSource._labels