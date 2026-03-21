"""Unit tests for Linear source connector with continuous sync."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from airweave.platform.configs.config import LinearConfig
from airweave.platform.entities.linear import (
    LinearCommentEntity,
    LinearIssueEntity,
    LinearProjectEntity,
    LinearTeamEntity,
    LinearUserEntity,
    _parse_dt,
)
from airweave.platform.sources.linear import LinearSource


def _mock_auth(token="test-token"):
    auth = AsyncMock()
    auth.get_token = AsyncMock(return_value=token)
    auth.force_refresh = AsyncMock(return_value="refreshed-token")
    auth.supports_refresh = True
    auth.provider_kind = "oauth"
    return auth


def _mock_http_client():
    client = AsyncMock()
    client.get = AsyncMock()
    client.post = AsyncMock()
    return client


def _mock_logger():
    return MagicMock()


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
    """Create a Linear source instance via the v2 ``create()`` contract."""

    async def _create():
        return await LinearSource.create(
            auth=_mock_auth(),
            logger=_mock_logger(),
            http_client=_mock_http_client(),
            config=LinearConfig(),
        )

    return asyncio.run(_create())


# ---------------------------------------------------------------------------
# create
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_returns_instance():
    """create() should return a LinearSource with injected deps."""
    auth = _mock_auth()
    http = _mock_http_client()
    source = await LinearSource.create(
        auth=auth,
        logger=_mock_logger(),
        http_client=http,
        config=LinearConfig(),
    )
    assert isinstance(source, LinearSource)
    assert source.auth is auth
    assert source.http_client is http


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

    with patch.object(linear_source, "_post", new_callable=AsyncMock, side_effect=responses):
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
async def test_incremental_sync_passes_updated_filter(linear_source):
    """Incremental sync should include updatedAt filter in GraphQL queries."""
    mock_cursor = MagicMock()
    mock_cursor.data = {"last_synced_at": "2024-06-01T00:00:00Z"}

    captured_queries = []
    responses = [
        _graphql_response("teams", []),
        _graphql_response("projects", []),
        _graphql_response("users", []),
        _graphql_response("issues", []),
    ]

    async def capture_post(query):
        captured_queries.append(query)
        return responses[len(captured_queries) - 1]

    with patch.object(linear_source, "_post", side_effect=capture_post):
        async for _ in linear_source.generate_entities(cursor=mock_cursor):
            pass

    for query in captured_queries[:4]:
        assert "updatedAt" in query
        assert "2024-06-01T00:00:00Z" in query


@pytest.mark.asyncio
async def test_incremental_sync_updates_cursor(linear_source):
    """Incremental sync should update the cursor with the sync start timestamp."""
    mock_cursor = MagicMock()
    mock_cursor.data = {"last_synced_at": "2024-06-01T00:00:00Z"}

    responses = [
        _graphql_response("teams", []),
        _graphql_response("projects", []),
        _graphql_response("users", []),
        _graphql_response("issues", []),
    ]

    with patch.object(linear_source, "_post", new_callable=AsyncMock, side_effect=responses):
        async for _ in linear_source.generate_entities(cursor=mock_cursor):
            pass

    mock_cursor.update.assert_called_once()
    call_kwargs = mock_cursor.update.call_args[1]
    assert "last_synced_at" in call_kwargs
    assert call_kwargs["last_synced_at"].endswith("+00:00")


# ---------------------------------------------------------------------------
# parse datetime (entity helpers)
# ---------------------------------------------------------------------------


def test_parse_dt_valid():
    """_parse_dt parses ISO8601 timestamps."""
    dt = _parse_dt("2024-06-15T12:30:00Z")
    assert dt is not None
    assert dt.year == 2024
    assert dt.month == 6
    assert dt.day == 15


def test_parse_dt_none():
    """_parse_dt returns None for None/empty input."""
    assert _parse_dt(None) is None
    assert _parse_dt("") is None


def test_parse_dt_invalid():
    """_parse_dt returns None for invalid strings."""
    assert _parse_dt("not-a-date") is None
