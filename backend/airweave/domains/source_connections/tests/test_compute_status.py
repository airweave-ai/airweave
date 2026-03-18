"""Tests for compute_status() and SourceConnectionListItem.status with error categories."""

from dataclasses import dataclass
from types import SimpleNamespace
from typing import Optional

import pytest

from airweave.core.shared_models import SourceConnectionErrorCategory, SourceConnectionStatus, SyncJobStatus
from airweave.schemas.source_connection import SourceConnectionListItem, compute_status


@dataclass
class StatusCase:
    name: str
    is_authenticated: bool
    is_active: bool
    last_job_status: Optional[str]
    last_job_error_category: Optional[str]
    expected: SourceConnectionStatus


CASES = [
    StatusCase(
        name="failed_with_error_category_returns_needs_reauth",
        is_authenticated=True,
        is_active=True,
        last_job_status="failed",
        last_job_error_category=SourceConnectionErrorCategory.OAUTH_CREDENTIALS_EXPIRED.value,
        expected=SourceConnectionStatus.NEEDS_REAUTH,
    ),
    StatusCase(
        name="failed_without_error_category_returns_error",
        is_authenticated=True,
        is_active=True,
        last_job_status="failed",
        last_job_error_category=None,
        expected=SourceConnectionStatus.ERROR,
    ),
    StatusCase(
        name="completed_returns_active",
        is_authenticated=True,
        is_active=True,
        last_job_status="completed",
        last_job_error_category=None,
        expected=SourceConnectionStatus.ACTIVE,
    ),
    StatusCase(
        name="running_returns_syncing",
        is_authenticated=True,
        is_active=True,
        last_job_status="running",
        last_job_error_category=None,
        expected=SourceConnectionStatus.SYNCING,
    ),
    StatusCase(
        name="unauthenticated_returns_pending_auth",
        is_authenticated=False,
        is_active=True,
        last_job_status=None,
        last_job_error_category=None,
        expected=SourceConnectionStatus.PENDING_AUTH,
    ),
    StatusCase(
        name="inactive_returns_inactive",
        is_authenticated=True,
        is_active=False,
        last_job_status=None,
        last_job_error_category=None,
        expected=SourceConnectionStatus.INACTIVE,
    ),
    StatusCase(
        name="api_key_invalid_category",
        is_authenticated=True,
        is_active=True,
        last_job_status="failed",
        last_job_error_category=SourceConnectionErrorCategory.API_KEY_INVALID.value,
        expected=SourceConnectionStatus.NEEDS_REAUTH,
    ),
    StatusCase(
        name="auth_provider_account_gone_category",
        is_authenticated=True,
        is_active=True,
        last_job_status="failed",
        last_job_error_category=SourceConnectionErrorCategory.AUTH_PROVIDER_ACCOUNT_GONE.value,
        expected=SourceConnectionStatus.NEEDS_REAUTH,
    ),
]


@pytest.mark.parametrize("case", CASES, ids=lambda c: c.name)
def test_compute_status(case: StatusCase):
    source_conn = SimpleNamespace(
        is_authenticated=case.is_authenticated,
        is_active=case.is_active,
    )
    job_status = SyncJobStatus(case.last_job_status) if case.last_job_status else None
    result = compute_status(source_conn, job_status, case.last_job_error_category)
    assert result == case.expected


@pytest.mark.parametrize("case", CASES, ids=lambda c: c.name)
def test_list_item_computed_status(case: StatusCase):
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)
    item = SourceConnectionListItem(
        id="550e8400-e29b-41d4-a716-446655440000",
        name="test",
        short_name="github",
        readable_collection_id="test-abc123",
        created_at=now,
        modified_at=now,
        is_authenticated=case.is_authenticated,
        is_active=case.is_active,
        last_job_status=case.last_job_status,
        last_job_error_category=case.last_job_error_category,
    )
    assert item.status == case.expected
