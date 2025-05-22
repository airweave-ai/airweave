"""Auth config."""

from pydantic import Field, field_validator

from airweave.platform.configs._base import BaseConfig


class AuthConfig(BaseConfig):
    """Authentication config schema."""

    pass


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
            "Comma separated list of tables to sync. For example, 'users,orders'. "
            "For all tables, use '*'"
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


class AsanaAuthConfig(AuthConfig):
    """Asana authentication credentials schema."""

    refresh_token: str = Field(
        title="Refresh Token", description="The refresh token for your Asana app."
    )
    access_token: str = Field(
        title="Access Token", description="The access token for your Asana app."
    )


class ClickUpAuthConfig(AuthConfig):
    """Clickup authentication credentials schema."""

    access_token: str = Field(
        title="Access Token", description="The access token for your Clickup app."
    )


class ConfluenceAuthConfig(AuthConfig):
    """Confluence authentication credentials schema."""

    refresh_token: str = Field(
        title="Refresh Token", description="The refresh token for your Confluence app."
    )
    access_token: str = Field(
        title="Access Token", description="The access token for your Confluence app."
    )


class DropboxAuthConfig(AuthConfig):
    """Dropbox authentication credentials schema."""

    client_id: str = Field(
        title="Client ID", description="The OAuth client ID for your Dropbox app"
    )
    client_secret: str = Field(
        title="Client Secret", description="The OAuth client secret for your Dropbox app"
    )
    refresh_token: str = Field(
        title="Refresh Token", description="The refresh token for your Dropbox app."
    )
    access_token: str = Field(
        title="Access Token", description="The access token for your Dropbox app."
    )


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
    repo_name: str = Field(
        title="Repository Name",
        description="Repository to sync in owner/repo format (e.g., 'airweave-ai/airweave')",
    )


class GmailAuthConfig(AuthConfig):
    """Gmail authentication credentials schema."""

    client_id: str = Field(title="Client ID", description="The OAuth client ID for your Google app")
    client_secret: str = Field(
        title="Client Secret", description="The OAuth client secret for your Google app"
    )
    refresh_token: str = Field(
        title="Refresh Token", description="The refresh token for your Gmail app."
    )
    access_token: str = Field(
        title="Access Token", description="The access token for your Gmail app."
    )


class GoogleCalendarAuthConfig(AuthConfig):
    """Google Calendar authentication credentials schema."""

    client_id: str = Field(title="Client ID", description="The OAuth client ID for your Google app")
    client_secret: str = Field(
        title="Client Secret", description="The OAuth client secret for your Google app"
    )
    refresh_token: str = Field(
        title="Refresh Token", description="The refresh token for your Google Calendar app."
    )
    access_token: str = Field(
        title="Access Token", description="The access token for your Google Calendar app."
    )


class GoogleDriveAuthConfig(AuthConfig):
    """Google Drive authentication credentials schema."""

    client_id: str = Field(title="Client ID", description="The OAuth client ID for your Google app")
    client_secret: str = Field(
        title="Client Secret", description="The OAuth client secret for your Google app"
    )
    refresh_token: str = Field(
        title="Refresh Token", description="The refresh token for your Google Drive app."
    )
    access_token: str = Field(
        title="Access Token", description="The access token for your Google Drive app."
    )


class HubspotAuthConfig(AuthConfig):
    """Hubspot authentication credentials schema."""

    refresh_token: str = Field(
        title="Refresh Token", description="The refresh token for your Hubspot app."
    )
    access_token: str = Field(
        title="Access Token", description="The access token for your Hubspot app."
    )


class IntercomAuthConfig(AuthConfig):
    """Intercom authentication credentials schema."""

    access_token: str = Field(
        title="Access Token", description="The access token for your Intercom app."
    )


class JiraAuthConfig(AuthConfig):
    """Jira authentication credentials schema."""

    refresh_token: str = Field(
        title="Refresh Token", description="The refresh token for your Jira app."
    )
    access_token: str = Field(
        title="Access Token", description="The access token for your Jira app."
    )


class LinearAuthConfig(AuthConfig):
    """Linear authentication credentials schema."""

    access_token: str = Field(
        title="Access Token", description="The access token for your Linear app."
    )


class MondayAuthConfig(AuthConfig):
    """Monday authentication credentials schema."""

    access_token: str = Field(
        title="Access Token", description="The access token for your Monday app."
    )


class MySQLAuthConfig(BaseDatabaseAuthConfig):
    """MySQL authentication configuration."""


class NotionAuthConfig(AuthConfig):
    """Notion authentication credentials schema."""

    access_token: str = Field(
        title="Access Token", description="The access token for your Notion app."
    )


class OneDriveAuthConfig(AuthConfig):
    """OneDrive authentication credentials schema."""

    refresh_token: str = Field(
        title="Refresh Token", description="The refresh token for your OneDrive app."
    )
    access_token: str = Field(
        title="Access Token", description="The access token for your OneDrive app."
    )


class OracleAuthConfig(BaseDatabaseAuthConfig):
    """Oracle authentication configuration."""


class OutlookCalendarAuthConfig(AuthConfig):
    """Outlook Calendar authentication credentials schema."""

    refresh_token: str = Field(
        title="Refresh Token", description="The refresh token for your Outlook Calendar app."
    )
    access_token: str = Field(
        title="Access Token", description="The access token for your Outlook Calendar app."
    )


class OutlookMailAuthConfig(AuthConfig):
    """Outlook Mail authentication credentials schema."""

    refresh_token: str = Field(
        title="Refresh Token", description="The refresh token for your Outlook Mail app."
    )
    access_token: str = Field(
        title="Access Token", description="The access token for your Outlook Mail app."
    )


class PostgreSQLAuthConfig(BaseDatabaseAuthConfig):
    """PostgreSQL authentication configuration."""


class SlackAuthConfig(AuthConfig):
    """Slack authentication credentials schema."""

    access_token: str = Field(
        title="Access Token", description="The access token for your Slack app."
    )


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


class TodoistAuthConfig(AuthConfig):
    """Todoist authentication credentials schema."""

    access_token: str = Field(
        title="Access Token", description="The access token for your Todoist app."
    )


class TrelloAuthConfig(AuthConfig):
    """Trello authentication credentials schema."""

    pass


class ZenDeskAuthConfig(AuthConfig):
    """ZenDesk authentication credentials schema."""

    refresh_token: str = Field(
        title="Refresh Token", description="The refresh token for your ZenDesk app."
    )
    access_token: str = Field(
        title="Access Token", description="The access token for your ZenDesk app."
    )


class WooCommerceAuthConfig(AuthConfig):
    """WooCommerce authentication configuration."""

    consumer_key: str = Field(..., description="WooCommerce API consumer key")
    consumer_secret: str = Field(..., description="WooCommerce API consumer secret")
    store_url: str = Field(..., description="WooCommerce store URL (e.g., https://example.com)")
