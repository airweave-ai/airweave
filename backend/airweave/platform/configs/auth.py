"""Auth config."""

from typing import Optional

from pydantic import Field, field_validator

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

    host: str = Field(title="Host", description="The host of the PostgreSQL database")
    port: int = Field(title="Port", description="The port of the PostgreSQL database")
    database: str = Field(title="Database", description="The name of the PostgreSQL database")
    user: str = Field(title="Username", description="The username for the PostgreSQL database")
    password: str = Field(title="Password", description="The password for the PostgreSQL database")
    schema: str = Field(
        default="public",
        title="Schema",
        description="The schema of the PostgreSQL database",
    )
    tables: str = Field(
        default="*",
        title="Tables",
        description=(
            "Comma separated list of tables and views to sync. For example, 'users,orders'. "
            "For all tables (not views), use '*'."
        ),
    )

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
        title="API Key", description="The API key for the Qdrant service (if required)"
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
    )


class BitbucketAuthConfig(AuthConfig):
    """Bitbucket authentication credentials schema.

    Supports either:
    - access_token (Bearer) + workspace/repo_slug, or
    - username + app_password (legacy Basic) + workspace/repo_slug
    """

    # New token-based auth
    access_token: Optional[str] = Field(
        default=None,
        title="API Token",
        description=(
            "Bitbucket API token used as a Bearer token. Provide this to use token-based auth."
        ),
    )

    # Legacy Basic auth (deprecated)
    username: Optional[str] = Field(
        default=None,
        title="Username",
        description="Your Bitbucket username (email when using API token)",
    )
    app_password: Optional[str] = Field(
        default=None,
        title="App Password",
        description=("Bitbucket app password (deprecated). Prefer API tokens where available."),
    )

    workspace: str = Field(
        default=None,
        title="Workspace",
        description="Bitbucket workspace slug (e.g., 'my-workspace')",
    )
    repo_slug: Optional[str] = Field(
        default="",
        title="Repository Slug",
        description="Specific repository to sync (e.g., 'my-repo'). "
        "If empty, syncs all repositories in the workspace.",
    )


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
    )


class GmailAuthConfig(OAuth2BYOCAuthConfig):
    """Gmail authentication credentials schema."""

    # Inherits client_id, client_secret, refresh_token and access_token from OAuth2BYOCAuthConfig


class GoogleCalendarAuthConfig(OAuth2BYOCAuthConfig):
    """Google Calendar authentication credentials schema."""

    # Inherits client_id, client_secret, refresh_token and access_token from OAuth2BYOCAuthConfig


class GoogleDriveAuthConfig(OAuth2BYOCAuthConfig):
    """Google Drive authentication credentials schema."""

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


class CTTIAuthConfig(AuthConfig):
    """CTTI Clinical Trials authentication credentials schema."""

    username: str = Field(
        title="Username", description="Username for the AACT Clinical Trials database"
    )
    password: str = Field(
        title="Password", description="Password for the AACT Clinical Trials database"
    )


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
    )


class TodoistAuthConfig(OAuth2AuthConfig):
    """Todoist authentication credentials schema."""

    # Inherits access_token from OAuth2AuthConfig


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
