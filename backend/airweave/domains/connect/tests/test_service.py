"""Table-driven unit tests for ConnectService.

Covers mode enforcement, integration filtering, collection scoping,
and all CRUD operations across the session mode matrix.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List, Optional
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException

from airweave import schemas
from airweave.api.context import ConnectContext
from airweave.domains.connect.service import ConnectService
from airweave.domains.connect.types import MODES_CREATE, MODES_DELETE, MODES_VIEW
from airweave.schemas.connect_session import ConnectSessionMode

from .conftest import COLLECTION_ID, ORG_ID, SESSION_ID, make_session

NOW = datetime.now(timezone.utc)
CONN_ID = uuid4()
SYNC_ID = uuid4()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_connection_list_item(
    short_name: str = "slack",
    collection_id: str = COLLECTION_ID,
) -> schemas.SourceConnectionListItem:
    return schemas.SourceConnectionListItem(
        id=CONN_ID,
        name="Test Connection",
        short_name=short_name,
        readable_collection_id=collection_id,
        created_at=NOW,
        modified_at=NOW,
        is_authenticated=True,
        entity_count=10,
    )


def _make_connection_response(
    short_name: str = "slack",
    collection_id: str = COLLECTION_ID,
    sync_id: Optional[UUID] = SYNC_ID,
) -> MagicMock:
    conn = MagicMock(spec=schemas.SourceConnection)
    conn.id = CONN_ID
    conn.short_name = short_name
    conn.readable_collection_id = collection_id
    conn.sync_id = sync_id
    return conn


# ===========================================================================
# Guard method tests (static methods on ConnectService)
# ===========================================================================


class TestCheckMode:
    """ConnectService._check_mode — session mode enforcement."""

    @dataclass
    class Case:
        id: str
        mode: ConnectSessionMode
        allowed_modes: frozenset
        should_pass: bool

    CASES = [
        Case("all-can-view", ConnectSessionMode.ALL, MODES_VIEW, True),
        Case("all-can-create", ConnectSessionMode.ALL, MODES_CREATE, True),
        Case("all-can-delete", ConnectSessionMode.ALL, MODES_DELETE, True),
        Case("connect-can-create", ConnectSessionMode.CONNECT, MODES_CREATE, True),
        Case("connect-cannot-view", ConnectSessionMode.CONNECT, MODES_VIEW, False),
        Case("connect-cannot-delete", ConnectSessionMode.CONNECT, MODES_DELETE, False),
        Case("manage-can-view", ConnectSessionMode.MANAGE, MODES_VIEW, True),
        Case("manage-can-delete", ConnectSessionMode.MANAGE, MODES_DELETE, True),
        Case("manage-cannot-create", ConnectSessionMode.MANAGE, MODES_CREATE, False),
        Case("reauth-can-view", ConnectSessionMode.REAUTH, MODES_VIEW, True),
        Case("reauth-cannot-create", ConnectSessionMode.REAUTH, MODES_CREATE, False),
        Case("reauth-cannot-delete", ConnectSessionMode.REAUTH, MODES_DELETE, False),
    ]

    @pytest.mark.parametrize("case", CASES, ids=lambda c: c.id)
    def test_mode_enforcement(self, case: Case):
        session = make_session(mode=case.mode)
        if case.should_pass:
            ConnectService._check_mode(session, case.allowed_modes, "test op")
        else:
            with pytest.raises(HTTPException) as exc_info:
                ConnectService._check_mode(session, case.allowed_modes, "test op")
            assert exc_info.value.status_code == 403


class TestCheckIntegrationAccess:
    """ConnectService._check_integration_access — integration filtering."""

    @dataclass
    class Case:
        id: str
        allowed: Optional[List[str]]
        short_name: str
        should_pass: bool

    CASES = [
        Case("no-restriction", None, "slack", True),
        Case("allowed", ["slack", "github"], "slack", True),
        Case("denied", ["slack", "github"], "notion", False),
        Case("empty-list-passes-falsy", [], "slack", True),
    ]

    @pytest.mark.parametrize("case", CASES, ids=lambda c: c.id)
    def test_integration_filtering(self, case: Case):
        session = make_session(allowed_integrations=case.allowed)
        if case.should_pass:
            ConnectService._check_integration_access(session, case.short_name)
        else:
            with pytest.raises(HTTPException) as exc_info:
                ConnectService._check_integration_access(session, case.short_name)
            assert exc_info.value.status_code == 403


class TestCheckCollectionScope:
    """ConnectService._check_collection_scope — collection boundary."""

    def test_matching_collection_passes(self):
        ConnectService._check_collection_scope(COLLECTION_ID, make_session())

    def test_mismatched_collection_raises_403(self):
        with pytest.raises(HTTPException) as exc_info:
            ConnectService._check_collection_scope("other-collection", make_session())
        assert exc_info.value.status_code == 403


# ===========================================================================
# Context builder
# ===========================================================================


class TestBuildContext:
    """ConnectService._build_context — builds ConnectContext from session."""

    async def test_raises_404_for_missing_org(self, connect_service):
        missing_org_id = uuid4()
        session = make_session(org_id=missing_org_id)

        with pytest.raises(HTTPException) as exc_info:
            await connect_service._build_context(AsyncMock(), session)
        assert exc_info.value.status_code == 404

    async def test_returns_connect_context(self, connect_service):
        session = make_session()
        ctx = await connect_service._build_context(AsyncMock(), session)

        assert isinstance(ctx, ConnectContext)
        assert str(ctx.organization.id) == str(ORG_ID)
        assert ctx.session_id == SESSION_ID
        assert ctx.collection_id == COLLECTION_ID
        assert ctx.auth_metadata["connect_session_id"] == str(SESSION_ID)

    async def test_headers_identify_connect(self, connect_service):
        session = make_session()
        ctx = await connect_service._build_context(AsyncMock(), session)

        assert ctx.headers is not None
        assert ctx.headers.client_name == "airweave-connect"
        assert ctx.headers.session_id == str(SESSION_ID)


# ===========================================================================
# Service integration tests (with fakes)
# ===========================================================================


class TestListSourceConnections:
    """ConnectService.list_source_connections — mode + filtering matrix."""

    @dataclass
    class Case:
        id: str
        mode: ConnectSessionMode
        allowed_integrations: Optional[List[str]]
        seeded_connections: List[str]  # short_names
        expected_count: int
        should_raise: bool = False

    CASES = [
        Case("all-mode-no-filter", ConnectSessionMode.ALL, None, ["slack", "github"], 2),
        Case("manage-mode-no-filter", ConnectSessionMode.MANAGE, None, ["slack"], 1),
        Case("all-mode-with-filter", ConnectSessionMode.ALL, ["slack"], ["slack", "github"], 1),
        Case("connect-mode-denied", ConnectSessionMode.CONNECT, None, ["slack"], 0, True),
        Case("reauth-mode-allowed", ConnectSessionMode.REAUTH, None, ["slack"], 1),
    ]

    @pytest.mark.parametrize("case", CASES, ids=lambda c: c.id)
    async def test_list_matrix(self, case: Case, connect_service, sc_service):
        items = [
            _make_connection_list_item(short_name=sn)
            for sn in case.seeded_connections
        ]
        sc_service.seed_list_items(items)

        session = make_session(
            mode=case.mode, allowed_integrations=case.allowed_integrations
        )

        if case.should_raise:
            with pytest.raises(HTTPException) as exc_info:
                await connect_service.list_source_connections(AsyncMock(), session)
            assert exc_info.value.status_code == 403
        else:
            result = await connect_service.list_source_connections(AsyncMock(), session)
            assert len(result) == case.expected_count


class TestGetSourceConnection:
    """ConnectService.get_source_connection — scope + access checks."""

    @dataclass
    class Case:
        id: str
        mode: ConnectSessionMode
        conn_collection: str
        conn_short_name: str
        allowed_integrations: Optional[List[str]]
        expected_status: int  # 0 means success

    CASES = [
        Case("happy-path", ConnectSessionMode.ALL, COLLECTION_ID, "slack", None, 0),
        Case("wrong-collection", ConnectSessionMode.ALL, "other-col", "slack", None, 403),
        Case("filtered-out", ConnectSessionMode.ALL, COLLECTION_ID, "notion", ["slack"], 403),
        Case("connect-mode-denied", ConnectSessionMode.CONNECT, COLLECTION_ID, "slack", None, 403),
    ]

    @pytest.mark.parametrize("case", CASES, ids=lambda c: c.id)
    async def test_get_matrix(self, case: Case, connect_service, sc_service):
        conn = _make_connection_response(
            short_name=case.conn_short_name,
            collection_id=case.conn_collection,
        )
        sc_service._store[CONN_ID] = conn

        session = make_session(
            mode=case.mode, allowed_integrations=case.allowed_integrations
        )

        if case.expected_status > 0:
            with pytest.raises(HTTPException) as exc_info:
                await connect_service.get_source_connection(AsyncMock(), CONN_ID, session)
            assert exc_info.value.status_code == case.expected_status
        else:
            result = await connect_service.get_source_connection(AsyncMock(), CONN_ID, session)
            assert result is not None


class TestDeleteSourceConnection:
    """ConnectService.delete_source_connection — mode enforcement."""

    @dataclass
    class Case:
        id: str
        mode: ConnectSessionMode
        should_raise: bool
        expected_status: int = 403

    CASES = [
        Case("all-mode-allowed", ConnectSessionMode.ALL, False),
        Case("manage-mode-allowed", ConnectSessionMode.MANAGE, False),
        Case("connect-mode-denied", ConnectSessionMode.CONNECT, True),
        Case("reauth-mode-denied", ConnectSessionMode.REAUTH, True),
    ]

    @pytest.mark.parametrize("case", CASES, ids=lambda c: c.id)
    async def test_delete_mode_matrix(self, case: Case, connect_service, sc_service):
        conn = _make_connection_response()
        sc_service._store[CONN_ID] = conn

        session = make_session(mode=case.mode)

        if case.should_raise:
            with pytest.raises(HTTPException) as exc_info:
                await connect_service.delete_source_connection(AsyncMock(), CONN_ID, session)
            assert exc_info.value.status_code == case.expected_status
        else:
            result = await connect_service.delete_source_connection(AsyncMock(), CONN_ID, session)
            assert result is not None


class TestCreateSourceConnection:
    """ConnectService.create_source_connection — mode + filter enforcement."""

    @dataclass
    class Case:
        id: str
        mode: ConnectSessionMode
        allowed_integrations: Optional[List[str]]
        short_name: str
        should_raise: bool
        expected_status: int = 403

    CASES = [
        Case("all-mode-allowed", ConnectSessionMode.ALL, None, "slack", False),
        Case("connect-mode-allowed", ConnectSessionMode.CONNECT, None, "slack", False),
        Case("manage-mode-denied", ConnectSessionMode.MANAGE, None, "slack", True),
        Case("reauth-mode-denied", ConnectSessionMode.REAUTH, None, "slack", True),
        Case("filtered-out", ConnectSessionMode.ALL, ["github"], "slack", True),
        Case("filtered-in", ConnectSessionMode.ALL, ["slack"], "slack", False),
    ]

    @pytest.mark.parametrize("case", CASES, ids=lambda c: c.id)
    async def test_create_mode_matrix(self, case: Case, connect_service, sc_service):
        created_conn = _make_connection_response(short_name=case.short_name)

        async def _fake_create(db, obj_in, ctx):
            return created_conn

        sc_service._create_service = MagicMock()
        sc_service._create_service.create = _fake_create

        session = make_session(
            mode=case.mode, allowed_integrations=case.allowed_integrations
        )
        create_in = schemas.SourceConnectionCreate(
            short_name=case.short_name,
            readable_collection_id="ignored-by-service",
        )

        if case.should_raise:
            with pytest.raises(HTTPException) as exc_info:
                await connect_service.create_source_connection(
                    AsyncMock(), create_in, session, "fake-token"
                )
            assert exc_info.value.status_code == case.expected_status
        else:
            result = await connect_service.create_source_connection(
                AsyncMock(), create_in, session, "fake-token"
            )
            assert result is not None
            assert create_in.readable_collection_id == COLLECTION_ID


class TestGetConnectionJobs:
    """ConnectService.get_connection_jobs — access check + empty sync handling."""

    async def test_returns_empty_when_no_sync(self, connect_service, sc_service):
        conn = _make_connection_response(sync_id=None)
        sc_service._store[CONN_ID] = conn

        session = make_session()
        result = await connect_service.get_connection_jobs(AsyncMock(), CONN_ID, session)
        assert result == []

    async def test_raises_for_wrong_collection(self, connect_service, sc_service):
        conn = _make_connection_response(collection_id="other-collection")
        sc_service._store[CONN_ID] = conn

        session = make_session()
        with pytest.raises(HTTPException) as exc_info:
            await connect_service.get_connection_jobs(AsyncMock(), CONN_ID, session)
        assert exc_info.value.status_code == 403


class TestListSources:
    """ConnectService.list_sources — filtering by allowed_integrations."""

    async def test_returns_all_when_unrestricted(self, connect_service, source_service):
        s1 = MagicMock(spec=schemas.Source)
        s1.short_name = "slack"
        s2 = MagicMock(spec=schemas.Source)
        s2.short_name = "github"
        source_service._sources = {"slack": s1, "github": s2}

        session = make_session()
        result = await connect_service.list_sources(AsyncMock(), session)
        assert len(result) == 2

    async def test_filters_by_allowed_integrations(self, connect_service, source_service):
        s1 = MagicMock(spec=schemas.Source)
        s1.short_name = "slack"
        s2 = MagicMock(spec=schemas.Source)
        s2.short_name = "github"
        source_service._sources = {"slack": s1, "github": s2}

        session = make_session(allowed_integrations=["slack"])
        result = await connect_service.list_sources(AsyncMock(), session)
        assert len(result) == 1
        assert result[0].short_name == "slack"


class TestGetSource:
    """ConnectService.get_source — access restriction."""

    async def test_raises_403_when_restricted(self, connect_service):
        session = make_session(allowed_integrations=["github"])
        with pytest.raises(HTTPException) as exc_info:
            await connect_service.get_source(AsyncMock(), "slack", session)
        assert exc_info.value.status_code == 403

    async def test_passes_when_allowed(self, connect_service, source_service):
        src = MagicMock(spec=schemas.Source)
        src.short_name = "slack"
        source_service._sources = {"slack": src}

        session = make_session(allowed_integrations=["slack"])
        result = await connect_service.get_source(AsyncMock(), "slack", session)
        assert result.short_name == "slack"
