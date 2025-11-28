"""Auth config."""

from typing import Optional

from pydantic import Field, field_validator, model_validator

from airweave.platform.configs._base import BaseConfig


class AuthConfig(BaseConfig):
    """Authentication config schema."""

    pass


class OAuth2AuthConfig(AuthConfig):
    """Base OAuth2 authentication config.

    This is for OAuth2 sources that only have access tokens (no refresh).
    These sources require going through the OAuth flow and cannot be created via API.
    """

    access_token: str = Field(
        title="Access Token",
        description="The access token for the OAuth2 app. This is obtained through the OAuth flow.",
    )


class OAuth2WithRefreshAuthConfig(OAuth2AuthConfig):
    """OAuth2 authentication config with refresh token support.

    These sources support refresh tokens for long-lived access.
    They require going through the OAuth flow and cannot be created via API.
    """

    refresh_token: str = Field(
        title="Refresh Token",
        description="The refresh token for the OAuth2 app. "
        "This is obtained through the OAuth flow.",
    )


class OAuth2BYOCAuthConfig(OAuth2WithRefreshAuthConfig):
    """OAuth2 Bring Your Own Credentials authentication config.

    These are OAuth2 sources where users provide their own client credentials.
    While they still require OAuth flow, users need to configure client_id/client_secret first.
    """

    client_id: Optional[str] = Field(
        default=None, title="Client ID", description="Your OAuth application's client ID"
    )
    client_secret: Optional[str] = Field(
        default=None, title="Client Secret", description="Your OAuth application's client secret"
    )


class APIKeyAuthConfig(AuthConfig):
    """API key authentication credentials schema."""

    api_key: str = Field(title="API Key", description="The API key for the API")


class OpenAIAuthConfig(APIKeyAuthConfig):
    """OpenAI authentication credentials schema."""

    api_key: str = Field(title="API Key", description="The API key for the OpenAI account")


class URLAndAPIKeyAuthConfig(AuthConfig):
    """URL and API key authentication credentials schema."""

    url: str = Field(title="URL", description="The URL of the API")
    api_key: str = Field(title="API Key", description="The API key for the API")


# Source auth configs


# Source database-specific auth configs
class ODBCAuthConfig(AuthConfig):
    """ODBC authentication credentials schema."""

    host: str = Field(title="Host", description="The host of the ODBC database")
    port: int = Field(title="Port", description="The port of the ODBC database")
    database: str = Field(title="Database", description="The name of the ODBC database")
    username: str = Field(title="Username", description="The username for the ODBC database")
    password: str = Field(title="Password", description="The password for the ODBC database")
    schema: str = Field(title="Schema", description="The schema of the ODBC database")
    tables: str = Field(title="Tables", description="The tables of the ODBC database")


class BaseDatabaseAuthConfig(AuthConfig):
    """Base database authentication configuration."""

    host: str = Field(
        title="Host",
        description="The host of the PostgreSQL database",
        min_length=1,
    )
    port: int = Field(
        title="Port",
        description="The port of the PostgreSQL database",
        gt=0,
        le=65535,
    )
    database: str = Field(
        title="Database",
        description="The name of the PostgreSQL database",
        min_length=1,
    )
    user: str = Field(
        title="Username",
        description="The username for the PostgreSQL database",
        min_length=1,
    )
    password: str = Field(
        title="Password",
        description="The password for the PostgreSQL database",
        min_length=1,
    )
    schema: str = Field(
        default="public",
        title="Schema",
        description="The schema of the PostgreSQL database",
        min_length=1,
    )
    tables: str = Field(
        default="*",
        title="Tables",
        description=(
            "Comma separated list of tables and views to sync. For example, 'users,orders'. "
            "For all tables (not views), use '*'."
        ),
        min_length=1,
    )

    @field_validator("host")
    @classmethod
    def validate_host(cls, v: str) -> str:
        """Validate database host."""
        if not v or not v.strip():
            raise ValueError("Host is required")
        v = v.strip()
        # Host should not include protocol
        if v.startswith(("http://", "https://", "postgresql://", "mysql://")):
            raise ValueError(
                "Host should not include protocol (e.g., use 'localhost' not 'postgresql://localhost')"
            )
        return v

    @field_validator("port")
    @classmethod
    def validate_port(cls, v: int) -> int:
        """Validate database port."""
        if v <= 0 or v > 65535:
            raise ValueError("Port must be between 1 and 65535")
        return v

    @field_validator("database", "user", "password", "schema")
    @classmethod
    def validate_not_empty(cls, v: str, info) -> str:
        """Validate that required fields are not empty."""
        if not v or not v.strip():
            field_name = info.field_name.replace("_", " ").title()
            raise ValueError(f"{field_name} is required")
        return v.strip()

    @field_validator("tables")
    @classmethod
    def validate_tables(cls, v: str) -> str:
        """Validate tables list."""
        if not v or not v.strip():
            raise ValueError("Tables field is required (use '*' for all tables)")
        v = v.strip()
        # Allow * for all tables, or comma-separated list
        if v == "*":
            return v
        # Split by comma and validate each table name
        tables = [t.strip() for t in v.split(",")]
        for table in tables:
            if not table:
                raise ValueError("Empty table name in list")
            # Basic validation - alphanumeric, underscore, and dot (for schema.table)
            if not all(c.isalnum() or c in "._" for c in table):
                raise ValueError(
                    f"Invalid table name '{table}'. "
                    "Use alphanumeric characters, underscores, and dots only"
                )
        return v

    class Config:
        """Pydantic config."""

        json_schema_extra = {
            "example": {
                "host": "localhost",
                "port": 5432,
                "database": "mydb",
                "user": "postgres",
                "password": "secret",
                "schema": "public",
                "tables": "users,orders",
            }
        }


