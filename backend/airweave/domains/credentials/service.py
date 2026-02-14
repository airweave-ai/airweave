"""Credential service -- cross-cutting validation, encryption, and CRUD for credentials.

Replaces scattered resource_locator + crud.integration_credential usage
with a single injectable service backed by SourceRegistry and a repository.
"""

from typing import Any, Dict, Optional

from pydantic import ValidationError

from airweave import schemas
from airweave.core import credentials
from airweave.core.protocols.credential import CredentialServiceProtocol
from airweave.core.protocols.integration_credential_repository import (
    IntegrationCredentialRepositoryProtocol,
)
from airweave.domains.credentials.exceptions import (
    FeatureFlagRequiredError,
    InvalidAuthFieldsError,
    InvalidConfigFieldsError,
    InvalidCredentialsError,
    SourceDoesNotSupportDirectAuthError,
)
from airweave.domains.sources.exceptions import SourceNotFoundError
from airweave.domains.sources.protocols import SourceRegistryProtocol
from airweave.models.integration_credential import IntegrationType
from airweave.schemas.source_connection import AuthenticationMethod, OAuthType


class CredentialService(CredentialServiceProtocol):
    """Credential validation and management using SourceRegistry for schema lookups."""

    def __init__(
        self,
        source_registry: SourceRegistryProtocol,
        credential_repo: IntegrationCredentialRepositoryProtocol,
    ) -> None:
        """Initialize with a source registry and credential repository."""
        self._source_registry = source_registry
        self._credential_repo = credential_repo

    def _get_entry(self, short_name: str):
        """Look up source entry, raise SourceNotFoundError if missing."""
        try:
            return self._source_registry.get(short_name)
        except KeyError:
            raise SourceNotFoundError(short_name)

    async def validate_auth_fields(self, short_name: str, auth_fields: dict) -> Any:
        """Validate auth fields against the source's auth config schema."""
        entry = self._get_entry(short_name)

        if entry.auth_config_ref is None:
            raise SourceDoesNotSupportDirectAuthError(entry.name)

        try:
            return entry.auth_config_ref(**auth_fields)
        except ValidationError as e:
            errors = "; ".join(
                f"{'.'.join(str(x) for x in err['loc'])}: {err['msg']}" for err in e.errors()
            )
            raise InvalidAuthFieldsError(errors) from e
        except Exception as e:
            raise InvalidAuthFieldsError(str(e)) from e

    async def validate_config_fields(
        self, short_name: str, config_fields: Any, enabled_features: list
    ) -> dict:
        """Validate config fields against the source's config schema."""
        entry = self._get_entry(short_name)

        if not config_fields:
            return {}

        payload = self._as_mapping(config_fields)

        if entry.config_ref is None:
            return payload

        self._check_feature_gated_fields(entry.config_ref, payload, enabled_features)

        try:
            if hasattr(entry.config_ref, "model_validate"):
                model = entry.config_ref.model_validate(payload)
            else:
                model = entry.config_ref(**payload)

            return model.model_dump() if hasattr(model, "model_dump") else payload

        except ValidationError as e:
            errors = "; ".join(
                f"{'.'.join(str(x) for x in err.get('loc', []))}: {err.get('msg')}"
                for err in e.errors()
            )
            raise InvalidConfigFieldsError(errors) from e
        except Exception as e:
            raise InvalidConfigFieldsError(str(e)) from e

    @staticmethod
    def _check_feature_gated_fields(
        config_ref: type, payload: dict, enabled_features: list
    ) -> None:
        """Reject config fields that require a feature flag the org doesn't have."""
        for field_name, field_info in config_ref.model_fields.items():
            json_schema_extra = field_info.json_schema_extra or {}
            feature_flag = json_schema_extra.get("feature_flag")

            if feature_flag and feature_flag not in enabled_features:
                if field_name in payload and payload[field_name] is not None:
                    field_title = field_info.title or field_name
                    raise FeatureFlagRequiredError(field_title, feature_flag)

    async def validate_direct_auth(
        self, short_name: str, auth_config: Any, config_fields: Any
    ) -> None:
        """Validate direct auth by instantiating the source and calling .validate()."""
        entry = self._get_entry(short_name)
        try:
            source_instance = await entry.source_class_ref.create(auth_config, config=config_fields)
            if hasattr(source_instance, "validate"):
                is_valid = await source_instance.validate()
                if not is_valid:
                    raise InvalidCredentialsError()
            else:
                raise InvalidCredentialsError(f"No validate method found for {short_name}")
        except InvalidCredentialsError:
            raise
        except Exception as e:
            raise InvalidCredentialsError(f"Validation failed: {e}") from e

    async def validate_oauth_token(
        self, short_name: str, access_token: str, config_fields: Any
    ) -> None:
        """Validate OAuth token by instantiating the source and calling .validate()."""
        entry = self._get_entry(short_name)
        try:
            source_instance = await entry.source_class_ref.create(
                access_token=access_token, config=config_fields
            )
            if hasattr(source_instance, "validate"):
                is_valid = await source_instance.validate()
                if not is_valid:
                    raise InvalidCredentialsError("OAuth token is invalid")
            # No validate method is OK for OAuth — some sources skip it
        except InvalidCredentialsError:
            raise
        except Exception as e:
            raise InvalidCredentialsError(f"Token validation failed: {e}") from e

    async def create_credential(
        self,
        source_short_name: str,
        source_name: str,
        auth_fields: dict,
        organization_id: Any,
        auth_method: AuthenticationMethod,
        oauth_type: Optional[str],
        auth_config_class: Optional[str],
        db: Any,
        uow: Any,
        ctx: Any = None,
    ) -> Any:
        """Encrypt and create an IntegrationCredential record."""
        if hasattr(auth_fields, "model_dump"):
            auth_fields_dict = auth_fields.model_dump()
        else:
            auth_fields_dict = auth_fields

        encrypted = credentials.encrypt(auth_fields_dict)

        pydantic_oauth_type = OAuthType(oauth_type) if oauth_type else None

        cred_in = schemas.IntegrationCredentialCreateEncrypted(
            name=f"{source_name} - {organization_id}",
            description=f"Credentials for {source_name}",
            integration_short_name=source_short_name,
            integration_type=IntegrationType.SOURCE,
            authentication_method=auth_method,
            oauth_type=pydantic_oauth_type,
            encrypted_credentials=encrypted,
            auth_config_class=auth_config_class,
        )
        return await self._credential_repo.create(db, obj_in=cred_in, ctx=ctx, uow=uow)

    async def update_credential(
        self,
        credential_id: Any,
        auth_fields: dict,
        short_name: str,
        db: Any,
        uow: Any,
        ctx: Any = None,
    ) -> None:
        """Re-validate auth fields, re-encrypt, and update the credential record."""
        validated_auth = await self.validate_auth_fields(short_name, auth_fields)

        if hasattr(validated_auth, "model_dump"):
            serializable = validated_auth.model_dump()
        elif hasattr(validated_auth, "dict"):
            serializable = validated_auth.dict()
        else:
            serializable = validated_auth

        credential_update = schemas.IntegrationCredentialUpdate(
            encrypted_credentials=credentials.encrypt(serializable)
        )
        credential = await self._credential_repo.get(db, id=credential_id, ctx=ctx)
        if credential:
            await self._credential_repo.update(
                db, db_obj=credential, obj_in=credential_update, ctx=ctx, uow=uow
            )

    @staticmethod
    def _as_mapping(value: Any) -> Dict[str, Any]:
        """Normalize config_fields to a plain dict."""
        if isinstance(value, dict):
            return value
        if hasattr(value, "model_dump"):
            return value.model_dump()
        if hasattr(value, "dict"):
            return value.dict()
        if hasattr(value, "__dict__"):
            return {k: v for k, v in value.__dict__.items() if not k.startswith("_")}
        raise TypeError(f"Cannot convert {type(value).__name__} to mapping")
