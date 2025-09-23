"""Configuration management for monke tests."""

import yaml
from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class ConnectorConfig:
    """Configuration for a specific connector."""

    name: str
    type: str
    auth_fields: Dict[str, Any]
    config_fields: Dict[str, Any]
    rate_limit_delay_ms: int = 1000


@dataclass
class DeletionConfig:
    """Configuration for incremental deletion testing."""

    # Phase 1: Partial deletion
    partial_delete_count: int = 1  # Number of entities to delete during partial deletion

    # Verification settings
    verify_partial_deletion: bool = True
    verify_remaining_entities: bool = True
    verify_complete_deletion: bool = True


@dataclass
class TestFlowConfig:
    """Configuration for test flow customization."""

    steps: List[str] = field(
        default_factory=lambda: [
            "collection_cleanup",
            "cleanup",
            "create",
            "sync",
            "verify",
            "update",
            "sync",
            "verify",
            "partial_delete",
            "sync",
            "verify_partial_deletion",
            "verify_remaining_entities",
            "complete_delete",
            "sync",
            "verify_complete_deletion",
            "cleanup",
            "collection_cleanup",
        ]
    )
    custom_steps: Dict[str, Dict[str, Any]] = field(default_factory=dict)


@dataclass
class SyncConfig:
    """Configuration for sync behavior."""

    # If verification fails after sync, retry with force_sync
    auto_fallback_to_force: bool = True
    # Force certain sync steps to use force_sync (by step name or index)
    force_sync_steps: List[str] = field(default_factory=list)


@dataclass
class TestConfig:
    """Main test configuration."""

    name: str
    description: str
    connector: ConnectorConfig
    test_flow: TestFlowConfig
    deletion: DeletionConfig
    sync: SyncConfig
    collection_config: Dict[str, Any]
    verification_config: Dict[str, Any]
    cleanup_config: Dict[str, Any]
    entity_count: int = 10  # Number of entities to create for testing

    @classmethod
    def from_file(cls, config_path: str) -> "TestConfig":
        """Load configuration from YAML file."""
        with open(config_path, "r") as f:
            content = f.read()

        # Process environment variable substitution
        import os
        import re

        def substitute_env_vars(match):
            var_name = match.group(1)
            return os.getenv(var_name, match.group(0))

        # Replace ${VAR_NAME} with actual environment variable values
        processed_content = re.sub(r"\$\{([^}]+)\}", substitute_env_vars, content)

        # Load the processed YAML
        data = yaml.safe_load(processed_content)

        return cls(
            name=data["name"],
            description=data["description"],
            connector=ConnectorConfig(**data["connector"]),
            test_flow=TestFlowConfig(**data.get("test_flow", {})),
            deletion=DeletionConfig(**data.get("deletion", {})),
            sync=SyncConfig(**data.get("sync", {})),
            entity_count=data.get("entity_count", 10),
            collection_config=data.get("collection", {}),
            verification_config=data.get("verification", {}),
            cleanup_config=data.get("cleanup", {}),
        )

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TestConfig":
        """Create configuration from dictionary."""
        return cls(
            name=data["name"],
            description=data["description"],
            connector=ConnectorConfig(**data["connector"]),
            test_flow=TestFlowConfig(**data.get("test_flow", {})),
            deletion=DeletionConfig(**data.get("deletion", {})),
            sync=SyncConfig(**data.get("sync", {})),
            entity_count=data.get("entity_count", 10),
            collection_config=data.get("collection", {}),
            verification_config=data.get("verification", {}),
            cleanup_config=data.get("cleanup", {}),
        )