# Destination auth configs
class WeaviateAuthConfig(AuthConfig):
    """Weaviate authentication credentials schema."""

    cluster_url: str = Field(title="Cluster URL", description="The URL of the Weaviate cluster")
    api_key: str = Field(title="API Key", description="The API key for the Weaviate cluster")


class QdrantAuthConfig(AuthConfig):
    """Qdrant authentication credentials schema."""

    url: str = Field(title="URL", description="The URL of the Qdrant service")
    api_key: str = Field(
        title="API Key",
        description="The API key for the Qdrant service (if required)",
    )


class Neo4jAuthConfig(AuthConfig):
    """Neo4j authentication credentials schema."""

    uri: str = Field(title="URI", description="The URI of the Neo4j database")
    username: str = Field(title="Username", description="The username for the Neo4j database")
    password: str = Field(title="Password", description="The password for the Neo4j database")


# AUTH CONFIGS FOR ALL SOURCES


class AirtableAuthConfig(OAuth2WithRefreshAuthConfig):
    """Airtable authentication credentials schema."""

    # Inherits refresh_token and access_token from OAuth2WithRefreshAuthConfig


class AsanaAuthConfig(OAuth2WithRefreshAuthConfig):
    """Asana authentication credentials schema."""

    # Inherits refresh_token and access_token from OAuth2WithRefreshAuthConfig


class AttioAuthConfig(APIKeyAuthConfig):
    """Attio authentication credentials schema."""

    api_key: str = Field(
        title="API Key",
        description="The API key for Attio. Generate one in Workspace Settings > Developers.",
        min_length=10,
    )

    @field_validator("api_key")
    @classmethod
    def validate_api_key(cls, v: str) -> str:
        """Validate Attio API key."""
        if not v or not v.strip():
            raise ValueError("API key is required")
        v = v.strip()
        # Check for common placeholder values
        placeholder_values = ["your-api-key", "xxx", "api-key-here", "paste-here", "placeholder"]
        if any(placeholder in v.lower() for placeholder in placeholder_values):
            raise ValueError("Please enter your actual API key, not a placeholder value")
        return v


class BitbucketAuthConfig(AuthConfig):
    """Bitbucket authentication credentials schema.

    Requires API token authentication with Atlassian email.
    """

    access_token: str = Field(
        title="API Token",
        description=(
            "Create a Bitbucket API token "
            "[here](https://id.atlassian.com/manage-profile/security/api-tokens) "
            "with scopes:\n"
            "- account\n"
            "- read:user:bitbucket\n"
            "- read:workspace:bitbucket\n"
            "- read:repository:bitbucket\n\n"
            "When using this, also provide your Atlassian email address."
        ),
        min_length=10,
    )

    email: str = Field(
        title="Email",
        description="Your Atlassian email address (required for API token authentication)",
    )

    workspace: str = Field(
        title="Workspace",
        description="Bitbucket workspace slug (e.g., 'my-workspace')",
        min_length=1,
        pattern=r"^[a-zA-Z0-9_-]+$",
    )
    repo_slug: Optional[str] = Field(
        default="",
        title="Repository Slug",
        description="Specific repository to sync (e.g., 'my-repo'). "
        "If empty, syncs all repositories in the workspace.",
        pattern=r"^[a-zA-Z0-9_.-]*$",
    )

    @model_validator(mode="after")
    def validate_required_fields(self):
        """Ensure required authentication fields are provided."""
        if not self.access_token or not self.access_token.strip():
            raise ValueError("API token is required")
        if not self.email or not self.email.strip():
            raise ValueError("Atlassian email is required")
        return self


