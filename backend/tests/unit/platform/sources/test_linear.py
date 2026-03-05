"""Unit tests for Linear source connector with continuous sync."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock

from airweave.platform.entities.linear import (
    LinearCommentEntity,
    LinearIssueEntity,
    LinearProjectEntity,
    LinearTeamEntity,
    LinearUserEntity,
)
from airweave.platform.sources.linear import LinearSource


def _graphql_response(collection_key: str, nodes: list, has_next_page: bool = False):
    """Build a mock Linear GraphQL response."""
    return {
        "data": {
            collection_key: {
                "nodes": nodes,
                "pageInfo": {"hasNextPage": has_next_page, "endCursor": "cursor-1"},
            }
        }
    }


TEAM_NODE = {
    "id": "team-1",
    "name": "Engineering",
    "key": "ENG",
    "description": "The engineering team",
    "color": "#00f",
    "icon": None,
    "private": False,
    "timezone": "UTC",
    "createdAt": "2024-01-01T00:00:00Z",
    "updatedAt": "2024-06-01T00:00:00Z",
    "parent": None,
    "issueCount": 42,
}

PROJECT_NODE = {
    "id": "proj-1",
    "name": "Q1 Launch",
    "slugId": "q1-launch",
    "description": "Q1 launch project",
    "priority": 1,
    "startDate": "2024-01-01",
    "targetDate": "2024-03-31",
    "state": "started",
    "createdAt": "2024-01-01T00:00:00Z",
    "updatedAt": "2024-06-01T00:00:00Z",
    "completedAt": None,
    "startedAt": "2024-01-01T00:00:00Z",
    "progress": 0.5,
    "teams": {"nodes": [{"id": "team-1", "name": "Engineering"}]},
    "lead": {"name": "Alice"},
}

USER_NODE = {
    "id": "user-1",
    "name": "Alice",
    "displayName": "alice",
    "email": "alice@example.com",
    "avatarUrl": None,
    "description": None,
    "timezone": "UTC",
    "active": True,
    "admin": False,
    "guest": False,
    "lastSeen": "2024-06-01T00:00:00Z",
    "statusEmoji": None,
    "statusLabel": None,
    "statusUntilAt": None,
    "createdIssueCount": 10,
    "createdAt": "2024-01-01T00:00:00Z",
    "updatedAt": "2024-06-01T00:00:00Z",
    "teams": {"nodes": [{"id": "team-1", "name": "Engineering", "key": "ENG"}]},
}

ISSUE_NODE = {
    "id": "issue-1",
    "identifier": "ENG-123",
    "title": "Fix the bug",
    "description": "There is a bug that needs fixing.",
    "priority": 2,
    "completedAt": None,
    "createdAt": "2024-03-01T00:00:00Z",
    "updatedAt": "2024-06-15T00:00:00Z",
    "dueDate": "2024-07-01",
    "archivedAt": None,
    "state": {"name": "In Progress"},
    "team": {"id": "team-1", "name": "Engineering"},
    "project": {"id": "proj-1", "name": "Q1 Launch"},
    "assignee": {"name": "Alice"},
    "comments": {
        "nodes": [
            {
                "id": "comment-1",
                "body": "Working on this now.",
                "createdAt": "2024-03-02T00:00:00Z",
                "updatedAt": "2024-03-02T00:00:00Z",
                "user": {"id": "user-1", "name": "Alice"},
            }
        ]
    },
}


@pytest.fixture
def linear_source():
    """Create a Linear source instance with test credentials."""
    source = LinearSource()
    source.access_token = "test-token"
    source.exclude_path = ""
    return source


@pytest.fixture
def linear_source_with_cursor(linear_source):
    """Linear source with a cursor set for incremental sync."""
    mock_cursor = MagicMock()
    mock_cursor.data = {"last_synced_at": "2024-06-01T00:00:00Z"}
    linear_source.set_cursor(mock_cursor)
    return linear_source


# ---------------------------------------------------------------------------
# create / validate
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_sets_config():
    """create() should set access_token and exclude_path from config."""
    source = await LinearSource.create("my-token", {"exclude_path": "TEAM-"})
    assert source.access_token == "my-token"
    assert source.exclude_path == "TEAM-"


@pytest.mark.asyncio
async def test_create_empty_config():
    """create() with no config should set empty exclude_path."""
    source = await LinearSource.create("token", None)
    assert source.exclude_path == ""


# ---------------------------------------------------------------------------
# cursor helper
# ---------------------------------------------------------------------------


def test_get_last_synced_at_no_cursor(linear_source):
    """_get_last_synced_at returns None when no cursor is set."""
    assert linear_source._get_last_synced_at() is None


def test_get_last_synced_at_empty_cursor(linear_source):
    """_get_last_synced_at returns None when cursor has empty last_synced_at."""
    mock_cursor = MagicMock()
    mock_cursor.data = {"last_synced_at": ""}
    linear_source.set_cursor(mock_cursor)
    assert linear_source._get_last_synced_at() is None


def test_get_last_synced_at_with_value(linear_source_with_cursor):
    """_get_last_synced_at returns the stored timestamp."""
    assert linear_source_with_cursor._get_last_synced_at() == "2024-06-01T00:00:00Z"


# ---------------------------------------------------------------------------
# full sync (no cursor)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_full_sync_generates_all_entity_types(linear_source):
    """On first sync (no cursor), generate_entities yields teams, projects, users, issues, comments."""
    responses = [
        _graphql_response("teams", [TEAM_NODE]),
        _graphql_response("projects", [PROJECT_NODE]),
        _graphql_response("users", [USER_NODE]),
        _graphql_response("issues", [ISSUE_NODE]),
    ]

    with patch.object(
        linear_source, "_post_with_auth", new_callable=AsyncMock, side_effect=responses
    ), patch.object(linear_source, "http_client") as mock_ctx:
        mock_client = MagicMock()
        mock_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_ctx.return_value.__aexit__ = AsyncMock(return_value=None)

        entities = []
        async for e in linear_source.generate_entities():
            entities.append(e)

    teams = [e for e in entities if isinstance(e, LinearTeamEntity)]
    projects = [e for e in entities if isinstance(e, LinearProjectEntity)]
    users = [e for e in entities if isinstance(e, LinearUserEntity)]
    issues = [e for e in entities if isinstance(e, LinearIssueEntity)]
    comments = [e for e in entities if isinstance(e, LinearCommentEntity)]

    assert len(teams) == 1
    assert teams[0].team_id == "team-1"
    assert len(projects) == 1
    assert projects[0].project_id == "proj-1"
    assert len(users) == 1
    assert users[0].user_id == "user-1"
    assert len(issues) == 1
    assert issues[0].issue_id == "issue-1"
    assert issues[0].identifier == "ENG-123"
    assert len(comments) == 1
    assert comments[0].comment_id == "comment-1"


# ---------------------------------------------------------------------------
# incremental sync (with cursor)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_incremental_sync_passes_updated_filter(linear_source_with_cursor):
    """Incremental sync should include updatedAt filter in GraphQL queries."""
    captured_queries = []
    original_post = AsyncMock(
        side_effect=[
            _graphql_response("teams", []),
            _graphql_response("projects", []),
            _graphql_response("users", []),
            _graphql_response("issues", []),
        ]
    )

    async def capture_post(client, query):
        captured_queries.append(query)
        return await original_post(client, query)

    with patch.object(
        linear_source_with_cursor, "_post_with_auth", side_effect=capture_post
    ), patch.object(linear_source_with_cursor, "http_client") as mock_ctx:
        mock_client = MagicMock()
        mock_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_ctx.return_value.__aexit__ = AsyncMock(return_value=None)

        async for _ in linear_source_with_cursor.generate_entities():
            pass

    # All entity queries (teams, projects, users, issues) should contain updatedAt filter
    for query in captured_queries[:4]:
        assert "updatedAt" in query
        assert "2024-06-01T00:00:00Z" in query


@pytest.mark.asyncio
async def test_incremental_sync_updates_cursor(linear_source_with_cursor):
    """Incremental sync should update the cursor with the sync start timestamp."""
    responses = [
        _graphql_response("teams", []),
        _graphql_response("projects", []),
        _graphql_response("users", []),
        _graphql_response("issues", []),
    ]

    with patch.object(
        linear_source_with_cursor, "_post_with_auth", new_callable=AsyncMock, side_effect=responses
    ), patch.object(linear_source_with_cursor, "http_client") as mock_ctx:
        mock_client = MagicMock()
        mock_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_ctx.return_value.__aexit__ = AsyncMock(return_value=None)

        async for _ in linear_source_with_cursor.generate_entities():
            pass

    linear_source_with_cursor.cursor.update.assert_called_once()
    call_kwargs = linear_source_with_cursor.cursor.update.call_args[1]
    assert "last_synced_at" in call_kwargs
    assert call_kwargs["last_synced_at"].endswith("+00:00")


# ---------------------------------------------------------------------------
# exclude_path filtering
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_exclude_path_skips_matching_issues(linear_source):
    """Issues matching exclude_path should be skipped."""
    linear_source.exclude_path = "ENG-"

    responses = [
        _graphql_response("teams", []),
        _graphql_response("projects", []),
        _graphql_response("users", []),
        _graphql_response("issues", [ISSUE_NODE]),
    ]

    with patch.object(
        linear_source, "_post_with_auth", new_callable=AsyncMock, side_effect=responses
    ), patch.object(linear_source, "http_client") as mock_ctx:
        mock_client = MagicMock()
        mock_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_ctx.return_value.__aexit__ = AsyncMock(return_value=None)

        entities = []
        async for e in linear_source.generate_entities():
            entities.append(e)

    issues = [e for e in entities if isinstance(e, LinearIssueEntity)]
    assert len(issues) == 0


# ---------------------------------------------------------------------------
# parse_datetime
# ---------------------------------------------------------------------------


def test_parse_datetime_valid(linear_source):
    """_parse_datetime parses ISO8601 timestamps."""
    dt = LinearSource._parse_datetime("2024-06-15T12:30:00Z")
    assert dt is not None
    assert dt.year == 2024
    assert dt.month == 6
    assert dt.day == 15


def test_parse_datetime_none():
    """_parse_datetime returns None for None/empty input."""
    assert LinearSource._parse_datetime(None) is None
    assert LinearSource._parse_datetime("") is None


def test_parse_datetime_invalid():
    """_parse_datetime returns None for invalid strings."""
    assert LinearSource._parse_datetime("not-a-date") is None
