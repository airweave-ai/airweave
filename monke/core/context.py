"""Test execution context - holds runtime state separate from configuration."""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class TestContext:
    """Runtime context for test execution.

    This holds all the runtime state that gets created during test execution,
    keeping it separate from the configuration.
    """

    # Core services
    bongo: Optional[Any] = None
    airweave_client: Optional[Any] = None

    # Infrastructure IDs
    collection_id: Optional[str] = None
    collection_readable_id: Optional[str] = None
    source_connection_id: Optional[str] = None
    sync_id: Optional[str] = None  # From source connection for raw data verification

    # Entity tracking
    created_entities: List[Dict[str, Any]] = field(default_factory=list)
    updated_entities: List[Dict[str, Any]] = field(default_factory=list)
    partially_deleted_entities: List[Dict[str, Any]] = field(default_factory=list)
    remaining_entities: List[Dict[str, Any]] = field(default_factory=list)

    # Sync tracking
    last_sync_job_id: Optional[str] = None

    # Metrics and warnings
    metrics: Dict[str, Any] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)
