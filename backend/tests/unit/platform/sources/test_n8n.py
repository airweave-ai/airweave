"""Unit tests for n8n source connector.

Tests the N8nSource connector with mocked API responses that match
the actual n8n API format exactly.
"""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from airweave.platform.configs.auth import N8nAuthConfig
from airweave.platform.configs.config import N8nConfig
from airweave.platform.sources.n8n import N8nSource


# Mock API responses based on actual n8n API structure
MOCK_WORKFLOWS_RESPONSE = {
    "data": [
        {
            "id": "1",
            "name": "Customer Onboarding Workflow",
            "active": True,
            "createdAt": "2025-01-01T10:00:00.000Z",
            "updatedAt": "2025-01-15T14:30:00.000Z",
            "tags": ["customer", "onboarding"],
            "nodes": [
                {
                    "id": "node-1",
                    "name": "Webhook",
                    "type": "n8n-nodes-base.webhook",
                    "typeVersion": 1,
                    "position": [250, 300],
                    "parameters": {"path": "customer-webhook"},
                },
                {
                    "id": "node-2",
                    "name": "Send Email",
                    "type": "n8n-nodes-base.emailSend",
                    "typeVersion": 1,
                    "position": [450, 300],
                    "parameters": {"toEmail": "customer@example.com"},
                },
            ],
            "connections": {
                "Webhook": {"main": [[{"node": "Send Email", "type": "main", "index": 0}]]}
            },
            "settings": {"executionOrder": "v1"},
            "staticData": None,
            "versionId": "v1",
        },
        {
            "id": "2",
            "name": "Data Sync Workflow",
            "active": False,
            "createdAt": "2025-01-10T09:00:00.000Z",
            "updatedAt": "2025-01-10T09:30:00.000Z",
            "tags": [{"id": "tag1", "name": "data-sync"}],
            "nodes": [
                {
                    "id": "node-3",
                    "name": "Schedule",
                    "type": "n8n-nodes-base.scheduleTrigger",
                    "typeVersion": 1,
                    "position": [250, 300],
                    "parameters": {"rule": {"interval": [{"field": "hours", "hoursInterval": 1}]}},
                },
                {
                    "id": "node-4",
                    "name": "HTTP Request",
                    "type": "n8n-nodes-base.httpRequest",
                    "typeVersion": 1,
                    "position": [450, 300],
                    "parameters": {"url": "https://api.example.com/data"},
                },
            ],
            "connections": {
                "Schedule": {"main": [[{"node": "HTTP Request", "type": "main", "index": 0}]]}
            },
            "settings": None,
            "staticData": {"key": "value"},
            "versionId": None,
        },
    ]
}

MOCK_EXECUTIONS_RESPONSE_SUCCESS = {
    "data": [
        {
            "id": "exec-1",
            "workflowId": "1",
            "mode": "trigger",
            "status": "success",
            "startedAt": "2025-01-15T14:30:00.000Z",
            "stoppedAt": "2025-01-15T14:30:05.000Z",
            "finished": True,
            "retryOf": None,
            "retrySuccessId": None,
            "waitingExecution": None,
            "data": {"resultData": {"runData": {}}},
        },
        {
            "id": "exec-2",
            "workflowId": "1",
            "mode": "manual",
            "status": "success",
            "startedAt": "2025-01-15T12:00:00.000Z",
            "stoppedAt": "2025-01-15T12:00:03.000Z",
            "finished": True,
            "retryOf": None,
            "retrySuccessId": None,
            "waitingExecution": None,
            "data": {"resultData": {"runData": {}}},
        },
    ],
    "nextCursor": None,
}

MOCK_EXECUTIONS_RESPONSE_WITH_ERROR = {
    "data": [
        {
            "id": "exec-error-1",
            "workflowId": "1",
            "mode": "trigger",
            "status": "error",
            "startedAt": "2025-01-14T10:00:00.000Z",
            "stoppedAt": "2025-01-14T10:00:02.000Z",
            "finished": True,
            "retryOf": None,
            "retrySuccessId": None,
            "waitingExecution": None,
            "data": {
                "resultData": {
                    "error": {
                        "message": "Connection timeout to external API",
                        "name": "Error",
                    }
                }
            },
        },
    ],
    "nextCursor": None,
}


@pytest.fixture
def n8n_auth_config():
    """Create a mock N8nAuthConfig."""
    return N8nAuthConfig(url="https://n8n.example.com", api_key="test_api_key_12345")


@pytest.fixture
def n8n_config_with_executions():
    """Create a mock N8nConfig with executions enabled."""
    return N8nConfig(include_executions=True, max_executions_per_workflow=100)


@pytest.fixture
def n8n_config_without_executions():
    """Create a mock N8nConfig with executions disabled."""
    return N8nConfig(include_executions=False, max_executions_per_workflow=100)