class BoxAuthConfig(OAuth2WithRefreshAuthConfig):
    """Box authentication credentials schema."""

    # Inherits refresh_token and access_token from OAuth2WithRefreshAuthConfig


class ClickUpAuthConfig(OAuth2AuthConfig):
    """Clickup authentication credentials schema."""

    # Inherits access_token from OAuth2AuthConfig


class ConfluenceAuthConfig(OAuth2WithRefreshAuthConfig):
    """Confluence authentication credentials schema."""

    # Inherits refresh_token and access_token from OAuth2WithRefreshAuthConfig


class DropboxAuthConfig(OAuth2BYOCAuthConfig):
    """Dropbox authentication credentials schema."""

    # Inherits client_id, client_secret, refresh_token and access_token from OAuth2BYOCAuthConfig


class ElasticsearchAuthConfig(AuthConfig):
    """Elasticsearch authentication credentials schema."""

    host: str = Field(
        title="Host",
        description="The full URL to the Elasticsearch server, including http or https",
    )
    port: int = Field(title="Port", description="The port of the elasticsearch database")
    indices: str = Field(
        default="*",
        title="Indices",
        description="Comma separated list of indices to sync. Use '*' for all indices.",
    )
    fields: str = Field(
        default="*",
        title="Fields",
        description="List of fields to sync from each document. For all fields, use '*'",
    )

    @field_validator("host")
    @classmethod
    def validate_host(cls, v: str) -> str:
        """Validate that the host URL starts with http:// or https://."""
        if not v.startswith(("http://", "https://")):
            raise ValueError("Host must start with http:// or https://")
        return v


class GitHubAuthConfig(AuthConfig):
    """GitHub authentication credentials schema."""

    personal_access_token: str = Field(
        title="Personal Access Token",
        description="GitHub PAT with read rights (code, contents, metadata) to the repository",
        min_length=4,
    )

    @field_validator("personal_access_token")
    @classmethod
    def validate_personal_access_token(cls, v: str) -> str:
        """Validate GitHub personal access token format."""
        if not v or not v.strip():
            raise ValueError("Personal access token is required")
        v = v.strip()
        # GitHub classic tokens start with ghp_, fine-grained tokens start with github_pat_
        # Also allow legacy tokens (40 char hex)
        if not (
            v.startswith("ghp_")
            or v.startswith("github_pat_")
            or v.startswith("gho_")
            or (len(v) == 40 and all(c in "0123456789abcdef" for c in v.lower()))
        ):
            raise ValueError(
                "Invalid token format. Expected format: "
                "ghp_... or github_pat_... or gho_... or 40-character hex"
            )
        return v


class GmailAuthConfig(OAuth2BYOCAuthConfig):
    """Gmail authentication credentials schema."""

    # Inherits client_id, client_secret, refresh_token and access_token from OAuth2BYOCAuthConfig


class GoogleCalendarAuthConfig(OAuth2BYOCAuthConfig):
    """Google Calendar authentication credentials schema."""

    # Inherits client_id, client_secret, refresh_token and access_token from OAuth2BYOCAuthConfig


class GoogleDocsAuthConfig(OAuth2BYOCAuthConfig):
    """Google Docs authentication credentials schema."""

    # Inherits client_id, client_secret, refresh_token and access_token from OAuth2BYOCAuthConfig


class GoogleDriveAuthConfig(OAuth2BYOCAuthConfig):
    """Google Drive authentication credentials schema."""

    # Inherits client_id, client_secret, refresh_token and access_token from OAuth2BYOCAuthConfig


class GoogleSlidesAuthConfig(OAuth2BYOCAuthConfig):
    """Google Slides authentication credentials schema."""

    # Inherits client_id, client_secret, refresh_token and access_token from OAuth2BYOCAuthConfig


class GitLabAuthConfig(OAuth2WithRefreshAuthConfig):
    """GitLab authentication credentials schema."""

    # Inherits refresh_token and access_token from OAuth2WithRefreshAuthConfig


