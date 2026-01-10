"""n8n entity schemas.

Based on the n8n REST API reference, we define entity schemas for
n8n workflows and executions.

API Reference:
    https://docs.n8n.io/api/api-reference/
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from airweave.platform.entities._airweave_field import AirweaveField
from airweave.platform.entities._base import BaseEntity


class N8nWorkflowEntity(BaseEntity):
    """Schema for n8n workflow entities.

    Represents a workflow automation definition including all nodes,
    connections, and settings.

    Reference:
        https://docs.n8n.io/api/api-reference/
    """

    # Base fields are inherited and set during entity creation:
    # - entity_id (the workflow ID)
    # - breadcrumbs (empty - workflows are top-level)
    # - name (from workflow name)
    # - created_at (workflow creation timestamp)
    # - updated_at (workflow update timestamp)

    # API fields
    active: bool = AirweaveField(
        False, description="Whether the workflow is currently active", embeddable=True
    )
    tags: List[str] = AirweaveField(
        default_factory=list,
        description="Tags associated with the workflow for organization",
        embeddable=True,
    )
    nodes: List[Dict[str, Any]] = AirweaveField(
        default_factory=list,
        description="Array of node definitions that make up the workflow. "
        "Each node represents a specific action or data transformation. "
        "Searchable to find workflows using specific integrations.",
        embeddable=True,
    )
    connections: Dict[str, Any] = AirweaveField(
        default_factory=dict,
        description="Connection definitions between nodes showing data flow",
        embeddable=False,
    )
    settings: Optional[Dict[str, Any]] = AirweaveField(
        None,
        description="Workflow settings including execution mode, timezone, etc.",
        embeddable=False,
    )
    static_data: Optional[Dict[str, Any]] = AirweaveField(
        None,
        description="Static data stored with the workflow",
        embeddable=False,
    )
    version_id: Optional[str] = AirweaveField(
        None, description="Version identifier of the workflow", embeddable=False
    )


class N8nExecutionEntity(BaseEntity):
    """Schema for n8n execution (workflow run) entities.

    Represents a single execution of a workflow, including status,
    timing, and error information.

    Reference:
        https://docs.n8n.io/api/api-reference/
    """

    # Base fields are inherited and set during entity creation:
    # - entity_id (the execution ID)
    # - breadcrumbs (workflow breadcrumb)
    # - name (constructed from workflow name + execution time)
    # - created_at (execution start time)
    # - updated_at (execution finish time)

    # API fields
    workflow_id: str = AirweaveField(
        ..., description="ID of the workflow that was executed", embeddable=False
    )
    workflow_name: str = AirweaveField(
        ..., description="Name of the workflow that was executed", embeddable=True
    )
    mode: str = AirweaveField(
        ...,
        description="Execution mode: 'manual', 'trigger', 'retry', 'webhook', 'cli'",
        embeddable=True,
    )
    status: str = AirweaveField(
        ...,
        description="Execution status: 'success', 'error', 'waiting', 'running', 'canceled'",
        embeddable=True,
    )
    started_at: Optional[datetime] = AirweaveField(
        None, description="Timestamp when execution started", embeddable=False
    )
    stopped_at: Optional[datetime] = AirweaveField(
        None, description="Timestamp when execution finished", embeddable=False
    )
    finished: bool = AirweaveField(
        False, description="Whether the execution has completed", embeddable=True
    )
    error_message: Optional[str] = AirweaveField(
        None,
        description="Error message if execution failed. Searchable to find failed runs.",
        embeddable=True,
    )
    retry_of: Optional[str] = AirweaveField(
        None, description="ID of execution this is a retry of", embeddable=False
    )
    retry_success_id: Optional[str] = AirweaveField(
        None, description="ID of successful retry execution", embeddable=False
    )
    waiting_execution: Optional[Dict[str, Any]] = AirweaveField(
        None, description="Information about waiting execution state", embeddable=False
    )