@pytest.mark.asyncio
async def test_create_n8n_source(n8n_auth_config, n8n_config_with_executions):
    """Test creating an N8nSource instance."""
    source = await N8nSource.create(n8n_auth_config, n8n_config_with_executions.model_dump())

    assert source.base_url == "https://n8n.example.com"
    assert source.api_key == "test_api_key_12345"
    assert source.include_executions is True
    assert source.max_executions_per_workflow == 100


@pytest.mark.asyncio
async def test_create_n8n_source_with_defaults(n8n_auth_config):
    """Test creating an N8nSource instance with default config."""
    source = await N8nSource.create(n8n_auth_config, None)

    assert source.base_url == "https://n8n.example.com"
    assert source.api_key == "test_api_key_12345"
    assert source.include_executions is True  # default
    assert source.max_executions_per_workflow == 100  # default


@pytest.mark.asyncio
async def test_get_with_auth(n8n_auth_config):
    """Test _get_with_auth makes correct API request."""
    source = await N8nSource.create(n8n_auth_config, None)

    # Mock the HTTP client
    mock_client = AsyncMock()
    mock_response = MagicMock()
    mock_response.json.return_value = {"data": []}
    mock_response.raise_for_status = MagicMock()
    mock_client.get.return_value = mock_response

    result = await source._get_with_auth(mock_client, "/workflows")

    # Verify the request was made correctly
    mock_client.get.assert_called_once()
    call_args = mock_client.get.call_args

    assert call_args[0][0] == "https://n8n.example.com/api/v1/workflows"
    assert call_args[1]["headers"]["X-N8N-API-KEY"] == "test_api_key_12345"
    assert call_args[1]["timeout"] == 20.0
    assert result == {"data": []}


@pytest.mark.asyncio
async def test_generate_workflow_entities(n8n_auth_config):
    """Test generating workflow entities from API response."""
    source = await N8nSource.create(n8n_auth_config, None)

    # Mock the HTTP client
    mock_client = AsyncMock()
    mock_response = MagicMock()
    mock_response.json.return_value = MOCK_WORKFLOWS_RESPONSE
    mock_response.raise_for_status = MagicMock()
    mock_client.get.return_value = mock_response

    # Mock _get_with_auth to return our mock data
    source._get_with_auth = AsyncMock(return_value=MOCK_WORKFLOWS_RESPONSE)

    # Generate entities
    workflows = []
    async for workflow in source._generate_workflow_entities(mock_client):
        workflows.append(workflow)

    # Verify we got 2 workflows
    assert len(workflows) == 2

    # Verify first workflow
    wf1 = workflows[0]
    assert wf1.entity_id == "1"
    assert wf1.name == "Customer Onboarding Workflow"
    assert wf1.active is True
    assert wf1.tags == ["customer", "onboarding"]
    assert len(wf1.nodes) == 2
    assert wf1.nodes[0]["name"] == "Webhook"
    assert wf1.version_id == "v1"

    # Verify second workflow
    wf2 = workflows[1]
    assert wf2.entity_id == "2"
    assert wf2.name == "Data Sync Workflow"
    assert wf2.active is False
    assert wf2.tags == ["data-sync"]  # Extracted from tag object
    assert len(wf2.nodes) == 2


@pytest.mark.asyncio
async def test_generate_execution_entities_success(n8n_auth_config):
    """Test generating execution entities with successful executions."""
    source = await N8nSource.create(n8n_auth_config, None)

    # Mock the HTTP client
    mock_client = AsyncMock()
    source._get_with_auth = AsyncMock(return_value=MOCK_EXECUTIONS_RESPONSE_SUCCESS)

    from airweave.platform.entities._base import Breadcrumb

    breadcrumb = Breadcrumb(entity_id="1")

    # Generate entities
    executions = []
    async for execution in source._generate_execution_entities(
        mock_client, "1", "Customer Onboarding Workflow", breadcrumb
    ):
        executions.append(execution)

    # Verify we got 2 executions
    assert len(executions) == 2

    # Verify first execution
    exec1 = executions[0]
    assert exec1.entity_id == "exec-1"
    assert exec1.workflow_id == "1"
    assert exec1.workflow_name == "Customer Onboarding Workflow"
    assert exec1.mode == "trigger"
    assert exec1.status == "success"
    assert exec1.finished is True
    assert exec1.error_message is None
    assert len(exec1.breadcrumbs) == 1


