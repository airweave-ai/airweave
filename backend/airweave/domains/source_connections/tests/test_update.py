"""Unit tests for SourceConnectionUpdateService.

Table-driven tests covering:
- Source connection not found
- Simple field update (name)
- Config update with validation
- Schedule update on existing sync
- Credential update for direct auth
- Credential rejection for non-direct auth
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from airweave.api.context import ApiContext
from airweave.core.exceptions import NotFoundException
from airweave.core.logging import logger
from airweave.core.shared_models import AuthMethod
from airweave.domains.collections.fakes.repository import FakeCollectionRepository
from airweave.domains.connections.fakes.repository import FakeConnectionRepository
from airweave.domains.credentials.fakes.repository import (
    FakeIntegrationCredentialRepository,
)
from airweave.domains.source_connections.fakes.repository import (
    FakeSourceConnectionRepository,
)
from airweave.domains.source_connections.fakes.response import FakeResponseBuilder
from airweave.domains.source_connections.update import SourceConnectionUpdateService
from airweave.domains.syncs.fakes.sync_repository import FakeSyncRepository
from airweave.domains.temporal.fakes.schedule_service import FakeTemporalScheduleService
from airweave.models.collection import Collection
from airweave.models.connection import Connection
from airweave.models.integration_credential import IntegrationCredential
from airweave.models.source_connection import SourceConnection
from airweave.models.sync import Sync
from airweave.schemas.organization import Organization
from airweave.schemas.source_connection import SourceConnectionUpdate

NOW = datetime.now(timezone.utc)
ORG_ID = uuid4()


def _make_ctx() -> ApiContext:
    org = Organization(id=str(ORG_ID), name="Test Org", created_at=NOW, modified_at=NOW)
    return ApiContext(
        request_id="test-req",
        organization=org,
        auth_method=AuthMethod.SYSTEM,
        logger=logger.with_context(request_id="test-req"),
    )


def _make_sc(*, id=None, sync_id=None, short_name="github", name="Test SC") -> SourceConnection:
    sc = MagicMock(spec=SourceConnection)
    sc.id = id or uuid4()
    sc.sync_id = sync_id
    sc.short_name = short_name
    sc.name = name
    sc.description = None
    sc.readable_collection_id = "test-col"
    sc.organization_id = ORG_ID
    sc.connection_id = uuid4()
    sc.is_authenticated = True
    sc.created_at = NOW
    sc.modified_at = NOW
    return sc


def _build_service(
    sc_repo=None,
    collection_repo=None,
    connection_repo=None,
    cred_repo=None,
    sync_repo=None,
    response_builder=None,
    temporal_schedule_service=None,
) -> SourceConnectionUpdateService:
    return SourceConnectionUpdateService(
        sc_repo=sc_repo or FakeSourceConnectionRepository(),
        collection_repo=collection_repo or FakeCollectionRepository(),
        connection_repo=connection_repo or FakeConnectionRepository(),
        cred_repo=cred_repo or FakeIntegrationCredentialRepository(),
        sync_repo=sync_repo or FakeSyncRepository(),
        response_builder=response_builder or FakeResponseBuilder(),
        temporal_schedule_service=temporal_schedule_service or FakeTemporalScheduleService(),
    )


# ---------------------------------------------------------------------------
# Error paths
# ---------------------------------------------------------------------------


async def test_update_not_found():
    """Raises NotFoundException when SC doesn't exist."""
    svc = _build_service()
    obj_in = SourceConnectionUpdate(name="New Name")
    with pytest.raises(NotFoundException, match="Source connection not found"):
        await svc.update(AsyncMock(), id=uuid4(), obj_in=obj_in, ctx=_make_ctx())


# ---------------------------------------------------------------------------
# Simple field update
# ---------------------------------------------------------------------------


async def test_update_name():
    """Simple name update without config/schedule/credential changes."""
    sc = _make_sc()
    sc_repo = FakeSourceConnectionRepository()
    sc_repo.seed(sc.id, sc)

    svc = _build_service(sc_repo=sc_repo)
    obj_in = SourceConnectionUpdate(name="Renamed")

    result = await svc.update(AsyncMock(), id=sc.id, obj_in=obj_in, ctx=_make_ctx())
    assert result.id == sc.id


# ---------------------------------------------------------------------------
# Config update
# ---------------------------------------------------------------------------


@patch(
    "airweave.domains.source_connections.update.source_connection_helpers.validate_config_fields",
    new_callable=AsyncMock,
)
async def test_update_config_calls_validation(mock_validate):
    """Config update delegates to validate_config_fields helper."""
    mock_validate.return_value = {"key": "validated_value"}

    sc = _make_sc()
    sc_repo = FakeSourceConnectionRepository()
    sc_repo.seed(sc.id, sc)

    svc = _build_service(sc_repo=sc_repo)
    obj_in = SourceConnectionUpdate(config={"key": "value"})

    result = await svc.update(AsyncMock(), id=sc.id, obj_in=obj_in, ctx=_make_ctx())
    assert result.id == sc.id
    mock_validate.assert_awaited_once()


