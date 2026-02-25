"""Unit tests for SourceConnectionUpdateService.

Table-driven tests. Zero patches -- all deps are fakes.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi import HTTPException
from pydantic import BaseModel

from airweave import schemas
from airweave.adapters.encryption.fake import FakeCredentialEncryptor
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
from airweave.domains.sources.fakes.service import FakeSourceService
from airweave.domains.sources.fakes.validation import FakeSourceValidationService
from airweave.domains.syncs.fakes.sync_record_service import FakeSyncRecordService
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


class _AuthPayload(BaseModel):
    token: str


def _make_ctx() -> ApiContext:
    org = Organization(id=str(ORG_ID), name="Test Org", created_at=NOW, modified_at=NOW)
    return ApiContext(
        request_id="test-req",
        organization=org,
        auth_method=AuthMethod.SYSTEM,
        logger=logger.with_context(request_id="test-req"),
    )


_UNSET = object()


def _make_sc(
    *,
    id=None,
    sync_id=None,
    short_name="github",
    name="Test SC",
    connection_id=_UNSET,
    is_authenticated=True,
    readable_auth_provider_id=None,
    connection_init_session_id=None,
):
    sc = MagicMock(spec=SourceConnection)
    sc.id = id or uuid4()
    sc.sync_id = sync_id
    sc.short_name = short_name
    sc.name = name
    sc.description = None
    sc.readable_collection_id = "test-col"
    sc.organization_id = ORG_ID
    sc.connection_id = uuid4() if connection_id is _UNSET else connection_id
    sc.is_authenticated = is_authenticated
    sc.created_at = NOW
    sc.modified_at = NOW
    sc.readable_auth_provider_id = readable_auth_provider_id
    sc.connection_init_session_id = connection_init_session_id
    return sc


def _make_source_schema(*, short_name="github", supports_continuous=False):
    src = MagicMock(spec=schemas.Source)
    src.short_name = short_name
    src.supports_continuous = supports_continuous
    return src


def _build_service(
    sc_repo=None,
    collection_repo=None,
    connection_repo=None,
    cred_repo=None,
    sync_repo=None,
    sync_record_service=None,
    source_service=None,
    source_validation=None,
    credential_encryptor=None,
    response_builder=None,
    temporal_schedule_service=None,
):
    return SourceConnectionUpdateService(
        sc_repo=sc_repo or FakeSourceConnectionRepository(),
        collection_repo=collection_repo or FakeCollectionRepository(),
        connection_repo=connection_repo or FakeConnectionRepository(),
        cred_repo=cred_repo or FakeIntegrationCredentialRepository(),
        sync_repo=sync_repo or FakeSyncRepository(),
        sync_record_service=sync_record_service or FakeSyncRecordService(),
        source_service=source_service or FakeSourceService(),
        source_validation=source_validation or FakeSourceValidationService(),
        credential_encryptor=credential_encryptor or FakeCredentialEncryptor(),
        response_builder=response_builder or FakeResponseBuilder(),
        temporal_schedule_service=temporal_schedule_service or FakeTemporalScheduleService(),
    )


# ---------------------------------------------------------------------------
# Not found
# ---------------------------------------------------------------------------


async def test_update_not_found():
    svc = _build_service()
    obj_in = SourceConnectionUpdate(name="New Name")
    with pytest.raises(NotFoundException, match="Source connection not found"):
        await svc.update(AsyncMock(), id=uuid4(), obj_in=obj_in, ctx=_make_ctx())


# ---------------------------------------------------------------------------
# Field updates -- table-driven
# ---------------------------------------------------------------------------


@dataclass
class FieldUpdateCase:
    desc: str
    obj_in: SourceConnectionUpdate
    expected_fields: dict = field(default_factory=dict)


FIELD_UPDATE_CASES = [
    FieldUpdateCase("name_only", SourceConnectionUpdate(name="Renamed")),
    FieldUpdateCase("description_only", SourceConnectionUpdate(description="New desc")),
    FieldUpdateCase("name_and_description", SourceConnectionUpdate(name="Renamed", description="Desc")),
]


@pytest.mark.parametrize("case", FIELD_UPDATE_CASES, ids=lambda c: c.desc)
async def test_field_update(case: FieldUpdateCase):
    sc = _make_sc()
    sc_repo = FakeSourceConnectionRepository()
    sc_repo.seed(sc.id, sc)

    svc = _build_service(sc_repo=sc_repo)
    result = await svc.update(AsyncMock(), id=sc.id, obj_in=case.obj_in, ctx=_make_ctx())
    assert result.id == sc.id


# ---------------------------------------------------------------------------
# Config update
# ---------------------------------------------------------------------------


async def test_update_config_valid():
    sc = _make_sc()
    sc_repo = FakeSourceConnectionRepository()
    sc_repo.seed(sc.id, sc)

    validation = FakeSourceValidationService()
    validation.seed_config_result("github", {"key": "validated_value"})

    svc = _build_service(sc_repo=sc_repo, source_validation=validation)
    obj_in = SourceConnectionUpdate(config={"key": "value"})

    result = await svc.update(AsyncMock(), id=sc.id, obj_in=obj_in, ctx=_make_ctx())
    assert result.id == sc.id
    assert any(c[0] == "validate_config" for c in validation._calls)


# ---------------------------------------------------------------------------
# Schedule updates -- table-driven
# ---------------------------------------------------------------------------


@dataclass
class ScheduleCase:
    desc: str
    has_sync: bool
    new_cron: Optional[str]
    expect_temporal_create: bool
    expect_temporal_delete: bool
    has_connection_id: bool = True
    expect_sync_record_create: bool = False


SCHEDULE_CASES = [
    ScheduleCase("update_existing", has_sync=True, new_cron="0 * * * *", expect_temporal_create=True, expect_temporal_delete=False),
    ScheduleCase("remove_schedule", has_sync=True, new_cron=None, expect_temporal_create=False, expect_temporal_delete=True),
    ScheduleCase("add_no_sync", has_sync=False, new_cron="0 * * * *", expect_temporal_create=True, expect_temporal_delete=False, expect_sync_record_create=True),
    ScheduleCase("no_connection_id_warning", has_sync=False, new_cron="0 * * * *", has_connection_id=False, expect_temporal_create=False, expect_temporal_delete=False),
]


@pytest.mark.parametrize("case", SCHEDULE_CASES, ids=lambda c: c.desc)
async def test_schedule_update(case: ScheduleCase):
    sync_id = uuid4() if case.has_sync else None
    connection_id = uuid4() if case.has_connection_id else None
    sc = _make_sc(sync_id=sync_id, connection_id=connection_id)
    sc_repo = FakeSourceConnectionRepository()
    sc_repo.seed(sc.id, sc)

    sync_repo = FakeSyncRepository()
    if case.has_sync and sync_id:
        sync_obj = MagicMock(spec=Sync)
        sync_obj.id = sync_id
        sync_repo.seed_model(sync_id, sync_obj)

    source_svc = FakeSourceService()
    if case.new_cron:
        source_svc.seed(_make_source_schema(short_name="github"))

    temporal = FakeTemporalScheduleService()

    sync_record_svc = FakeSyncRecordService()
    if case.expect_sync_record_create:
        mock_sync = MagicMock(spec=schemas.Sync)
        mock_sync.id = uuid4()
        sync_record_svc.set_create_result(mock_sync)

        col = MagicMock(spec=Collection)
        col.id = uuid4()
        col.readable_id = "test-col"
        col.organization_id = ORG_ID
        col_repo = FakeCollectionRepository()
        col_repo.seed_readable("test-col", col)
    else:
        col_repo = FakeCollectionRepository()

    schedule_val = {"cron": case.new_cron} if case.new_cron is not None else None
    obj_in = SourceConnectionUpdate(schedule=schedule_val)

    svc = _build_service(
        sc_repo=sc_repo,
        sync_repo=sync_repo,
        source_service=source_svc,
        temporal_schedule_service=temporal,
        sync_record_service=sync_record_svc,
        collection_repo=col_repo,
    )

    result = await svc.update(AsyncMock(), id=sc.id, obj_in=obj_in, ctx=_make_ctx())
    assert result.id == sc.id

    if case.expect_temporal_create:
        assert any(c[0] == "create_or_update_schedule" for c in temporal._calls)
    if case.expect_temporal_delete:
        assert any(c[0] == "delete_all_schedules_for_sync" for c in temporal._calls)
    if case.expect_sync_record_create:
        assert any(c[0] == "create_sync" for c in sync_record_svc._calls)


async def test_schedule_add_collection_not_found():
    sc = _make_sc(sync_id=None)
    sc_repo = FakeSourceConnectionRepository()
    sc_repo.seed(sc.id, sc)

    source_svc = FakeSourceService()
    source_svc.seed(_make_source_schema())

    svc = _build_service(sc_repo=sc_repo, source_service=source_svc)
    obj_in = SourceConnectionUpdate(schedule={"cron": "0 * * * *"})

    with pytest.raises(NotFoundException, match="Collection not found"):
        await svc.update(AsyncMock(), id=sc.id, obj_in=obj_in, ctx=_make_ctx())


# ---------------------------------------------------------------------------
# Credential updates -- table-driven
# ---------------------------------------------------------------------------


@dataclass
class CredentialCase:
    desc: str
    is_direct_auth: bool
    expect_success: bool


CREDENTIAL_CASES = [
    CredentialCase("direct_auth_update", is_direct_auth=True, expect_success=True),
    CredentialCase("non_direct_auth_rejection", is_direct_auth=False, expect_success=False),
]


@pytest.mark.parametrize("case", CREDENTIAL_CASES, ids=lambda c: c.desc)
async def test_credential_update(case: CredentialCase):
    conn_id = uuid4()
    cred_id = uuid4()

    if case.is_direct_auth:
        sc = _make_sc(connection_id=conn_id, is_authenticated=True)
    else:
        sc = _make_sc(
            connection_id=conn_id,
            is_authenticated=False,
            readable_auth_provider_id="some-provider",
        )

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

    validation = FakeSourceValidationService()
    validation.seed_auth_result("github", _AuthPayload(token="secret"))

    encryptor = FakeCredentialEncryptor()

    svc = _build_service(
        sc_repo=sc_repo,
        connection_repo=conn_repo,
        cred_repo=cred_repo,
        source_validation=validation,
        credential_encryptor=encryptor,
    )

    obj_in = SourceConnectionUpdate(authentication={"credentials": {"token": "new_secret"}})

    if case.expect_success:
        result = await svc.update(AsyncMock(), id=sc.id, obj_in=obj_in, ctx=_make_ctx())
        assert result.id == sc.id
        assert len(encryptor._encrypt_calls) == 1
        assert any(c[0] == "update" for c in cred_repo._calls)
    else:
        with pytest.raises(HTTPException) as exc_info:
            await svc.update(AsyncMock(), id=sc.id, obj_in=obj_in, ctx=_make_ctx())
        assert exc_info.value.status_code == 400
        assert "direct authentication" in str(exc_info.value.detail)


async def test_credential_update_direct_auth_missing_connection_raises():
    conn_id = uuid4()
    sc = _make_sc(connection_id=conn_id, is_authenticated=True)

    sc_repo = FakeSourceConnectionRepository()
    sc_repo.seed(sc.id, sc)

    validation = FakeSourceValidationService()
    validation.seed_auth_result("github", _AuthPayload(token="secret"))

    svc = _build_service(sc_repo=sc_repo, source_validation=validation)

    obj_in = SourceConnectionUpdate(authentication={"credentials": {"token": "new_secret"}})

    with pytest.raises(NotFoundException, match="Connection not found"):
        await svc.update(AsyncMock(), id=sc.id, obj_in=obj_in, ctx=_make_ctx())


async def test_credential_update_direct_auth_missing_integration_credential_raises():
    conn_id = uuid4()
    sc = _make_sc(connection_id=conn_id, is_authenticated=True)

    sc_repo = FakeSourceConnectionRepository()
    sc_repo.seed(sc.id, sc)

    conn = MagicMock(spec=Connection)
    conn.id = conn_id
    conn.integration_credential_id = None
    conn_repo = FakeConnectionRepository()
    conn_repo.seed(conn_id, conn)

    validation = FakeSourceValidationService()
    validation.seed_auth_result("github", _AuthPayload(token="secret"))

    svc = _build_service(
        sc_repo=sc_repo,
        connection_repo=conn_repo,
        source_validation=validation,
    )

    obj_in = SourceConnectionUpdate(authentication={"credentials": {"token": "new_secret"}})

    with pytest.raises(NotFoundException, match="Integration credential not configured"):
        await svc.update(AsyncMock(), id=sc.id, obj_in=obj_in, ctx=_make_ctx())


async def test_credential_update_direct_auth_missing_credential_record_raises():
    conn_id = uuid4()
    cred_id = uuid4()
    sc = _make_sc(connection_id=conn_id, is_authenticated=True)

    sc_repo = FakeSourceConnectionRepository()
    sc_repo.seed(sc.id, sc)

    conn = MagicMock(spec=Connection)
    conn.id = conn_id
    conn.integration_credential_id = cred_id
    conn_repo = FakeConnectionRepository()
    conn_repo.seed(conn_id, conn)

    validation = FakeSourceValidationService()
    validation.seed_auth_result("github", _AuthPayload(token="secret"))

    svc = _build_service(
        sc_repo=sc_repo,
        connection_repo=conn_repo,
        source_validation=validation,
    )

    obj_in = SourceConnectionUpdate(authentication={"credentials": {"token": "new_secret"}})

    with pytest.raises(NotFoundException, match="Integration credential not found"):
        await svc.update(AsyncMock(), id=sc.id, obj_in=obj_in, ctx=_make_ctx())


# ---------------------------------------------------------------------------
# Cron validation -- table-driven (tests _validate_cron_schedule_for_source directly)
# ---------------------------------------------------------------------------


@dataclass
class CronCase:
    desc: str
    cron: str
    supports_continuous: bool
    expect_error: bool


CRON_CASES = [
    CronCase("hourly_ok", "0 * * * *", False, False),
    CronCase("sub_hourly_rejected", "*/5 * * * *", False, True),
    CronCase("sub_hourly_continuous_ok", "*/5 * * * *", True, False),
    CronCase("every_minute_rejected", "* * * * *", False, True),
    CronCase("every_minute_continuous_ok", "* * * * *", True, False),
    CronCase("daily_ok", "0 0 * * *", False, False),
]


@pytest.mark.parametrize("case", CRON_CASES, ids=lambda c: c.desc)
def test_cron_validation(case: CronCase):
    svc = _build_service()
    source = _make_source_schema(supports_continuous=case.supports_continuous)

    if case.expect_error:
        with pytest.raises(HTTPException) as exc_info:
            svc._validate_cron_schedule_for_source(case.cron, source, _make_ctx())
        assert exc_info.value.status_code == 400
    else:
        svc._validate_cron_schedule_for_source(case.cron, source, _make_ctx())
