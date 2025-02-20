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
        DTAP_ENVIRONMENT Optional[str]: Either "local" or "prod" for determining the use case.
        FRONTEND_LOCATION_URI Optional[str]: Defines the location of the host.
        FIRST_SUPERUSER (str): The email address of the first superuser.
        FIRST_SUPERUSER_PASSWORD (str): The password of the first superuser.
        ENCRYPTION_KEY (str): The encryption key.
        POSTGRES_LOCAL_DEVELOPMENT (Optional[bool]): Whether the application is running locally.
        POSTGRES_DB (str): The PostgreSQL database name.
        POSTGRES_USER (str): The PostgreSQL username.
        POSTGRES_PASSWORD (str): The PostgreSQL password.
        POSTGRES_HOST (str): The PostgreSQL host name.
        POSTGRES_PORT (str): PostgresSQL port
        SQLALCHEMY_ASYNC_DATABASE_URI (Optional[PostgresDsn]): The SQLAlchemy async database URI.
        LOCAL_NGROK_SERVER (Optional[str]): The local ngrok server URL.
        RUN_ALEMBIC_MIGRATIONS (Optional[bool]): Whether to run the alembic migrations.
        RUN_DB_SYNC (Optional[bool]): Whether to run the system sync to process sources,
            destinations, and chunk types.
        NATIVE_WEAVIATE_HOST (str): The Weaviate host.
        NATIVE_WEAVIATE_PORT (int): The Weaviate port.
        NATIVE_WEAVIATE_GRPC_PORT (int): The Weaviate gRPC port.
    """

    PROJECT_NAME: str = "Airweave"
    POSTGRES_LOCAL_DEVELOPMENT: Optional[bool] = False
    FRONTEND_LOCATION_URI: str = "localhost"
    FRONTEND_LOCAL_DEVELOPMENT_PORT: Optional[int] = 8080
    DTAP_ENVIRONMENT: Optional[str] = "local"

    FIRST_SUPERUSER: str
    FIRST_SUPERUSER_PASSWORD: str

    ENCRYPTION_KEY: str

    POSTGRES_DB: str = "airweave"
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_PORT: int = 5432
    POSTGRES_HOST: str = "db"
    SQLALCHEMY_ASYNC_DATABASE_URI: Optional[PostgresDsn] = None

    LOCAL_NGROK_SERVER: Optional[str] = None

    RUN_ALEMBIC_MIGRATIONS: Optional[bool] = False
    RUN_DB_SYNC: Optional[bool] = True

    NATIVE_WEAVIATE_HOST: str = "weaviate"
    NATIVE_WEAVIATE_PORT: int = 8080
    NATIVE_WEAVIATE_GRPC_PORT: int = 50051

    OPENAI_API_KEY: Optional[str] = None

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

        if info.data.get("POSTGRES_LOCAL_DEVELOPMENT"):
            host = "localhost"
        else:
            host = info.data.get("POSTGRES_HOST")

        return PostgresDsn.build(
            scheme="postgresql+asyncpg",
            username=info.data.get("POSTGRES_USER"),
            password=info.data.get("POSTGRES_PASSWORD"),
            host=host,
            port=info.data.get("POSTGRES_PORT"),
            path=f"{info.data.get('POSTGRES_DB') or ''}",
        )

    @property
    def api_url(self) -> str:
        """The server URL.

        Returns:
            str: The server URL.
        """
        if self.DTAP_ENVIRONMENT == "local":
            return self.LOCAL_NGROK_SERVER
        if self.DTAP_ENVIRONMENT == "prod":
            return "https://api.airweave.ai"
        return f"https://api.{self.DTAP_ENVIRONMENT}-airweave.ai"

    @property
    def app_url(self) -> str:
        """The app URL.

        Returns:
            str: The app URL.
        """
        if self.DTAP_ENVIRONMENT == "local":
            return f"http://{self.FRONTEND_LOCATION_URI}:{self.FRONTEND_LOCAL_DEVELOPMENT_PORT}"
        if self.DTAP_ENVIRONMENT == "prod":
            return "https://app.airweave.ai"
        return f"https://app.{self.DTAP_ENVIRONMENT}-airweave.ai"

    @property
    def docs_url(self) -> str:
        """The docs URL.

        Returns:
            str: The docs URL.
        """
        if self.DTAP_ENVIRONMENT == "local":
            return f"http://{self.FRONTEND_LOCATION_URI}:{self.FRONTEND_LOCAL_DEVELOPMENT_PORT}"
        if self.DTAP_ENVIRONMENT == "prod":
            return "https://docs.airweave.ai"
        return f"https://docs.{self.DTAP_ENVIRONMENT}-airweave.ai"


settings = Settings()
