"""Tests for activity and workflow wiring."""

import sys
from unittest.mock import MagicMock, patch

import pytest

_FACTORY_KEY = "airweave.core.container.factory"


@pytest.fixture(autouse=True)
def _mock_factory_import():
    """Prevent cohere import chain via factory.py."""
    original = sys.modules.get(_FACTORY_KEY)
    already_present = _FACTORY_KEY in sys.modules
    if not already_present:
        sys.modules[_FACTORY_KEY] = MagicMock(create_container=MagicMock())
    yield
    if not already_present:
        sys.modules.pop(_FACTORY_KEY, None)
    elif original is not None:
        sys.modules[_FACTORY_KEY] = original


@pytest.mark.unit
def test_create_activities_returns_list():
    mock_container = MagicMock()

    with patch("airweave.core.container.container", mock_container):
        from airweave.domains.temporal.worker.wiring import create_activities

        result = create_activities()

    assert isinstance(result, list)
    assert len(result) == 7


@pytest.mark.unit
def test_create_activities_raises_when_container_none():
    with patch("airweave.core.container.container", None):
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
