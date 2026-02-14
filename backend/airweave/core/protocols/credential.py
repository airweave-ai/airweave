"""Protocol for cross-cutting credential operations.

Used by source connections, and in future by destinations,
sync token refresh, and any domain that authenticates to external systems.
"""

from typing import Any, Optional, Protocol

from airweave.schemas.source_connection import AuthenticationMethod


class CredentialServiceProtocol(Protocol):
    """Credential validation, encryption, and CRUD."""

    async def validate_auth_fields(self, short_name: str, auth_fields: dict) -> Any:
        """Validate auth fields against the source's auth config schema.

        Returns the validated auth config instance.
        Raises InvalidAuthFieldsError on validation failure.
        Raises SourceNotFoundError if source doesn't exist.
        Raises SourceDoesNotSupportDirectAuthError if source has no auth config.
        """
        ...

    async def validate_config_fields(
        self, short_name: str, config_fields: Any, enabled_features: list
    ) -> dict:
        """Validate config fields against the source's config schema.

        Strips feature-gated fields the organization doesn't have access to.
        Returns a plain dict of validated config.
        Raises InvalidConfigFieldsError on validation failure.
        """
        ...

    async def validate_direct_auth(
        self, short_name: str, auth_config: Any, config_fields: Any
    ) -> None:
        """Validate direct auth credentials by instantiating the source and calling .validate().

        Raises InvalidCredentialsError if validation fails.
        """
        ...

    async def validate_oauth_token(
        self, short_name: str, access_token: str, config_fields: Any
    ) -> None:
        """Validate an OAuth token by instantiating the source and calling .validate().

        Raises InvalidCredentialsError if validation fails.
        """
        ...

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
        """Encrypt auth fields and create an IntegrationCredential record.

        Returns the created credential ORM object.
        """
        ...

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
        ...
