"""Configuration management for monke tests with Pydantic validation."""

import os
import re
import yaml
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, field_validator, model_validator, ConfigDict


class ComposioConfig(BaseModel):
    """Composio authentication configuration."""

    account_id: str = Field(..., description="Composio account ID (e.g., ca_xxx)")
    auth_config_id: str = Field(..., description="Composio auth config ID (e.g., ac_xxx)")

    @field_validator("account_id")
    @classmethod
    def validate_account_id(cls, v: str) -> str:
        """Validate Composio account ID format."""
        if not v.startswith("ca_"):
            raise ValueError(f"account_id must start with 'ca_', got: {v}")
        if len(v) < 5:
            raise ValueError(f"account_id too short: {v}")
        return v

    @field_validator("auth_config_id")
    @classmethod
    def validate_auth_config_id(cls, v: str) -> str:
        """Validate Composio auth config ID format."""
        if not v.startswith("ac_"):
            raise ValueError(f"auth_config_id must start with 'ac_', got: {v}")
        if len(v) < 5:
            raise ValueError(f"auth_config_id too short: {v}")
        return v


class ConnectorConfig(BaseModel):
    """Configuration for a specific connector with validation."""

    model_config = ConfigDict(extra="forbid")  # Fail on unknown fields

    name: str = Field(..., description="Connector instance name")
    type: str = Field(..., description="Connector type (e.g., github, asana)")
    auth_mode: str = Field("composio", description="Authentication mode: 'composio' or 'direct'")

    # Auth configuration (one of these must be set based on auth_mode)
    composio_config: Optional[ComposioConfig] = Field(
        None, description="Composio auth configuration"
    )
    auth_fields: Dict[str, str] = Field(
        default_factory=dict, description="Direct auth field mappings"
    )

    # Additional configuration
    config_fields: Dict[str, Any] = Field(
        default_factory=dict, description="Connector-specific config"
    )
    rate_limit_delay_ms: int = Field(1000, description="Rate limit delay in milliseconds")

    @field_validator("auth_mode")
    @classmethod
    def validate_auth_mode(cls, v: str) -> str:
        """Validate auth mode is supported."""
        if v not in ["composio", "direct"]:
            raise ValueError(f"auth_mode must be 'composio' or 'direct', got: {v}")
        return v

    @field_validator("auth_fields")
    @classmethod
    def validate_auth_fields(cls, v: Dict[str, str]) -> Dict[str, str]:
        """Ensure all env var names in direct auth start with MONKE_."""
        for field_name, env_var in v.items():
            if not env_var.startswith("MONKE_"):
                raise ValueError(
                    f"Environment variable '{env_var}' for field '{field_name}' "
                    f"must start with 'MONKE_'"
                )
        return v

    @model_validator(mode="after")
    def validate_auth_consistency(self) -> "ConnectorConfig":
        """Ensure auth configuration matches the auth_mode."""
        if self.auth_mode == "composio":
            if not self.composio_config:
                raise ValueError("auth_mode is 'composio' but composio_config is not provided")
            if self.auth_fields:
                raise ValueError(
                    "auth_mode is 'composio' but auth_fields are provided. "
                    "Cannot use both Composio and direct auth"
                )
        elif self.auth_mode == "direct":
            if self.composio_config:
                raise ValueError(
                    "auth_mode is 'direct' but composio_config is provided. "
                    "Cannot use both direct and Composio auth"
                )
            if not self.auth_fields:
                raise ValueError("auth_mode is 'direct' but no auth_fields provided")
        return self

    def resolve_auth_fields(self) -> Dict[str, Any]:
        """Resolve auth fields from environment variables for direct auth."""
        if self.auth_mode != "direct":
            return {}

        resolved = {}
        for field_name, env_var in self.auth_fields.items():
            value = os.getenv(env_var)
            if not value:
                raise ValueError(
                    f"Required environment variable '{env_var}' not set "
                    f"for field '{field_name}' in {self.type}"
                )
            resolved[field_name] = value
        return resolved

    def get_composio_credentials(self) -> tuple[str, str]:
        """Get Composio account and auth config IDs."""
        if self.auth_mode != "composio" or not self.composio_config:
            raise ValueError(f"Connector {self.type} is not configured for Composio auth")
        return self.composio_config.account_id, self.composio_config.auth_config_id


