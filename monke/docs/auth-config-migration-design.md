# Monke Configuration Design

## Executive Summary

This document outlines the design for centralizing all non-secret configuration (account IDs, auth config IDs, and config fields) into a single YAML file (`config.yml`) in the Monke testing framework. This file becomes the single source of truth for all connector configuration.

## Current State

### Problem
Currently, configuration is scattered across multiple sources:
- Account/auth config IDs in environment variables
- Test-specific config in individual YAML files
- No centralized way to manage connector-specific settings

## Proposed Solution

### New Structure
Single configuration file `monke/config.yml`:

```yaml
# monke/config.yml
# Single source of truth for all non-secret configuration
# This file can be safely committed to version control

# Global defaults
defaults:
  auth_provider: composio

# Per-connector configuration
connectors:
  # Composio-based connectors (with account/auth config IDs)
  asana:
    account_id: ca_-v_9I3Ig098s
    auth_config_id: ac_mPRmEEGQygEV
    config_fields:
      rate_limit_delay_ms: 2000

  github:
    account_id: ca_dIOSeizCPa2r
    auth_config_id: ac_wVC3o-VbiEvr
    config_fields:
      repo_name: "test-repo"

  notion:
    account_id: ca_1r92u-koLifQ
    auth_config_id: ac_oh6wodsWoVWB

  jira:
    account_id: ca_example_jira
    auth_config_id: ac_BCboB-rIS5fe
    config_fields:
      cloud_id: "abc-123-def"
      project_key: "TEST"

  # Direct auth connectors (using auth_fields)
  stripe:
    auth_fields:
      api_key: MONKE_STRIPE_API_KEY  # Maps to env var
    config_fields:
      test_mode: true

  bitbucket:
    auth_fields:
      username: MONKE_BITBUCKET_USERNAME
      app_password: MONKE_BITBUCKET_APP_PASSWORD
    config_fields:
      branch: "main"
```

### Configuration Resolution

The `config.yml` file is the **single source of truth**. No environment variables or other sources are consulted for these configurations:

- Account IDs and auth config IDs come exclusively from `config.yml`
- Config fields can be specified in `config.yml` and override test defaults
- The file is loaded once at startup and cached

## Implementation Plan

