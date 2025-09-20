"""Settings module for integration authentication settings."""

from pathlib import Path
from typing import Any

import yaml

from airweave.core.config import settings as core_settings
from airweave.core.logging import logger
from airweave.core.secrets import secret_client
from airweave.platform.auth.schemas import (
    APIKeyAuthSettings,
    BaseAuthSettings,
    ConfigClassAuthSettings,
    OAuth2Settings,
    OAuth2WithRefreshRotatingSettings,
    OAuth2WithRefreshSettings,
)
from airweave.schemas.source_connection import AuthenticationMethod, OAuthType


class IntegrationSettings:
    """Class for loading and parsing integration settings based on the auth_type.

    Fetches integration settings from a environment-specific YAML file and parses them.
    """

    def __init__(self, file_path: Path):
        """Initializes the IntegrationSettings class.

        Args:
        ----
            file_path (Path): The path to the YAML file containing the integration settings.

        """
        self._settings: dict[str, BaseAuthSettings] = {}
        self.load_settings(file_path)

    def _parse_integration(self, name: str, config: dict[str, Any]) -> BaseAuthSettings:
        """Dynamically parse integration settings based on oauth_type presence.

        Args:
        ----
            name (str): The name of the integration.
            config (Dict[str, Any]): The configuration for the integration.

        Returns:
        -------
            BaseAuthSettings: The parsed integration settings with auth method and oauth type.

        Raises:
        ------
            ValueError: If the configuration is not supported.

        """
        # Handle case where config is None (implicit direct auth)
        if config is None:
            config = {}

        # New model: oauth_type determines if it's OAuth, absence means direct auth
        oauth_type_str = config.get("oauth_type", "")

        # Set integration short name
        config["integration_short_name"] = name

        if oauth_type_str:
            # It's an OAuth integration
            config["authentication_method"] = AuthenticationMethod.OAUTH_BROWSER.value

            # Determine the OAuth settings model based on oauth_type
            # Pydantic validation will handle field requirements
            if oauth_type_str == "access_only":
                model = OAuth2Settings
                config["oauth_type"] = OAuthType.ACCESS_ONLY.value
            elif oauth_type_str == "with_refresh":
                model = OAuth2WithRefreshSettings
                config["oauth_type"] = OAuthType.WITH_REFRESH.value
            elif oauth_type_str == "with_rotating_refresh":
                model = OAuth2WithRefreshRotatingSettings
                config["oauth_type"] = OAuthType.WITH_ROTATING_REFRESH.value
            else:
                raise ValueError(f"Unknown oauth_type for integration {name}: {oauth_type_str}")

        else:
            # It's a direct authentication integration (API key, config class, etc.)
            config["authentication_method"] = AuthenticationMethod.DIRECT.value
            config["oauth_type"] = None

            # Special cases for known integrations
            if name == "stripe":
                model = APIKeyAuthSettings
            else:
                model = ConfigClassAuthSettings

        return model(**config) if model else None

    def load_settings(self, file_path: Path) -> None:
        """Loads and parses integration settings from a YAML file.

        Args:
        ----
            file_path (Path): The path to the YAML file containing the integration settings.

        """
        with file_path.open("r") as file:
            data = yaml.safe_load(file).get("integrations", {})
            for name, config in data.items():
                self._settings[name] = self._parse_integration(name, config)

    async def _get_client_secret(self, settings: BaseAuthSettings) -> str:
        """Retrieves the client secret for a specific integration.

        Args:
        ----
            settings (BaseAuthSettings): The settings for the integration.
        """
        if core_settings.ENVIRONMENT == "prd":
            secret = await secret_client.get_secret(settings.client_secret)
            return secret.value
        else:
            return settings.client_secret

    async def get_by_short_name(self, short_name: str) -> BaseAuthSettings:
        """Retrieves settings for a specific integration by its short name.

        Args:
        ----
            short_name (str): The short name of the integration.

        Returns:
        -------
            Optional[BaseAuthSettings]: The settings for the integration, if found.

        Raises:
        ------
            KeyError: If the integration settings are not found.

        """
        settings = self._settings.get(short_name)
        if not settings:
            raise KeyError(f"Integration settings not found for {short_name}")

        # Enrich with client secret for PRD - create a copy to avoid mutating the original
        # Check if this is an OAuth integration that needs client secret
        is_oauth = False

        if hasattr(settings, "oauth_type") and settings.oauth_type:
            # If oauth_type is set, it's OAuth
            is_oauth = True
        elif hasattr(settings, "authentication_method"):
            # Check authentication method
            is_oauth = settings.authentication_method in [
                AuthenticationMethod.OAUTH_BROWSER.value,
                AuthenticationMethod.OAUTH_TOKEN.value,
            ]

        if is_oauth:
            # Create a copy of the settings object
            settings_dict = settings.model_dump()
            settings_dict["client_secret"] = await self._get_client_secret(settings)
            try:
                # Return a new instance with the enriched client secret
                return type(settings)(**settings_dict)
            except Exception as e:
                # If there's an error, log it and return the original settings
                logger.error(f"Error creating settings object: {e}")
                raise e

        return settings


current_file_path = Path(__file__)
parent_directory = current_file_path.parent
environment = core_settings.ENVIRONMENT
if environment == "local":
    env_prefix = "dev"
else:
    env_prefix = environment
yaml_file_path = parent_directory / f"yaml/{env_prefix}.integrations.yaml"

integration_settings = IntegrationSettings(yaml_file_path)
