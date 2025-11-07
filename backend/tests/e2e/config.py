"""
Test configuration using Pydantic Settings.

Manages all environment variables and test configuration in a type-safe way.
"""

from typing import Optional, Literal
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, field_validator


class TestSettings(BaseSettings):
    """Test configuration from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env.test",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Test environment
    TEST_ENV: Literal["local", "dev", "prod"] = Field(
        default="local", description="Test environment to run against"
    )

    # API Configuration
    AIRWEAVE_API_KEY: Optional[str] = Field(
        default=None, description="API key for dev/prod environments"
    )

    # Required credentials
    TEST_STRIPE_API_KEY: str = Field(description="Stripe API key for payment testing")

    OPENAI_API_KEY: Optional[str] = Field(
        default=None, description="OpenAI API key for embeddings (optional)"
    )

    # OAuth test tokens
    TEST_NOTION_TOKEN: str = Field(description="Notion OAuth token for injection")

    TEST_GOOGLE_CLIENT_ID: str = Field(description="Google OAuth client ID for BYOC")

    TEST_GOOGLE_CLIENT_SECRET: str = Field(description="Google OAuth client secret for BYOC")

    TEST_PIPEDREAM_PROJECT_ID: str = Field(description="Pipedream project ID for BYOC")
    TEST_PIPEDREAM_ACCOUNT_ID: str = Field(description="Pipedream account ID for BYOC")
    TEST_PIPEDREAM_EXTERNAL_USER_ID: str = Field(description="Pipedream external user ID for BYOC")
    TEST_PIPEDREAM_CLIENT_ID: str = Field(description="Pipedream client ID for BYOC")
    TEST_PIPEDREAM_CLIENT_SECRET: str = Field(description="Pipedream client secret for BYOC")

    TEST_TRELLO_CONSUMER_KEY: str = Field(description="Trello consumer key for BYOC")
    TEST_TRELLO_CONSUMER_SECRET: str = Field(description="Trello consumer secret for BYOC")

    # Auth provider configuration
    TEST_AUTH_PROVIDER_NAME: Literal["composio"] = Field(
        default="composio",
        description="Auth provider name (must be 'composio')",
    )

    TEST_COMPOSIO_API_KEY: str = Field(description="Composio API key")

    # Asana Composio configuration
    TEST_COMPOSIO_ASANA_AUTH_CONFIG_ID: Optional[str] = Field(
        default=None, description="Composio auth config ID for Asana"
    )
    TEST_COMPOSIO_ASANA_ACCOUNT_ID: Optional[str] = Field(
        default=None, description="Composio account ID for Asana"
    )

    # Gmail Composio configuration
    TEST_COMPOSIO_GMAIL_AUTH_CONFIG_ID: Optional[str] = Field(
        default=None, description="Composio auth config ID for Gmail"
    )
    TEST_COMPOSIO_GMAIL_ACCOUNT_ID: Optional[str] = Field(
        default=None, description="Composio account ID for Gmail"
    )

    # Todoist Composio configuration
    TEST_COMPOSIO_TODOIST_AUTH_CONFIG_ID: Optional[str] = Field(
        default=None, description="Composio auth config ID for Todoist"
    )
    TEST_COMPOSIO_TODOIST_ACCOUNT_ID: Optional[str] = Field(
        default=None, description="Composio account ID for Todoist"
    )

    # Notion Composio configuration (connection-level rate limiting tests)
    TEST_COMPOSIO_NOTION_AUTH_CONFIG_ID_1: Optional[str] = Field(
        default=None, description="Composio auth config ID for Notion account 1"
    )
    TEST_COMPOSIO_NOTION_ACCOUNT_ID_1: Optional[str] = Field(
        default=None, description="Composio account ID for Notion account 1"
    )
    TEST_COMPOSIO_NOTION_AUTH_CONFIG_ID_2: Optional[str] = Field(
        default=None, description="Composio auth config ID for Notion account 2"
    )
    TEST_COMPOSIO_NOTION_ACCOUNT_ID_2: Optional[str] = Field(
        default=None, description="Composio account ID for Notion account 2"
    )

    # Google Drive Composio configuration (org-level rate limiting tests)
    TEST_COMPOSIO_GOOGLE_DRIVE_AUTH_CONFIG_ID_1: Optional[str] = Field(
        default=None, description="Composio auth config ID for Google Drive account 1"
    )
    TEST_COMPOSIO_GOOGLE_DRIVE_ACCOUNT_ID_1: Optional[str] = Field(
        default=None, description="Composio account ID for Google Drive account 1"
    )
    TEST_COMPOSIO_GOOGLE_DRIVE_AUTH_CONFIG_ID_2: Optional[str] = Field(
        default=None, description="Composio auth config ID for Google Drive account 2"
    )
    TEST_COMPOSIO_GOOGLE_DRIVE_ACCOUNT_ID_2: Optional[str] = Field(
        default=None, description="Composio account ID for Google Drive account 2"
    )

    # Pipedream configuration for rate limit testing (separate project from regular tests)
    TEST_PIPEDREAM_RATE_LIMIT_CLIENT_ID: Optional[str] = Field(
        default=None, description="Pipedream client ID for rate limit tests"
    )
    TEST_PIPEDREAM_RATE_LIMIT_CLIENT_SECRET: Optional[str] = Field(
        default=None, description="Pipedream client secret for rate limit tests"
    )
    TEST_PIPEDREAM_RATE_LIMIT_PROJECT_ID: Optional[str] = Field(
        default=None, description="Pipedream project ID for rate limit tests"
    )
    
    # Pipedream configuration for proxy testing
    TEST_PIPEDREAM_GOOGLE_DRIVE_DEFAULT_OAUTH_ACCOUNT_ID: Optional[str] = Field(
        default=None, description="Pipedream account ID for Google Drive (default OAuth - proxy mode)"
    )
    TEST_PIPEDREAM_GOOGLE_DRIVE_DEFAULT_OAUTH_EXTERNAL_USER_ID: Optional[str] = Field(
        default=None, description="External user ID for Google Drive default OAuth"
    )
    TEST_PIPEDREAM_GOOGLE_DRIVE_CUSTOM_OAUTH_ACCOUNT_ID: Optional[str] = Field(
        default=None, description="Pipedream account ID for Google Drive (custom OAuth - direct mode)"
    )
    TEST_PIPEDREAM_GOOGLE_DRIVE_CUSTOM_OAUTH_EXTERNAL_USER_ID: Optional[str] = Field(
        default=None, description="External user ID for Google Drive custom OAuth"
    )
    TEST_PIPEDREAM_NOTION_DEFAULT_OAUTH_ACCOUNT_ID: Optional[str] = Field(
        default=None, description="Pipedream account ID for Notion (default OAuth - proxy mode)"
    )
    TEST_PIPEDREAM_NOTION_DEFAULT_OAUTH_EXTERNAL_USER_ID: Optional[str] = Field(
        default=None, description="External user ID for Notion default OAuth"
    )

    # Test behavior settings
    SKIP_STARTUP: bool = Field(
        default=False, description="Skip running start.sh and container health checks"
    )

    STRICT_MODE: bool = Field(
        default=False, description="Require all optional environment variables"
    )

    # Timeouts
    DEFAULT_TIMEOUT: int = Field(
        default=30, description="Default timeout for API requests in seconds"
    )

    SYNC_TIMEOUT: int = Field(default=60, description="Timeout for sync operations in seconds")

    # Parallelization settings
    MAX_WORKERS: int = Field(default=4, description="Maximum number of parallel workers for tests")

    @field_validator("TEST_STRIPE_API_KEY")
    @classmethod
    def validate_stripe_key(cls, v: str) -> str:
        """Validate Stripe API key format."""
        if not v.startswith("sk_"):
            raise ValueError("Stripe API key must start with 'sk_'")
        if len(v) < 10:
            raise ValueError("Stripe API key seems too short")
        return v

    @field_validator("TEST_AUTH_PROVIDER_NAME")
    @classmethod
    def validate_auth_provider(cls, v: str) -> str:
        """Validate auth provider is composio."""
        if v != "composio":
            raise ValueError(f"TEST_AUTH_PROVIDER_NAME must be 'composio', got '{v}'")
        return v

    @property
    def api_url(self) -> str:
        """Get API URL based on environment."""
        urls = {
            "local": "http://localhost:8001",
            "dev": "https://api.dev-airweave.com",
            "prod": "https://api.airweave.ai",
        }
        return urls[self.TEST_ENV]

    @property
    def requires_api_key(self) -> bool:
        """Check if environment requires API key."""
        return self.TEST_ENV in ["dev", "prod"]

    @property
    def is_local(self) -> bool:
        """Check if running in local environment."""
        return self.TEST_ENV == "local"

    @property
    def qdrant_url(self) -> str:
        """Get Qdrant URL for local testing only."""
        return "http://localhost:6333"

    @property
    def api_headers(self) -> dict:
        """Get API headers with authentication if needed."""
        headers = {"Content-Type": "application/json", "accept": "application/json"}

        if self.requires_api_key and self.AIRWEAVE_API_KEY:
            headers["x-api-key"] = self.AIRWEAVE_API_KEY

        return headers

    # Convenience properties with lowercase names for backwards compatibility
    @property
    def test_env(self) -> str:
        return self.TEST_ENV

    @property
    def test_notion_token(self) -> str:
        return self.TEST_NOTION_TOKEN

    @property
    def default_timeout(self) -> int:
        return self.DEFAULT_TIMEOUT

    @property
    def sync_timeout(self) -> int:
        return self.SYNC_TIMEOUT


# Global instance
settings = TestSettings()