class HubspotAuthConfig(OAuth2WithRefreshAuthConfig):
    """Hubspot authentication credentials schema."""

    # Inherits refresh_token and access_token from OAuth2WithRefreshAuthConfig


class IntercomAuthConfig(OAuth2AuthConfig):
    """Intercom authentication credentials schema."""

    # Inherits access_token from OAuth2AuthConfig


class SalesforceAuthConfig(OAuth2BYOCAuthConfig):
    """Salesforce authentication credentials schema."""

    # instance_url is now in SalesforceConfig as a template field
    # Inherits client_id, client_secret, refresh_token and access_token from OAuth2BYOCAuthConfig


class JiraAuthConfig(OAuth2WithRefreshAuthConfig):
    """Jira authentication credentials schema."""

    # Inherits refresh_token and access_token from OAuth2WithRefreshAuthConfig


class LinearAuthConfig(OAuth2AuthConfig):
    """Linear authentication credentials schema."""

    # Inherits access_token from OAuth2AuthConfig


class MondayAuthConfig(OAuth2AuthConfig):
    """Monday authentication credentials schema."""

    # Inherits access_token from OAuth2AuthConfig


class MySQLAuthConfig(BaseDatabaseAuthConfig):
    """MySQL authentication configuration."""


class NotionAuthConfig(OAuth2AuthConfig):
    """Notion authentication credentials schema."""

    # Inherits access_token from OAuth2AuthConfig


class OneDriveAuthConfig(OAuth2WithRefreshAuthConfig):
    """OneDrive authentication credentials schema."""

    # Inherits refresh_token and access_token from OAuth2WithRefreshAuthConfig


class OracleAuthConfig(BaseDatabaseAuthConfig):
    """Oracle authentication configuration."""


class OutlookCalendarAuthConfig(OAuth2WithRefreshAuthConfig):
    """Outlook Calendar authentication credentials schema."""

    # Inherits refresh_token and access_token from OAuth2WithRefreshAuthConfig


class OutlookMailAuthConfig(OAuth2WithRefreshAuthConfig):
    """Outlook Mail authentication credentials schema."""

    # Inherits refresh_token and access_token from OAuth2WithRefreshAuthConfig


class PipedriveAuthConfig(AuthConfig):
    """Pipedrive authentication credentials schema."""

    api_token: str = Field(
        title="API Token",
        description="Your Pipedrive API token. Find it in Settings > Personal preferences > API.",
        min_length=10,
    )

    @field_validator("api_token")
    @classmethod
    def validate_api_token(cls, v: str) -> str:
        """Validate Pipedrive API token."""
        if not v or not v.strip():
            raise ValueError("API token is required")
        return v.strip()


class ExcelAuthConfig(OAuth2WithRefreshAuthConfig):
    """Microsoft Excel authentication credentials schema."""

    # Inherits refresh_token and access_token from OAuth2WithRefreshAuthConfig


class OneNoteAuthConfig(OAuth2WithRefreshAuthConfig):
    """Microsoft OneNote authentication credentials schema."""

    # Inherits refresh_token and access_token from OAuth2WithRefreshAuthConfig


class WordAuthConfig(OAuth2WithRefreshAuthConfig):
    """Microsoft Word authentication credentials schema."""

    # Inherits refresh_token and access_token from OAuth2WithRefreshAuthConfig


class CTTIAuthConfig(AuthConfig):
    """CTTI Clinical Trials authentication credentials schema."""

    username: str = Field(
        title="Username",
        description="Username for the AACT Clinical Trials database",
        min_length=1,
    )
    password: str = Field(
        title="Password",
        description="Password for the AACT Clinical Trials database",
        min_length=1,
    )

    @field_validator("username", "password")
    @classmethod
    def validate_not_empty(cls, v: str, info) -> str:
        """Validate that username and password are not empty."""
        if not v or not v.strip():
            field_name = info.field_name.replace("_", " ").title()
            raise ValueError(f"{field_name} is required")
        return v.strip()


class PostgreSQLAuthConfig(BaseDatabaseAuthConfig):
    """PostgreSQL authentication configuration."""


class SharePointAuthConfig(OAuth2WithRefreshAuthConfig):
    """SharePoint authentication credentials schema."""

    # Inherits refresh_token and access_token from OAuth2WithRefreshAuthConfig


class SlackAuthConfig(OAuth2AuthConfig):
    """Slack authentication credentials schema."""

    # Inherits access_token from OAuth2AuthConfig


class SQLServerAuthConfig(BaseDatabaseAuthConfig):
    """SQL Server authentication configuration."""


