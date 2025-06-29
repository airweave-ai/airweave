"""This module contains the service classes for managing secrets."""

import logging
import os
from abc import ABC, abstractmethod
from typing import Optional, Dict

from azure.identity.aio import DefaultAzureCredential
from azure.keyvault.secrets.aio import SecretClient

from airweave.core.config import settings

logger = logging.getLogger(__name__)


class SecretProvider(ABC):
    """Abstract base class for secret providers."""
    
    @abstractmethod
    async def get_secret(self, key: str) -> Optional[str]:
        """Get a secret by key.
        
        Args:
            key: The key of the secret.
            
        Returns:
            The secret value or None if not found.
        """
        pass
    
    @abstractmethod
    async def set_secret(self, key: str, value: str) -> bool:
        """Set a secret.
        
        Args:
            key: The key of the secret.
            value: The value to store.
            
        Returns:
            True if successful, False otherwise.
        """
        pass


class AzureKeyVaultSecretProvider(SecretProvider):
    """Azure Key Vault secret provider."""
    
    def __init__(self):
        """Initialize Azure Key Vault client."""
        try:
            vault_url = f"https://{settings.AZURE_KEYVAULT_NAME}.vault.azure.net/"
            credential = DefaultAzureCredential()  # uses managed identity on Kubernetes
            self.client = SecretClient(vault_url=vault_url, credential=credential)
            logger.info(f"Initialized Azure Key Vault client with vault: {settings.AZURE_KEYVAULT_NAME}")
        except Exception as e:
            logger.error(f"Failed to initialize Azure Key Vault client: {e}")
            self.client = None
    
    async def get_secret(self, key: str) -> Optional[str]:
        """Get a secret from Azure Key Vault.
        
        Args:
            key: The key of the secret.
            
        Returns:
            The secret value or None if not found.
        """
        if not self.client:
            logger.error("Azure Key Vault client is not initialized")
            return None
            
        try:
            secret = await self.client.get_secret(key)
            return secret.value
        except Exception as e:
            logger.error(f"Failed to get secret {key}: {e}")
            return None
    
    async def set_secret(self, key: str, value: str) -> bool:
        """Set a secret in Azure Key Vault.
        
        Args:
            key: The key of the secret.
            value: The value to store.
            
        Returns:
            True if successful, False otherwise.
        """
        if not self.client:
            logger.error("Azure Key Vault client is not initialized")
            return False
            
        try:
            await self.client.set_secret(key, value)
            return True
        except Exception as e:
            logger.error(f"Failed to set secret {key}: {e}")
            return False


class EnvironmentSecretProvider(SecretProvider):
    """Environment variable-based secret provider."""
    
    async def get_secret(self, key: str) -> Optional[str]:
        """Get a secret from environment variables.
        
        Args:
            key: The key of the secret.
            
        Returns:
            The secret value or None if not found.
        """
        return os.environ.get(key)
    
    async def set_secret(self, key: str, value: str) -> bool:
        """Set a secret in environment variables.
        
        Args:
            key: The key of the secret.
            value: The value to store.
            
        Returns:
            True if successful, False otherwise.
        """
        try:
            os.environ[key] = value
            return True
        except Exception as e:
            logger.error(f"Failed to set environment variable {key}: {e}")
            return False


class SecretManager:
    """Secret manager that delegates to appropriate provider based on environment."""
    
    def __init__(self):
        """Initialize the secret manager with appropriate providers."""
        self.providers: Dict[str, SecretProvider] = {}
        
        # Always add environment provider as fallback
        self.providers["env"] = EnvironmentSecretProvider()
        
        # Add Azure Key Vault provider in non-local environments
        if settings.ENVIRONMENT in ["dev", "prd"]:
            self.providers["azure"] = AzureKeyVaultSecretProvider()
    
    async def get_secret(self, key: str, provider: str = None) -> Optional[str]:
        """Get a secret using the specified or default provider.
        
        Args:
            key: The key of the secret.
            provider: The provider to use ("azure" or "env"). If None, tries each in order.
            
        Returns:
            The secret value or None if not found.
        """
        if provider and provider in self.providers:
            return await self.providers[provider].get_secret(key)
        
        # Try providers in priority order
        if "azure" in self.providers:
            value = await self.providers["azure"].get_secret(key)
            if value:
                return value
                
        # Fall back to environment variables
        return await self.providers["env"].get_secret(key)
    
    async def set_secret(self, key: str, value: str, provider: str = None) -> bool:
        """Set a secret using the specified or default provider.
        
        Args:
            key: The key of the secret.
            value: The value to store.
            provider: The provider to use ("azure" or "env"). If None, uses Azure in dev/prd, env otherwise.
            
        Returns:
            True if successful, False otherwise.
        """
        if provider and provider in self.providers:
            return await self.providers[provider].set_secret(key, value)
            
        # Use Azure in dev/prd environments, fallback to env in local
        if settings.ENVIRONMENT in ["dev", "prd"] and "azure" in self.providers:
            return await self.providers["azure"].set_secret(key, value)
        else:
            return await self.providers["env"].set_secret(key, value)


# Create a singleton instance
secret_manager = SecretManager()

# Keep backward compatibility
secret_client = None
if settings.ENVIRONMENT in ["dev", "prd"] and "azure" in secret_manager.providers:
    secret_client = secret_manager.providers["azure"].client