# ---------------------------------------------------------------------------
# Schedule update on existing sync
# ---------------------------------------------------------------------------


async def test_update_schedule_existing_sync():
    """Schedule update on existing sync updates DB + Temporal."""
    sync_id = uuid4()
    sc = _make_sc(sync_id=sync_id)
    sc_repo = FakeSourceConnectionRepository()
    sc_repo.seed(sc.id, sc)

    sync_obj = MagicMock(spec=Sync)
    sync_obj.id = sync_id
    sync_repo = FakeSyncRepository()
    sync_repo.seed_model(sync_id, sync_obj)

    temporal = FakeTemporalScheduleService()

    svc = _build_service(
        sc_repo=sc_repo,
        sync_repo=sync_repo,
        temporal_schedule_service=temporal,
    )
    obj_in = SourceConnectionUpdate(schedule={"cron": "0 * * * *"})

    with patch.object(svc, "_get_and_validate_source", new_callable=AsyncMock) as mock_source:
        source_mock = MagicMock()
        source_mock.supports_continuous = False
        source_mock.short_name = "github"
        mock_source.return_value = source_mock

        result = await svc.update(AsyncMock(), id=sc.id, obj_in=obj_in, ctx=_make_ctx())

    assert result.id == sc.id
    assert any(c[0] == "create_or_update_schedule" for c in temporal._calls)


# ---------------------------------------------------------------------------
# Schedule removal
# ---------------------------------------------------------------------------


async def test_update_schedule_removal():
    """Setting schedule to None deletes temporal schedule."""
    sync_id = uuid4()
    sc = _make_sc(sync_id=sync_id)
    sc_repo = FakeSourceConnectionRepository()
    sc_repo.seed(sc.id, sc)

    sync_obj = MagicMock(spec=Sync)
    sync_obj.id = sync_id
    sync_repo = FakeSyncRepository()
    sync_repo.seed_model(sync_id, sync_obj)

    temporal = FakeTemporalScheduleService()

    svc = _build_service(
        sc_repo=sc_repo,
        sync_repo=sync_repo,
        temporal_schedule_service=temporal,
    )
    obj_in = SourceConnectionUpdate(schedule=None)
    result = await svc.update(AsyncMock(), id=sc.id, obj_in=obj_in, ctx=_make_ctx())

    assert result.id == sc.id
    assert any(c[0] == "delete_all_schedules_for_sync" for c in temporal._calls)


# ---------------------------------------------------------------------------
# Credential update
# ---------------------------------------------------------------------------


@patch(
    "airweave.domains.source_connections.update.source_connection_helpers.validate_auth_fields",
    new_callable=AsyncMock,
)
@patch("airweave.domains.source_connections.update.credentials.encrypt")
async def test_update_credentials_direct_auth(mock_encrypt, mock_validate_auth):
    """Direct auth credential update encrypts and persists."""
    from airweave.schemas.source_connection import determine_auth_method

    mock_validate_auth.return_value = MagicMock(model_dump=lambda: {"token": "secret"})
    mock_encrypt.return_value = "encrypted_blob"

    sc = _make_sc()
    conn_id = sc.connection_id
    cred_id = uuid4()

    sc_repo = FakeSourceConnectionRepository()
    sc_repo.seed(sc.id, sc)

    conn = MagicMock(spec=Connection)
    conn.id = conn_id
    conn.integration_credential_id = cred_id
    conn_repo = FakeConnectionRepository()
    conn_repo.seed(conn_id, conn)

    cred = MagicMock(spec=IntegrationCredential)
    cred.id = cred_id
    cred_repo = FakeIntegrationCredentialRepository()
    cred_repo.seed(cred_id, cred)

    svc = _build_service(
        sc_repo=sc_repo,
        connection_repo=conn_repo,
        cred_repo=cred_repo,
    )

    obj_in = SourceConnectionUpdate(
        authentication={"credentials": {"token": "new_secret"}}
    )

    with patch(
        "airweave.schemas.source_connection.determine_auth_method"
    ) as mock_auth_method:
        from airweave.schemas.source_connection import AuthenticationMethod

        mock_auth_method.return_value = AuthenticationMethod.DIRECT
        result = await svc.update(AsyncMock(), id=sc.id, obj_in=obj_in, ctx=_make_ctx())

    assert result.id == sc.id
    mock_encrypt.assert_called_once()
    assert any(c[0] == "update" for c in cred_repo._calls)