class SQLiteAuthConfig(BaseDatabaseAuthConfig):
    """SQLite authentication configuration."""


class StripeAuthConfig(AuthConfig):
    """Stripe authentication credentials schema."""

    api_key: str = Field(
        title="API Key",
        description="The API key for the Stripe account. Should start with 'sk_test_' for test mode"
        " or 'sk_live_' for live mode.",
        pattern="^sk_(test|live)_[A-Za-z0-9]+$",
        min_length=20,
    )

    @field_validator("api_key")
    @classmethod
    def validate_api_key(cls, v: str) -> str:
        """Validate Stripe API key format."""
        if not v or not v.strip():
            raise ValueError("API key is required")
        v = v.strip()
        if not v.startswith(("sk_test_", "sk_live_")):
            raise ValueError("Stripe API key must start with 'sk_test_' or 'sk_live_'")
        return v


class TodoistAuthConfig(OAuth2AuthConfig):
    """Todoist authentication credentials schema."""

    # Inherits access_token from OAuth2AuthConfig


class TeamsAuthConfig(OAuth2WithRefreshAuthConfig):
    """Microsoft Teams authentication credentials schema."""

    # Inherits refresh_token and access_token from OAuth2WithRefreshAuthConfig


class TrelloAuthConfig(AuthConfig):
    """Trello authentication credentials schema.

    Trello uses OAuth1, which requires both a token and token secret.
    """

    oauth_token: str = Field(
        title="OAuth Token",
        description="The OAuth1 access token for Trello",
    )
    oauth_token_secret: str = Field(
        title="OAuth Token Secret",
        description="The OAuth1 access token secret for Trello",
    )


# AUTH PROVIDER AUTHENTICATION CONFIGS
# These are for authenticating TO auth providers themselves


class ComposioAuthConfig(APIKeyAuthConfig):
    """Composio Auth Provider authentication credentials schema."""

    api_key: str = Field(
        title="API Key",
        description="Your Composio API key.",
    )


class PipedreamAuthConfig(AuthConfig):
    """Pipedream Auth Provider authentication credentials schema.

    Pipedream uses OAuth2 client credentials flow for API authentication.
    The access tokens expire after 3600 seconds (1 hour).
    """

    client_id: str = Field(
        title="Client ID",
        description="Your Pipedream OAuth client ID.",
    )
    client_secret: str = Field(
        title="Client Secret",
        description="Your Pipedream OAuth client secret.",
    )


class S3AuthConfig(AuthConfig):
    """S3-compatible storage authentication configuration.

    Supports AWS S3, MinIO, LocalStack, Cloudflare R2, or any S3 API-compatible service.
    Used for dual-destination syncing (Qdrant + S3) for event streaming.
    """

    aws_access_key_id: str = Field(
        title="Access Key ID",
        description="S3 access key ID (AWS_ACCESS_KEY_ID)",
    )
    aws_secret_access_key: str = Field(
        title="Secret Access Key",
        description="S3 secret access key (AWS_SECRET_ACCESS_KEY)",
    )
    bucket_name: str = Field(
        title="Bucket Name",
        description="S3 bucket name where data will be written",
    )
    bucket_prefix: str = Field(
        default="airweave-outbound/",
        title="Bucket Prefix",
        description="Prefix for all Airweave data in the bucket (e.g., 'airweave-outbound/')",
    )
    aws_region: str = Field(
        default="us-east-1",
        title="AWS Region",
        description="AWS region (or dummy value for non-AWS S3 services)",
    )
    endpoint_url: Optional[str] = Field(
        default=None,
        title="Custom Endpoint URL",
        description="Custom S3 endpoint URL (for MinIO, LocalStack, etc.). Leave empty for AWS S3.",
    )
    use_ssl: bool = Field(
        default=True,
        title="Use SSL",
        description="Use SSL/TLS for S3 connections",
    )

    @model_validator(mode="after")
    def validate_credentials(self):
        """Ensure required credentials are provided."""
        # Strip whitespace from all credential fields
        self.aws_access_key_id = self.aws_access_key_id.strip()
        self.aws_secret_access_key = self.aws_secret_access_key.strip()
        self.bucket_name = self.bucket_name.strip()

        if not self.aws_access_key_id or not self.aws_secret_access_key:
            raise ValueError("S3 requires aws_access_key_id and aws_secret_access_key")
        if not self.bucket_name:
            raise ValueError("S3 requires bucket_name")
        return self
