"""Configuration settings for the Airweave backend.

Wraps environment variables and provides defaults.
"""

from typing import Optional

from pydantic import PostgresDsn, ValidationInfo, field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Pydantic settings class.

    Attributes:
    ----------
        PROJECT_NAME (str): The name of the project.
        LOCAL_DEVELOPMENT (bool): Whether the application is running locally.
        LOCAL_CURSOR_DEVELOPMENT (bool): Whether cursor development features are enabled.
        DTAP_ENVIRONMENT (str): The deployment environment (local, dev, test, prod).
        FRONTEND_LOCAL_DEVELOPMENT_PORT (int): Port for local frontend development.
        FIRST_SUPERUSER (str): The email address of the first superuser.
        FIRST_SUPERUSER_PASSWORD (str): The password of the first superuser.
        ENCRYPTION_KEY (str): The encryption key.
        POSTGRES_HOST (str): The PostgreSQL server hostname.
        POSTGRES_DB (str): The PostgreSQL database name.
        POSTGRES_USER (str): The PostgreSQL username.
        POSTGRES_PASSWORD (str): The PostgreSQL password.
        SQLALCHEMY_ASYNC_DATABASE_URI (Optional[PostgresDsn]): The SQLAlchemy async database URI.
        LOCAL_NGROK_SERVER (Optional[str]): The local ngrok server URL.
        RUN_ALEMBIC_MIGRATIONS (bool): Whether to run the alembic migrations.
        RUN_DB_SYNC (bool): Whether to run the system sync to process sources,
            destinations, and entity types.
        QDRANT_HOST (str): The Qdrant host.
        QDRANT_PORT (int): The Qdrant port.
        QDRANT_URL (str): The Qdrant URL.
        TEXT2VEC_INFERENCE_URL (str): The URL for text2vec-transformers inference service.
        OPENAI_API_KEY (Optional[str]): The OpenAI API key.
        MISTRAL_API_KEY (Optional[str]): The Mistral AI API key.
    """

    PROJECT_NAME: str = "Airweave"
    LOCAL_DEVELOPMENT: bool = False
    LOCAL_CURSOR_DEVELOPMENT: bool = False
    DTAP_ENVIRONMENT: str = "local"
    FRONTEND_LOCAL_DEVELOPMENT_PORT: int = 8080

    FIRST_SUPERUSER: str
    FIRST_SUPERUSER_PASSWORD: str

    AUTH_ENABLED: Optional[bool] = False
    AUTH0_DOMAIN: Optional[str] = None
    AUTH0_AUDIENCE: Optional[str] = None
    AUTH0_RULE_NAMESPACE: Optional[str] = None

    ENCRYPTION_KEY: str

    POSTGRES_HOST: str
    POSTGRES_DB: str = "airweave"
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    SQLALCHEMY_ASYNC_DATABASE_URI: Optional[PostgresDsn] = None

    LOCAL_NGROK_SERVER: Optional[str] = None

    RUN_ALEMBIC_MIGRATIONS: bool = False
    RUN_DB_SYNC: bool = True

    QDRANT_HOST: str = "localhost"
    QDRANT_PORT: int = 6333
    QDRANT_URL: str = f"http://{QDRANT_HOST}:{QDRANT_PORT}"

    TEXT2VEC_INFERENCE_URL: str = "http://localhost:9878"

    OPENAI_API_KEY: Optional[str] = None
    MISTRAL_API_KEY: Optional[str] = None

    @field_validator("AUTH0_DOMAIN", "AUTH0_AUDIENCE", "AUTH0_RULE_NAMESPACE", mode="before")
    def validate_auth0_settings(cls, v: str, info: ValidationInfo) -> str:
        """Validate Auth0 settings when AUTH_ENABLED is True.

        Args:

        ----
            v (str): The value of the Auth0 setting.
            info (ValidationInfo): The validation context containing all field values.

        Returns:
        -------
            str: The validated Auth0 setting.

        Raises:
        ------
            ValueError: If AUTH_ENABLED is True and the Auth0 setting is empty.
        """
        auth_enabled = info.data.get("AUTH_ENABLED", False)
        if auth_enabled and not v:
            field_name = info.field_name
            raise ValueError(f"{field_name} must be set when AUTH_ENABLED is True")
        return v

    @field_validator("SQLALCHEMY_ASYNC_DATABASE_URI", mode="before")
    def assemble_db_connection(cls, v: Optional[str], info: ValidationInfo) -> PostgresDsn:
        """Build the SQLAlchemy database URI.

        Args:
        ----
            v (Optional[str]): The value of the SQLALCHEMY_DATABASE_URI setting.
            info (ValidationInfo): The validation context containing all field values.

        Returns:
        -------
            PostgresDsn: The assembled SQLAlchemy async database URI.

        """
        if isinstance(v, str):
            return v

        # Connect to local PostgreSQL server during local development
        # This allows developers to debug without Docker
        host = info.data.get("POSTGRES_HOST", "localhost")

        return PostgresDsn.build(
            scheme="postgresql+asyncpg",
            username=info.data.get("POSTGRES_USER"),
            password=info.data.get("POSTGRES_PASSWORD"),
            host=host,
            path=f"{info.data.get('POSTGRES_DB') or ''}",
        )

    @property
    def api_url(self) -> str:
        """The server URL.

        Returns:
            str: The server URL.
        """
        if self.DTAP_ENVIRONMENT == "local":
            return self.LOCAL_NGROK_SERVER or "http://localhost:8001"
        if self.DTAP_ENVIRONMENT == "prod":
            return "https://api.airweave.ai"
        return f"https://api.{self.DTAP_ENVIRONMENT}-airweave.com"

    @property
    def app_url(self) -> str:
        """The app URL.

        Returns:
            str: The app URL.
        """
        if self.DTAP_ENVIRONMENT == "local":
            return f"http://localhost:{self.FRONTEND_LOCAL_DEVELOPMENT_PORT}"
        if self.DTAP_ENVIRONMENT == "prod":
            return "https://app.airweave.ai"
        return f"https://app.{self.DTAP_ENVIRONMENT}-airweave.com"

    @property
    def docs_url(self) -> str:
        """The docs URL.

        Returns:
            str: The docs URL.
        """
        if self.DTAP_ENVIRONMENT == "local":
            return f"http://localhost:{self.FRONTEND_LOCAL_DEVELOPMENT_PORT}"
        if self.DTAP_ENVIRONMENT == "prod":
            return "https://docs.airweave.ai"
        return f"https://docs.{self.DTAP_ENVIRONMENT}-airweave.com"


settings = Settings()
