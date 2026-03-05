"""Schemas for integration credentials."""

from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from airweave.models.integration_credential import IntegrationType
from airweave.schemas.source_connection import AuthenticationMethod, OAuthType


class IntegrationCredentialBase(BaseModel):
    """Base class for integration credentials."""

    name: str
    integration_short_name: str
    description: Optional[str] = None
    integration_type: IntegrationType
    authentication_method: AuthenticationMethod
    oauth_type: Optional[OAuthType] = None
    auth_config_class: Optional[str] = None


class IntegrationCredentialCreate(IntegrationCredentialBase):
    """Create class for integration credentials."""

    encrypted_credentials: str


class IntegrationCredentialCreateEncrypted(IntegrationCredentialBase):
    """Create class for integration credentials with encrypted data."""

    encrypted_credentials: str


class IntegrationCredentialUpdate(BaseModel):
    """Update class for integration credentials."""

    name: Optional[str] = None
    description: Optional[str] = None
    encrypted_credentials: Optional[str] = None


class IntegrationCredentialInDBBase(IntegrationCredentialBase):
    """Base class for integration credentials in the database."""

    id: UUID
    organization_id: UUID
    encrypted_credentials: str

    model_config = ConfigDict(from_attributes=True)


class IntegrationCredentialInDB(IntegrationCredentialInDBBase):
    """Integration credential in DB without decrypted data."""

    pass


class IntegrationCredential(IntegrationCredentialInDBBase):
    """Integration credential with decrypted data."""

    decrypted_credentials: dict


class IntegrationCredentialRawCreate(IntegrationCredentialBase):
    """Create class for integration credentials with raw auth fields.

    This schema is used when auth fields need to be validated and encrypted
    before creating the credential.
    """

    auth_fields: dict
