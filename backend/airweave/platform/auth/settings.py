"""Settings module for integration authentication settings."""

from pathlib import Path
from typing import Any

import yaml

from airweave.core.config import settings as core_settings
from airweave.core.secrets import secret_client
from airweave.platform.auth.schemas import (
    APIKeyAuthSettings,
    AuthType,
    BaseAuthSettings,
    ConfigClassAuthSettings,
    NativeFunctionalityAuthSettings,
    OAuth2Settings,
    OAuth2WithRefreshRotatingSettings,
    OAuth2WithRefreshSettings,
)


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
        """Dynamically parse integration settings based on the auth_type.

        Args:
        ----
            name (str): The name of the integration.
            config (Dict[str, Any]): The configuration for the integration.

        Returns:
        -------
            BaseAuthSettings: The parsed integration settings.

        Raises:
        ------
            ValueError: If the auth_type is not supported.

        """
        auth_type = config.get("auth_type", "")
        mapping = {
            AuthType.oauth2: OAuth2Settings,
            AuthType.api_key: APIKeyAuthSettings,
            AuthType.oauth2_with_refresh: OAuth2WithRefreshSettings,
            AuthType.oauth2_with_refresh_rotating: OAuth2WithRefreshRotatingSettings,
            AuthType.native_functionality: NativeFunctionalityAuthSettings,
            AuthType.config_class: ConfigClassAuthSettings,
            AuthType.none: None,
        }
        model = mapping.get(auth_type)
        config["integration_short_name"] = name
        if model:
            return model(**config)
        else:
            raise ValueError(f"Unsupported auth_type for integration {name}: {auth_type}")

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
            return await secret_client.get_secret(settings.client_secret)
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

        # Enrich with client secret for PRD
        if settings.auth_type in [
            AuthType.oauth2,
            AuthType.oauth2_with_refresh,
            AuthType.oauth2_with_refresh_rotating,
        ]:
            settings.client_secret = await self._get_client_secret(settings)
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
