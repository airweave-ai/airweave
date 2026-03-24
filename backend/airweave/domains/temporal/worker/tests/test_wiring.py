"""Tests for activity and workflow wiring."""

from unittest.mock import MagicMock, patch

import pytest

CONTAINER_MODULE = "airweave.core.container"


@pytest.mark.unit
def test_create_activities_returns_list():
    mock_container = MagicMock()
    mock_container.email_service = MagicMock()
    mock_container.event_bus = MagicMock()
    mock_container.sync_service = MagicMock()
    mock_container.sync_job_state_machine = MagicMock()
    mock_container.sync_repo = MagicMock()
    mock_container.sync_job_repo = MagicMock()
    mock_container.sc_repo = MagicMock()
    mock_container.conn_repo = MagicMock()
    mock_container.collection_repo = MagicMock()
    mock_container.temporal_workflow_service = MagicMock()
    mock_container.temporal_schedule_service = MagicMock()
    mock_container.arf_service = MagicMock()

    with patch(f"{CONTAINER_MODULE}.container", mock_container):
        from airweave.domains.temporal.worker.wiring import create_activities

        result = create_activities()

    assert isinstance(result, list)
    assert len(result) == 7


@pytest.mark.unit
def test_create_activities_raises_when_container_none():
    with patch(f"{CONTAINER_MODULE}.container", None):
        from airweave.domains.temporal.worker.wiring import create_activities

        with pytest.raises(RuntimeError, match="Container not initialized"):
            create_activities()


@pytest.mark.unit
def test_get_workflows_returns_classes():
    from airweave.domains.temporal.worker.wiring import get_workflows

    result = get_workflows()

    assert isinstance(result, list)
    assert len(result) == 4
    class_names = [cls.__name__ for cls in result]
    assert "RunSourceConnectionWorkflow" in class_names
    assert "CleanupStuckSyncJobsWorkflow" in class_names
    assert "CleanupSyncDataWorkflow" in class_names
    assert "APIKeyExpirationCheckWorkflow" in class_names
