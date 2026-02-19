"""Azure Key Vault credential adapter."""

from azure.identity.aio import DefaultAzureCredential
from azure.keyvault.secrets.aio import SecretClient

from airweave.core.config import settings

secret_client = None  # still allow imports to work even if not in use

if settings.ENVIRONMENT in ["dev", "prd"]:
    vault_url = f"https://{settings.AZURE_KEYVAULT_NAME}.vault.azure.net/"
    credential = DefaultAzureCredential()  # uses managed identity on Kubernetes
    secret_client = SecretClient(vault_url=vault_url, credential=credential)