### 1. Create ConfigManager with Pydantic Validation (Singleton)
```python
# monke/core/config_manager.py
from typing import Dict, Any, Optional
from pathlib import Path
from pydantic import BaseModel, Field, validator
import yaml

class ConnectorConfig(BaseModel):
    """Validated configuration for a connector (supports both Composio and direct auth)."""
    account_id: Optional[str] = Field(None, description="Composio account ID")
    auth_config_id: Optional[str] = Field(None, description="Composio auth config ID")
    config_fields: Dict[str, Any] = Field(default_factory=dict, description="Additional config fields")
    auth_fields: Dict[str, str] = Field(default_factory=dict, description="Direct auth field mappings (field_name: env_var_name)")

    @validator("account_id")
    def validate_account_id(cls, v):
        """Validate Composio account ID format if provided."""
        if v and not v.startswith("ca_"):
            raise ValueError(f"account_id must start with 'ca_', got: {v}")
        if v and len(v) < 5:
            raise ValueError(f"account_id too short: {v}")
        return v

    @validator("auth_config_id")
    def validate_auth_config_id(cls, v):
        """Validate Composio auth config ID format if provided."""
        if v and not v.startswith("ac_"):
            raise ValueError(f"auth_config_id must start with 'ac_', got: {v}")
        if v and len(v) < 5:
            raise ValueError(f"auth_config_id too short: {v}")
        return v

    @validator("auth_fields")
    def validate_auth_fields(cls, v):
        """Ensure all env var names start with MONKE_."""
        for field_name, env_var in v.items():
            if not env_var.startswith("MONKE_"):
                raise ValueError(f"Environment variable '{env_var}' must start with 'MONKE_'")
        return v

    @validator("auth_config_id", always=True)
    def validate_auth_mode(cls, v, values):
        """Ensure connector uses either Composio auth OR direct auth, not both."""
        account_id = values.get("account_id")
        auth_fields = values.get("auth_fields", {})

        # Check for Composio auth completeness
        if (account_id and not v) or (not account_id and v):
            raise ValueError("Both account_id and auth_config_id must be set for Composio auth")

        # Ensure not mixing auth modes
        if (account_id or v) and auth_fields:
            raise ValueError("Cannot use both Composio auth (account_id/auth_config_id) and direct auth (auth_fields)")

        return v

class ConfigModel(BaseModel):
    """Root configuration model with validation."""
    defaults: Dict[str, str] = Field(default_factory=dict)
    connectors: Dict[str, ConnectorConfig]

    @validator("defaults")
    def validate_defaults(cls, v):
        if "auth_provider" in v and v["auth_provider"] not in ["composio"]:
            raise ValueError("Only 'composio' auth provider is currently supported")
        return v

class ConfigManager:
    """Singleton configuration manager - lazy loads connector configs."""
    _instance: Optional["ConfigManager"] = None

    def __new__(cls, config_path: str = "config.yml"):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialize(config_path)
        return cls._instance

    def _initialize(self, config_path: str):
        """Load configuration file but don't validate all connectors yet."""
        config_file = Path(__file__).parent.parent / config_path
        if not config_file.exists():
            raise FileNotFoundError(f"Config file not found: {config_file}")

        with open(config_file, "r") as f:
            self._raw_config = yaml.safe_load(f)

        self._defaults = self._raw_config.get("defaults", {})
        self._validated_connectors = {}  # Cache for validated configs

    def get_connector_config(self, connector_name: str) -> ConnectorConfig:
        """Get validated configuration for a specific connector (lazy validation)."""
        # Check cache first
        if connector_name in self._validated_connectors:
            return self._validated_connectors[connector_name]

        # Check if connector exists in raw config
        connectors = self._raw_config.get("connectors", {})
        if connector_name not in connectors:
            # Return empty config for connectors not in config.yml
            empty_config = ConnectorConfig()
            self._validated_connectors[connector_name] = empty_config
            return empty_config

        # Validate and cache the connector config
        try:
            config = ConnectorConfig(**connectors[connector_name])
            self._validated_connectors[connector_name] = config
            return config
        except Exception as e:
            raise ValueError(f"Invalid configuration for connector '{connector_name}': {e}")

    def get_account_id(self, connector_name: str) -> Optional[str]:
        """Get validated account ID for connector (None for direct auth)."""
        return self.get_connector_config(connector_name).account_id

    def get_auth_config_id(self, connector_name: str) -> Optional[str]:
        """Get validated auth config ID for connector (None for direct auth)."""
        return self.get_connector_config(connector_name).auth_config_id

    def get_auth_fields(self, connector_name: str) -> Dict[str, str]:
        """Get direct auth field mappings for connector."""
        return self.get_connector_config(connector_name).auth_fields

    def is_composio_auth(self, connector_name: str) -> bool:
        """Check if connector uses Composio auth."""
        config = self.get_connector_config(connector_name)
        return bool(config.account_id and config.auth_config_id)

    def is_direct_auth(self, connector_name: str) -> bool:
        """Check if connector uses direct auth."""
        config = self.get_connector_config(connector_name)
        return bool(config.auth_fields)

    def get_config_fields(self, connector_name: str) -> Dict[str, Any]:
        """Get additional config fields for connector."""
        return self.get_connector_config(connector_name).config_fields

    def get_defaults(self) -> Dict[str, str]:
        """Get default configuration."""
        return self._defaults

# Module-level singleton instance
config_manager = ConfigManager()
```

### 2. Update credentials_resolver.py
```python
# Modified monke/auth/credentials_resolver.py
from monke.core.config_manager import config_manager  # Import singleton
import os

def _make_broker(source_short_name: str) -> Optional[BaseAuthBroker]:
    """Create auth broker using config.yml settings, or None for direct auth."""
    if not config_manager.is_composio_auth(source_short_name):
        return None  # Direct auth - credentials from env vars

    account_id = config_manager.get_account_id(source_short_name)
    auth_config_id = config_manager.get_auth_config_id(source_short_name)

    # API key still comes from environment
    api_key = os.getenv("MONKE_COMPOSIO_API_KEY")
    if not api_key:
        raise ValueError("MONKE_COMPOSIO_API_KEY not set in environment")

    provider = config_manager.get_defaults().get("auth_provider", "composio")
    if provider == "composio":
        return ComposioBroker(
            api_key=api_key,
            account_id=account_id,
            auth_config_id=auth_config_id
        )
    raise ValueError(f"Unsupported auth provider: {provider}")

def _resolve_direct_auth(source_short_name: str) -> Dict[str, Any]:
    """Resolve direct auth credentials from environment variables."""
    auth_fields = config_manager.get_auth_fields(source_short_name)
    if not auth_fields:
        return {}  # No direct auth configured

    credentials = {}
    for field_name, env_var in auth_fields.items():
        value = os.getenv(env_var)
        if not value:
            raise ValueError(f"Required environment variable '{env_var}' not set for {source_short_name}")
        credentials[field_name] = value

    return credentials

async def resolve_credentials(
    connector_short_name: str, provided_auth_fields: Optional[Dict[str, Any]]
) -> Dict[str, Any]:
    """Resolve credentials - provided fields take precedence, then broker/direct auth."""
    if provided_auth_fields:
        return provided_auth_fields

    # Try Composio auth
    broker = _make_broker(connector_short_name)
    if broker:
        return await broker.get_credentials(connector_short_name)

    # Try direct auth
    return _resolve_direct_auth(connector_short_name)
```