class DeletionConfig(BaseModel):
    """Configuration for incremental deletion testing."""

    partial_delete_count: int = Field(
        1, description="Number of entities to delete in partial phase"
    )
    verify_partial_deletion: bool = Field(True, description="Verify partial deletion worked")
    verify_remaining_entities: bool = Field(True, description="Verify remaining entities exist")
    verify_complete_deletion: bool = Field(True, description="Verify complete deletion worked")


class TestFlowConfig(BaseModel):
    """Configuration for test flow customization."""

    steps: List[str] = Field(
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
        ],
        description="Test flow steps to execute",
    )
    custom_steps: Dict[str, Dict[str, Any]] = Field(
        default_factory=dict, description="Custom step configurations"
    )


class TestConfig(BaseModel):
    """Main test configuration with full validation."""

    model_config = ConfigDict(extra="allow")

    name: str = Field(..., description="Test name")
    description: str = Field(..., description="Test description")
    connector: ConnectorConfig = Field(..., description="Connector configuration")
    test_flow: TestFlowConfig = Field(
        default_factory=TestFlowConfig, description="Test flow config"
    )
    deletion: DeletionConfig = Field(default_factory=DeletionConfig, description="Deletion config")
    entity_count: int = Field(10, ge=1, description="Number of entities to create")
    collection_config: Dict[str, Any] = Field(default_factory=dict, description="Collection config")
    verification_config: Dict[str, Any] = Field(
        default_factory=dict, description="Verification config"
    )
    cleanup_config: Dict[str, Any] = Field(default_factory=dict, description="Cleanup config")

    @classmethod
    def from_file(cls, config_path: str) -> "TestConfig":
        """Load and validate configuration from YAML file."""
        with open(config_path, "r") as f:
            content = f.read()

        # Process environment variable substitution (supports ${VAR} and ${VAR:-default})
        def substitute_env_vars(match):
            spec = match.group(1).strip()
            if ":-" in spec:
                var_name, default = spec.split(":-", 1)
                var_name = var_name.strip()
                default = default.strip()
                return os.getenv(var_name) or default
            var_name = spec
            return os.getenv(var_name, match.group(0))

        # Replace ${VAR_NAME} and ${VAR_NAME:-default} with actual values
        processed_content = re.sub(r"\$\{([^}]+)\}", substitute_env_vars, content)

        # Load the processed YAML
        data = yaml.safe_load(processed_content)

        # Map old collection/verification/cleanup keys to new names
        if "collection" in data:
            data["collection_config"] = data.pop("collection")
        if "verification" in data:
            data["verification_config"] = data.pop("verification")
        if "cleanup" in data:
            data["cleanup_config"] = data.pop("cleanup")

        # Create and validate the config
        return cls(**data)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TestConfig":
        """Create configuration from dictionary with validation."""
        # Map old keys to new names for backward compatibility
        data = data.copy()
        if "collection" in data:
            data["collection_config"] = data.pop("collection")
        if "verification" in data:
            data["verification_config"] = data.pop("verification")
        if "cleanup" in data:
            data["cleanup_config"] = data.pop("cleanup")

        return cls(**data)

    def is_composio_auth(self) -> bool:
        """Check if this test uses Composio authentication."""
        return self.connector.auth_mode == "composio"

    def is_direct_auth(self) -> bool:
        """Check if this test uses direct authentication."""
        return self.connector.auth_mode == "direct"

    def get_auth_credentials(self) -> Dict[str, Any]:
        """Get resolved authentication credentials based on auth mode."""
        if self.is_direct_auth():
            return self.connector.resolve_auth_fields()
        # For Composio, credentials are fetched by the broker
        return {}


# Legacy support - maintain backward compatibility
def load_test_config(config_path: str) -> TestConfig:
    """Load test configuration from file (backward compatibility)."""
    return TestConfig.from_file(config_path)
