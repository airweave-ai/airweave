"""Auth config."""

from pydantic import Field

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


# Source application-specific auth configs
class StripeAuthConfig(AuthConfig):
    """Stripe authentication credentials schema."""

    api_key: str = Field(
        title="API Key",
        description="The API key for the Stripe account. Should start with 'sk_test_' for test mode"
        " or 'sk_live_' for live mode.",
        pattern="^sk_(test|live)_[A-Za-z0-9]+$",
    )


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


class PostgreSQLAuthConfig(BaseDatabaseAuthConfig):
    """PostgreSQL authentication configuration."""


class MySQLAuthConfig(BaseDatabaseAuthConfig):
    """MySQL authentication configuration."""


class SQLServerAuthConfig(BaseDatabaseAuthConfig):
    """SQL Server authentication configuration."""


class OracleAuthConfig(BaseDatabaseAuthConfig):
    """Oracle authentication configuration."""


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


# Source auth configs
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


class DropboxAuthConfig(AuthConfig):
    """Dropbox authentication credentials schema."""

    client_id: str = Field(
        title="Client ID", description="The OAuth client ID for your Dropbox app"
    )
    client_secret: str = Field(
        title="Client Secret", description="The OAuth client secret for your Dropbox app"
    )


class GoogleAuthConfig(AuthConfig):
    """Google authentication credentials schema."""

    client_id: str = Field(title="Client ID", description="The OAuth client ID for your Google app")
    client_secret: str = Field(
        title="Client Secret", description="The OAuth client secret for your Google app"
    )
