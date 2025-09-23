"""Azure Key Vault adapter for secret management."""

import os
import logging
from typing import Optional, Dict
from functools import lru_cache

logger = logging.getLogger(__name__)


class KeyVaultAdapter:
    """Adapter for Azure Key Vault secret management."""

    def __init__(self, vault_url: Optional[str] = None):
        """Initialize Key Vault adapter.

        Args:
            vault_url: Azure Key Vault URL (e.g., https://mykeyvault.vault.azure.net/)
                      If not provided, will look for AZURE_KEY_VAULT_URL env var
        """
        self.vault_url = vault_url or os.getenv("AZURE_KEY_VAULT_URL")
        self.client = None
        self._cache: Dict[str, str] = {}

        if self.vault_url:
            self._initialize_client()

    def _initialize_client(self):
        """Initialize Azure Key Vault client."""
        try:
            from azure.keyvault.secrets import SecretClient
            from azure.identity import DefaultAzureCredential

            # Use DefaultAzureCredential which works with:
            # - Managed Identity (in Azure)
            # - Azure CLI (local development)
            # - Environment variables
            # - GitHub OIDC (in GitHub Actions)
            credential = DefaultAzureCredential()
            self.client = SecretClient(vault_url=self.vault_url, credential=credential)
            logger.info(f"Connected to Azure Key Vault: {self.vault_url}")
        except ImportError:
            logger.warning(
                "Azure Key Vault SDK not installed. Install with: pip install azure-keyvault-secrets azure-identity"
            )
            self.client = None
        except Exception as e:
            logger.error(f"Failed to initialize Key Vault client: {e}")
            self.client = None

    @lru_cache(maxsize=128)
    def get_secret(self, secret_name: str, default: Optional[str] = None) -> Optional[str]:
        """Get secret from Key Vault with caching.

        Args:
            secret_name: Name of the secret in Key Vault
            default: Default value if secret not found

        Returns:
            Secret value or default
        """
        if not self.client:
            return default

        try:
            # Convert environment variable style to Key Vault style
            # e.g., OPENAI_API_KEY -> openai-api-key
            kv_secret_name = secret_name.lower().replace("_", "-")

            secret = self.client.get_secret(kv_secret_name)
            logger.debug(f"Retrieved secret: {kv_secret_name}")
            return secret.value
        except Exception as e:
            logger.debug(f"Secret {kv_secret_name} not found in Key Vault: {e}")
            return default

    def get_env_or_secret(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """Get value from environment variable or Key Vault.

        Environment variable takes precedence over Key Vault.

        Args:
            key: Environment variable / secret name
            default: Default value if not found

        Returns:
            Value from env var, Key Vault, or default
        """
        # Check environment variable first
        env_value = os.getenv(key)
        if env_value:
            return env_value

        # Try Key Vault if available
        if self.client:
            secret_value = self.get_secret(key, default)
            if secret_value:
                return secret_value

        return default

    def load_all_secrets_to_env(self, prefix: Optional[str] = None, exclude_core: bool = True):
        """Load all secrets from Key Vault into environment variables.

        Args:
            prefix: Optional prefix to filter secrets (e.g., "MONKE-")
            exclude_core: If True, excludes core dependencies (OpenAI, Mistral) from loading
        """
        if not self.client:
            logger.warning("Key Vault client not initialized, skipping secret loading")
            return

        # Core dependencies that should not be loaded from Key Vault
        core_secrets = {"openai-api-key", "mistral-api-key"} if exclude_core else set()

        try:
            # List all secrets
            secrets = self.client.list_properties_of_secrets()
            loaded_count = 0
            skipped_count = 0

            for secret_properties in secrets:
                secret_name = secret_properties.name

                # Skip core dependencies if requested
                if secret_name.lower() in core_secrets:
                    logger.debug(f"Skipping core secret: {secret_name}")
                    skipped_count += 1
                    continue

                # Apply prefix filter if specified
                if prefix and not secret_name.lower().startswith(prefix.lower()):
                    continue

                # Get the secret value
                try:
                    secret = self.client.get_secret(secret_name)

                    # Convert Key Vault style to env var style
                    # e.g., github-auth-provider-account-id -> GITHUB_AUTH_PROVIDER_ACCOUNT_ID
                    env_var_name = secret_name.upper().replace("-", "_")

                    # Only set if not already in environment
                    if not os.getenv(env_var_name):
                        os.environ[env_var_name] = secret.value
                        loaded_count += 1
                        logger.debug(f"Loaded secret {secret_name} as {env_var_name}")
                except Exception as e:
                    logger.warning(f"Failed to load secret {secret_name}: {e}")

            logger.info(
                f"Loaded {loaded_count} secrets from Key Vault (skipped {skipped_count} core secrets)"
            )
        except Exception as e:
            logger.error(f"Failed to list secrets from Key Vault: {e}")


# Singleton instance
_kv_adapter: Optional[KeyVaultAdapter] = None


def get_keyvault_adapter(vault_url: Optional[str] = None) -> KeyVaultAdapter:
    """Get or create the Key Vault adapter singleton.

    Args:
        vault_url: Optional Key Vault URL

    Returns:
        KeyVaultAdapter instance
    """
    global _kv_adapter
    if _kv_adapter is None:
        _kv_adapter = KeyVaultAdapter(vault_url)
    return _kv_adapter


def load_secrets_from_keyvault():
    """Convenience function to load all secrets into environment."""
    adapter = get_keyvault_adapter()
    if adapter.client:
        adapter.load_all_secrets_to_env()
        return True
    return False
