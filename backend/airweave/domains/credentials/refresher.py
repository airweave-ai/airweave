"""Credential refresh strategies.

Each implementation knows HOW to obtain a fresh access token and persist
the updated credentials.  They are stateless — the caller (TokenRefresher)
owns the timer / lock / current-token state.
"""

from typing import Any, Optional, Set
from uuid import UUID

from airweave import crud, schemas
from airweave.api.context import ApiContext
from airweave.core import credentials as credential_utils
from airweave.core.exceptions import TokenRefreshError
from airweave.core.logging import ContextualLogger, logger as default_logger
from airweave.domains.oauth.protocols import OAuth2ServiceProtocol


class OAuthCredentialRefresher:
    """Refresh via standard OAuth2 refresh-token flow.

    Wraps ``OAuth2ServiceProtocol.refresh_access_token`` and persists the
    updated credential set.
    """

    def __init__(
        self,
        *,
        source_short_name: str,
        connection_id: UUID,
        integration_credential_id: UUID,
        ctx: ApiContext,
        config_fields: Optional[dict],
        oauth2_service: OAuth2ServiceProtocol,
        logger: Optional[ContextualLogger] = None,
    ) -> None:
        self._source_short_name = source_short_name
        self._connection_id = connection_id
        self._integration_credential_id = integration_credential_id
        self._ctx = ctx
        self._config_fields = config_fields
        self._oauth2_service = oauth2_service
        self._logger = logger or default_logger

    async def refresh(self) -> str:
        from airweave.db.session import get_db_context

        try:
            async with get_db_context() as db:
                credential = await crud.integration_credential.get(
                    db, self._integration_credential_id, self._ctx
                )
                if not credential:
                    raise TokenRefreshError("Integration credential not found")

                decrypted = credential_utils.decrypt(credential.encrypted_credentials)

                oauth2_response = await self._oauth2_service.refresh_access_token(
                    db=db,
                    integration_short_name=self._source_short_name,
                    ctx=self._ctx,
                    connection_id=self._connection_id,
                    decrypted_credential=decrypted,
                    config_fields=self._config_fields,
                )
                return oauth2_response.access_token

        except TokenRefreshError:
            raise
        except Exception as exc:
            raise TokenRefreshError(f"OAuth refresh failed: {exc}") from exc


class AuthProviderCredentialRefresher:
    """Refresh via an auth-provider instance (e.g. Pipedream).

    Receives pre-computed ``runtime_auth_all_fields`` / ``runtime_auth_optional_fields``
    from the source registry so no DB lookup is needed at refresh time.
    """

    def __init__(
        self,
        *,
        auth_provider_instance: Any,
        source_short_name: str,
        integration_credential_id: Optional[UUID],
        ctx: ApiContext,
        runtime_auth_all_fields: list[str],
        runtime_auth_optional_fields: Set[str],
        logger: Optional[ContextualLogger] = None,
    ) -> None:
        self._auth_provider = auth_provider_instance
        self._source_short_name = source_short_name
        self._integration_credential_id = integration_credential_id
        self._ctx = ctx
        self._all_fields = runtime_auth_all_fields
        self._optional_fields = runtime_auth_optional_fields
        self._logger = logger or default_logger

    async def refresh(self) -> str:
        try:
            fresh_credentials = await self._auth_provider.get_creds_for_source(
                source_short_name=self._source_short_name,
                source_auth_config_fields=self._all_fields,
                optional_fields=self._optional_fields,
            )

            access_token = fresh_credentials.get("access_token")
            if not access_token:
                raise TokenRefreshError(
                    "No access token in credentials from auth provider"
                )

            if self._integration_credential_id:
                await self._persist_credentials(fresh_credentials)

            return access_token

        except TokenRefreshError:
            raise
        except Exception as exc:
            raise TokenRefreshError(
                f"Auth provider refresh failed: {exc}"
            ) from exc

    async def _persist_credentials(self, fresh_credentials: dict) -> None:
        from airweave.db.session import get_db_context

        credential_update = schemas.IntegrationCredentialUpdate(
            encrypted_credentials=credential_utils.encrypt(fresh_credentials)
        )
        try:
            async with get_db_context() as db:
                credential = await crud.integration_credential.get(
                    db, self._integration_credential_id, self._ctx
                )
                if credential:
                    await crud.integration_credential.update(
                        db,
                        db_obj=credential,
                        obj_in=credential_update,
                        ctx=self._ctx,
                    )
        except Exception as exc:
            self._logger.error(
                f"Failed to persist refreshed credentials: {exc}"
            )