@pytest.mark.asyncio
async def test_generate_execution_entities_with_error(n8n_auth_config):
    """Test generating execution entities with failed execution."""
    source = await N8nSource.create(n8n_auth_config, None)

    # Mock the HTTP client
    mock_client = AsyncMock()
    source._get_with_auth = AsyncMock(return_value=MOCK_EXECUTIONS_RESPONSE_WITH_ERROR)

    from airweave.platform.entities._base import Breadcrumb

    breadcrumb = Breadcrumb(entity_id="1")

    # Generate entities
    executions = []
    async for execution in source._generate_execution_entities(
        mock_client, "1", "Customer Onboarding Workflow", breadcrumb
    ):
        executions.append(execution)

    # Verify we got 1 execution
    assert len(executions) == 1

    # Verify error execution
    exec1 = executions[0]
    assert exec1.entity_id == "exec-error-1"
    assert exec1.status == "error"
    assert exec1.error_message == "Connection timeout to external API"


@pytest.mark.asyncio
async def test_generate_entities_with_executions(n8n_auth_config, n8n_config_with_executions):
    """Test generate_entities includes both workflows and executions."""
    source = await N8nSource.create(n8n_auth_config, n8n_config_with_executions.model_dump())

    # Mock HTTP responses
    async def mock_get_with_auth(client, endpoint, params=None):
        if endpoint == "/workflows":
            return MOCK_WORKFLOWS_RESPONSE
        elif endpoint == "/executions":
            # Return executions for workflow 1
            if params and params.get("workflowId") == "1":
                return MOCK_EXECUTIONS_RESPONSE_SUCCESS
            # Return empty for workflow 2
            return {"data": []}
        return {}

    source._get_with_auth = mock_get_with_auth

    # Generate all entities
    entities = []
    async for entity in source.generate_entities():
        entities.append(entity)

    # Should have: 2 workflows + 2 executions for workflow 1 + 0 executions for workflow 2
    assert len(entities) == 4

    # Verify entity types
    from airweave.platform.entities.n8n import N8nWorkflowEntity, N8nExecutionEntity

    workflows = [e for e in entities if isinstance(e, N8nWorkflowEntity)]
    executions = [e for e in entities if isinstance(e, N8nExecutionEntity)]

    assert len(workflows) == 2
    assert len(executions) == 2


@pytest.mark.asyncio
async def test_generate_entities_without_executions(
    n8n_auth_config, n8n_config_without_executions
):
    """Test generate_entities excludes executions when configured."""
    source = await N8nSource.create(n8n_auth_config, n8n_config_without_executions.model_dump())

    # Mock HTTP responses
    source._get_with_auth = AsyncMock(return_value=MOCK_WORKFLOWS_RESPONSE)

    # Generate all entities
    entities = []
    async for entity in source.generate_entities():
        entities.append(entity)

    # Should only have 2 workflows, no executions
    assert len(entities) == 2

    # Verify all are workflows
    from airweave.platform.entities.n8n import N8nWorkflowEntity

    assert all(isinstance(e, N8nWorkflowEntity) for e in entities)


@pytest.mark.asyncio
async def test_validate_success(n8n_auth_config):
    """Test successful validation."""
    source = await N8nSource.create(n8n_auth_config, None)

    # Mock successful API call
    source._get_with_auth = AsyncMock(return_value={"data": []})

    result = await source.validate()
    assert result is True


@pytest.mark.asyncio
async def test_validate_http_error(n8n_auth_config):
    """Test validation with HTTP error."""
    source = await N8nSource.create(n8n_auth_config, None)

    # Mock HTTP error
    import httpx

    mock_response = MagicMock()
    mock_response.status_code = 401
    mock_response.text = "Unauthorized"

    source._get_with_auth = AsyncMock(side_effect=httpx.HTTPStatusError("Unauthorized", request=MagicMock(), response=mock_response))

    result = await source.validate()
    assert result is False


@pytest.mark.asyncio
async def test_validate_connection_error(n8n_auth_config):
    """Test validation with connection error."""
    source = await N8nSource.create(n8n_auth_config, None)

    # Mock connection error
    source._get_with_auth = AsyncMock(side_effect=Exception("Connection failed"))

    result = await source.validate()
    assert result is False


@pytest.mark.asyncio
async def test_url_normalization():
    """Test that URLs are properly normalized in N8nAuthConfig."""
    # Test trailing slash removal
    config1 = N8nAuthConfig(url="https://n8n.example.com/", api_key="test")
    assert config1.url == "https://n8n.example.com"

    # Test /api/v1 suffix removal
    config2 = N8nAuthConfig(url="https://n8n.example.com/api/v1", api_key="test")
    assert config2.url == "https://n8n.example.com"

    # Test both
    config3 = N8nAuthConfig(url="https://n8n.example.com/api/v1/", api_key="test")
    assert config3.url == "https://n8n.example.com"


@pytest.mark.asyncio
async def test_url_validation_errors():
    """Test URL validation errors."""
    from pydantic import ValidationError

    # Test missing protocol
    with pytest.raises(ValueError, match="must start with http"):
        N8nAuthConfig(url="n8n.example.com", api_key="test")

    # Test empty URL (Pydantic validates string length first)
    with pytest.raises(ValidationError):
        N8nAuthConfig(url="", api_key="test")