### 3. Update TestFlow Class
```python
# Modified monke/core/flow.py
from monke.core.config_manager import config_manager  # Import singleton

class TestFlow:
    def __init__(self, config: TestConfig):
        # Merge config fields from config.yml into test config
        try:
            config_fields = config_manager.get_config_fields(config.connector.type)
            self.config.connector.config_fields.update(config_fields)
        except ValueError:
            # Connector not in config.yml, use test defaults only
            pass
```

### 4. Update Runner
```python
# Modified monke/runner.py
# No need to explicitly load - singleton is created on import
from monke.core.config_manager import config_manager

async def run_single_test(config_path: str, run_id: str) -> bool:
    """Run a single test configuration."""
    logger = get_logger("monke_runner")

    # Config manager is already initialized as singleton
    logger.info(f"Using config from: config.yml")

    try:
        runner = TestRunner(config_path, run_id=run_id)
        # TestRunner internally uses the singleton config_manager
        results = await runner.run_tests()
        # ...
```

## File Changes Summary

### New Files
1. `monke/config.yml` - Main configuration file (single source of truth)
2. `monke/core/config_manager.py` - Singleton configuration manager with Pydantic validation

### Modified Files
1. `monke/auth/credentials_resolver.py` - Remove ALL env var checks for IDs, use singleton config_manager
2. `monke/auth/broker.py` - Remove env var fallbacks, only accept config from config_manager
3. `monke/core/flow.py` - Import and use singleton config_manager
4. `monke/runner.py` - Import singleton, remove env-based config loading
5. `monke/core/runner.py` - Remove config passing, use singleton

### Removed Components
1. **Environment variable lookups** - Remove ALL checks for:
   - `{CONNECTOR}_AUTH_PROVIDER_ACCOUNT_ID`
   - `{CONNECTOR}_AUTH_PROVIDER_AUTH_CONFIG_ID`
   - `DM_AUTH_PROVIDER_ACCOUNT_ID`
   - `DM_AUTH_PROVIDER_AUTH_CONFIG_ID`
2. **Fallback mechanisms** in broker.py and credentials_resolver.py
3. **All Azure Key Vault support** - No longer needed

### Simplified .env File
```bash
# Only actual secrets remain (all prefixed with MONKE_)
MONKE_COMPOSIO_API_KEY=ak_JGlPB17kCHI0tcAQS6-x  # Composio API key
OPENAI_API_KEY=sk-proj-xxx                       # For content generation (keep as-is for LLM client)

# Direct auth credentials (referenced in config.yml auth_fields)
MONKE_STRIPE_API_KEY=sk_test_xxx
MONKE_BITBUCKET_USERNAME=john.doe
MONKE_BITBUCKET_APP_PASSWORD=app-pwd-123
```

## Config Field Merging Strategy

When a connector has `config_fields` in `config.yml`:
1. Load base config from test YAML (e.g., `configs/asana.yaml`)
2. Merge/override with fields from `config.yml`
3. Config fields in `config.yml` take precedence

Example flow:
```python
# configs/asana.yaml has:
config_fields:
  rate_limit_delay_ms: 1000

# config.yml has:
asana:
  config_fields:
    rate_limit_delay_ms: 2000  # This wins
    custom_field: "value"       # This is added
```

## Usage Examples

### Basic Connector Config
```yaml
connectors:
  github:
    account_id: ca_github_123
    auth_config_id: ac_github_456
```

### With Config Fields
```yaml
connectors:
  jira:
    account_id: ca_jira_789
    auth_config_id: ac_jira_012
    config_fields:
      cloud_id: "abc-123"
      project_key: "TEST"
      max_issues: 100
```

### Direct Auth Examples
```yaml
connectors:
  # Direct auth with single credential
  stripe:
    auth_fields:
      api_key: MONKE_STRIPE_API_KEY
    config_fields:
      test_mode: true

  # Direct auth with multiple credentials
  bitbucket:
    auth_fields:
      username: MONKE_BITBUCKET_USERNAME
      app_password: MONKE_BITBUCKET_APP_PASSWORD
    config_fields:
      branch: "main"

  # Connector not in config.yml at all:
  # - Returns empty config
  # - Can still work if auth provided in test YAML
```
