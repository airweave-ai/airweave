"""Source connection creation service."""

import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Tuple
from uuid import UUID

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from airweave import schemas
from airweave.analytics.events import business_events
from airweave.api.context import ApiContext
from airweave.core.config import settings as core_settings
from airweave.core.credentials import encrypt as encrypt_credentials
from airweave.core.events.sync import SyncLifecycleEvent
from airweave.core.protocols.event_bus import EventBus
from airweave.core.shared_models import ConnectionStatus, IntegrationType
from airweave.db.unit_of_work import UnitOfWork
from airweave.domains.collections.protocols import CollectionRepositoryProtocol
from airweave.domains.connections.protocols import ConnectionRepositoryProtocol
from airweave.domains.credentials.protocols import IntegrationCredentialRepositoryProtocol
from airweave.domains.oauth.protocols import OAuth1ServiceProtocol, OAuth2ServiceProtocol
from airweave.domains.source_connections.protocols import (
    ResponseBuilderProtocol,
    SourceConnectionRepositoryProtocol,
)
from airweave.domains.sources.protocols import (
    SourceLifecycleServiceProtocol,
    SourceRegistryProtocol,
)
from airweave.domains.sources.types import SourceRegistryEntry
from airweave.domains.syncs.protocols import SyncLifecycleServiceProtocol
from airweave.domains.syncs.types import SyncProvisionResult
from airweave.domains.temporal.protocols import TemporalWorkflowServiceProtocol
from airweave.models.connection import Connection
from airweave.models.connection_init_session import ConnectionInitStatus
from airweave.models.integration_credential import IntegrationCredential
from airweave.models.source_connection import SourceConnection
from airweave.schemas.connection import ConnectionCreate
from airweave.schemas.integration_credential import IntegrationCredentialCreateEncrypted
from airweave.schemas.source_connection import (
    AuthenticationMethod,
    AuthProviderAuthentication,
    DirectAuthentication,
    OAuthBrowserAuthentication,
    OAuthTokenAuthentication,
    SourceConnectionCreate,
)
from airweave.schemas.source_connection import (
    SourceConnection as SourceConnectionSchema,
)


class SourceConnectionCreationService:
    """Handles all source-connection creation logic (any auth method)."""

    def __init__(
        self,
        sc_repo: SourceConnectionRepositoryProtocol,
        collection_repo: CollectionRepositoryProtocol,
        connection_repo: ConnectionRepositoryProtocol,
        cred_repo: IntegrationCredentialRepositoryProtocol,
        source_registry: SourceRegistryProtocol,
        response_builder: ResponseBuilderProtocol,
        sync_lifecycle: SyncLifecycleServiceProtocol,
        oauth1_service: OAuth1ServiceProtocol,
        oauth2_service: OAuth2ServiceProtocol,
        source_lifecycle_service: SourceLifecycleServiceProtocol,
        temporal_workflow_service: TemporalWorkflowServiceProtocol,
        event_bus: EventBus,
    ) -> None:
        self._sc_repo = sc_repo
        self._collection_repo = collection_repo
        self._conn_repo = connection_repo
        self._cred_repo = cred_repo
        self._source_registry = source_registry
        self._response_builder = response_builder
        self._sync_lifecycle = sync_lifecycle
        self._oauth1_service = oauth1_service
        self._oauth2_service = oauth2_service
        self._source_lifecycle_service = source_lifecycle_service
        self._temporal_workflow_service = temporal_workflow_service
        self._event_bus = event_bus

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    async def create(  # noqa: C901
        self, db: AsyncSession, obj_in: SourceConnectionCreate, ctx: ApiContext
    ) -> SourceConnectionSchema:
        try:
            entry = self._source_registry.get(obj_in.short_name)
        except KeyError:
            raise HTTPException(status_code=404, detail=f"Source '{obj_in.short_name}' not found")

        if obj_in.name is None:
            obj_in.name = f"{entry.name} Connection"

        auth = obj_in.authentication

        match auth:
            case DirectAuthentication():
                auth_method = AuthenticationMethod.DIRECT
                is_browser = False
            case OAuthTokenAuthentication():
                auth_method = AuthenticationMethod.OAUTH_TOKEN
                is_browser = False
            case AuthProviderAuthentication():
                auth_method = AuthenticationMethod.AUTH_PROVIDER
                is_browser = False
            case OAuthBrowserAuthentication():
                has_byoc = bool(
                    (auth.client_id and auth.client_secret)
                    or (auth.consumer_key and auth.consumer_secret)
                )
                auth_method = (
                    AuthenticationMethod.OAUTH_BYOC
                    if has_byoc
                    else AuthenticationMethod.OAUTH_BROWSER
                )
                is_browser = True
            case None:
                auth_method = AuthenticationMethod.OAUTH_BROWSER
                is_browser = True

        supported = list(entry.auth_methods) if entry.auth_methods else []
        if (
            AuthenticationMethod.OAUTH_BROWSER.value in supported
            and AuthenticationMethod.OAUTH_BYOC.value not in supported
        ):
            supported.append(AuthenticationMethod.OAUTH_BYOC.value)

        if supported and auth_method.value not in supported:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Source '{entry.short_name}' does not support "
                    f"'{auth_method.value}' authentication. "
                    f"Supported: {supported}"
                ),
            )

        if entry.requires_byoc and is_browser and auth_method != AuthenticationMethod.OAUTH_BYOC:
            raise HTTPException(
                status_code=400,
                detail=f"Source '{entry.short_name}' requires custom OAuth client credentials. "
                "Please provide client_id and client_secret.",
            )

        if obj_in.sync_immediately is None:
            obj_in.sync_immediately = not is_browser

        if is_browser and obj_in.sync_immediately:
            raise HTTPException(
                status_code=400,
                detail="OAuth connections cannot use sync_immediately. "
                "Sync will start after authentication.",
            )

        match auth_method:
            case AuthenticationMethod.DIRECT:
                response = await self._create_direct(db, obj_in, entry, ctx)
            case AuthenticationMethod.OAUTH_TOKEN:
                response = await self._create_with_token(db, obj_in, entry, ctx)
            case AuthenticationMethod.AUTH_PROVIDER:
                response = await self._create_with_auth_provider(db, obj_in, entry, ctx)
            case AuthenticationMethod.OAUTH_BROWSER | AuthenticationMethod.OAUTH_BYOC:
                response = await self._create_with_oauth_browser(db, obj_in, entry, ctx)

        business_events.track_source_connection_created(
            ctx=ctx,
            connection_id=response.id,
            source_short_name=obj_in.short_name,
        )
        return response

    # ------------------------------------------------------------------
    # Branch: Direct auth
    # ------------------------------------------------------------------

    async def _create_direct(
        self,
        db: AsyncSession,
        obj_in: SourceConnectionCreate,
        entry: SourceRegistryEntry,
        ctx: ApiContext,
    ) -> SourceConnectionSchema:
        auth = obj_in.authentication
        if not isinstance(auth, DirectAuthentication):
            raise HTTPException(
                status_code=400, detail="Direct authentication requires credentials"
            )

        validated_auth = self._validate_auth_fields(entry, auth.credentials)
        validated_config = self._validate_config_fields(entry, obj_in.config, ctx)

        await self._source_lifecycle_service.validate(
            entry.short_name, validated_auth, validated_config or None
        )

        async with UnitOfWork(db) as uow:
            credential = await self._create_credential(
                uow.session, entry, validated_auth, AuthenticationMethod.DIRECT, ctx, uow
            )
            await uow.session.flush()

            connection = await self._create_connection(
                uow.session, obj_in.name, entry, credential.id, ctx, uow
            )
            await uow.session.flush()

            connection_schema = schemas.Connection.model_validate(connection, from_attributes=True)

            result = await self._sync_lifecycle.provision_sync(
                db=uow.session,
                name=obj_in.name,
                source_connection_id=connection.id,
                destination_connection_ids=[],
                collection_id=None,
                collection_readable_id=obj_in.readable_collection_id,
                source_entry=entry,
                schedule_config=obj_in.schedule,
                run_immediately=obj_in.sync_immediately,
                ctx=ctx,
                uow=uow,
            )

            sc = await self._create_source_connection_record(
                uow.session,
                obj_in=obj_in,
                connection_id=connection.id,
                collection_id=obj_in.readable_collection_id,
                sync_id=result.sync_id if result else None,
                config=validated_config,
                is_authenticated=True,
                ctx=ctx,
                uow=uow,
            )
            await uow.session.flush()

            if result and result.cron_schedule:
                await self._sync_lifecycle.create_schedule(
                    uow.session,
                    sync_id=result.sync_id,
                    cron_schedule=result.cron_schedule,
                    ctx=ctx,
                    uow=uow,
                )

            await uow.commit()
            await uow.session.refresh(sc)

        response = await self._response_builder.build_response(db, sc, ctx)

        if result and result.sync_job and obj_in.sync_immediately:
            await self._trigger_provisioned_sync(
                db,
                result,
                connection_schema,
                sc.id,
                obj_in.readable_collection_id,
                ctx,
            )

        return response

    # ------------------------------------------------------------------
    # Branch: OAuth browser (unified OAuth1/OAuth2)
    # ------------------------------------------------------------------

    async def _create_with_oauth_browser(
        self,
        db: AsyncSession,
        obj_in: SourceConnectionCreate,
        entry: SourceRegistryEntry,
        ctx: ApiContext,
    ) -> SourceConnectionSchema:
        from airweave.platform.auth.schemas import OAuth1Settings
        from airweave.platform.auth.settings import integration_settings

        validated_config = self._validate_config_fields(entry, obj_in.config, ctx)
        template_configs = self._extract_template_configs(entry, validated_config, ctx)

        oauth_settings = await integration_settings.get_by_short_name(entry.short_name)
        if not oauth_settings:
            raise HTTPException(
                status_code=400, detail=f"OAuth not configured for source: {entry.short_name}"
            )

        auth = obj_in.authentication
        state = secrets.token_urlsafe(24)
        api_callback = f"{core_settings.api_url}/source-connections/callback"

        provider_auth_url: str
        additional_overrides: Dict[str, Any] = {}

        if isinstance(oauth_settings, OAuth1Settings):
            consumer_key = (
                auth.consumer_key
                if isinstance(auth, OAuthBrowserAuthentication) and auth.consumer_key
                else oauth_settings.consumer_key
            )
            consumer_secret = (
                auth.consumer_secret
                if isinstance(auth, OAuthBrowserAuthentication) and auth.consumer_secret
                else oauth_settings.consumer_secret
            )

            request_token = await self._oauth1_service.get_request_token(
                request_token_url=oauth_settings.request_token_url,
                consumer_key=consumer_key,
                consumer_secret=consumer_secret,
                callback_url=api_callback,
                logger=ctx.logger,
            )
            additional_overrides = {
                "oauth_token": request_token.oauth_token,
                "oauth_token_secret": request_token.oauth_token_secret,
                "consumer_key": consumer_key,
                "consumer_secret": consumer_secret,
            }
            provider_auth_url = self._oauth1_service.build_authorization_url(
                authorization_url=oauth_settings.authorization_url,
                oauth_token=request_token.oauth_token,
                scope=oauth_settings.scope,
                expiration=oauth_settings.expiration,
            )
        else:
            client_id = (
                auth.client_id
                if isinstance(auth, OAuthBrowserAuthentication) and auth.client_id
                else None
            )
            url, code_verifier = await self._oauth2_service.generate_auth_url_with_redirect(
                oauth_settings,
                redirect_uri=api_callback,
                client_id=client_id,
                state=state,
                template_configs=template_configs,
            )
            provider_auth_url = url
            if code_verifier:
                additional_overrides["code_verifier"] = code_verifier

        async with UnitOfWork(db) as uow:
            sc = await self._create_source_connection_record(
                uow.session,
                obj_in=obj_in,
                connection_id=None,
                collection_id=obj_in.readable_collection_id,
                sync_id=None,
                config=validated_config,
                is_authenticated=False,
                ctx=ctx,
                uow=uow,
            )
            await uow.session.flush()

            proxy_url, proxy_expiry, redirect_session_id = await self._create_proxy_url(
                uow.session, provider_auth_url, ctx, uow
            )

            init_session = await self._create_init_session(
                uow.session,
                obj_in,
                entry,
                state,
                ctx,
                uow,
                redirect_session_id=redirect_session_id,
                template_configs=template_configs,
                additional_overrides=additional_overrides,
            )
            await uow.session.flush()

            sc.connection_init_session_id = init_session.id
            uow.session.add(sc)

            await uow.commit()
            await uow.session.refresh(sc)

        return await self._response_builder.build_response(
            db,
            sc,
            ctx,
            auth_url_override=proxy_url,
            auth_url_expiry_override=proxy_expiry,
        )

    # ------------------------------------------------------------------
    # Branch: OAuth token
    # ------------------------------------------------------------------

    async def _create_with_token(
        self,
        db: AsyncSession,
        obj_in: SourceConnectionCreate,
        entry: SourceRegistryEntry,
        ctx: ApiContext,
    ) -> SourceConnectionSchema:
        auth = obj_in.authentication
        if not isinstance(auth, OAuthTokenAuthentication):
            raise HTTPException(
                status_code=400, detail="OAuth token authentication requires an access token"
            )

        oauth_creds: Dict[str, Any] = {
            "access_token": auth.access_token,
            "refresh_token": auth.refresh_token,
            "token_type": "Bearer",
        }
        if auth.expires_at:
            oauth_creds["expires_at"] = auth.expires_at.isoformat()

        validated_config = self._validate_config_fields(entry, obj_in.config, ctx)

        await self._source_lifecycle_service.validate(
            entry.short_name, auth.access_token, validated_config or None
        )

        async with UnitOfWork(db) as uow:
            credential = await self._create_credential(
                uow.session, entry, oauth_creds, AuthenticationMethod.OAUTH_TOKEN, ctx, uow
            )
            await uow.session.flush()

            connection = await self._create_connection(
                uow.session, obj_in.name, entry, credential.id, ctx, uow
            )
            await uow.session.flush()

            connection_schema = schemas.Connection.model_validate(connection, from_attributes=True)

            result = await self._sync_lifecycle.provision_sync(
                db=uow.session,
                name=obj_in.name,
                source_connection_id=connection.id,
                destination_connection_ids=[],
                collection_id=None,
                collection_readable_id=obj_in.readable_collection_id,
                source_entry=entry,
                schedule_config=obj_in.schedule,
                run_immediately=obj_in.sync_immediately,
                ctx=ctx,
                uow=uow,
            )

            sc = await self._create_source_connection_record(
                uow.session,
                obj_in=obj_in,
                connection_id=connection.id,
                collection_id=obj_in.readable_collection_id,
                sync_id=result.sync_id if result else None,
                config=validated_config,
                is_authenticated=True,
                ctx=ctx,
                uow=uow,
            )
            await uow.session.flush()

            if result and result.cron_schedule:
                await self._sync_lifecycle.create_schedule(
                    uow.session,
                    sync_id=result.sync_id,
                    cron_schedule=result.cron_schedule,
                    ctx=ctx,
                    uow=uow,
                )

            await uow.commit()
            await uow.session.refresh(sc)

        response = await self._response_builder.build_response(db, sc, ctx)

        if result and result.sync_job and obj_in.sync_immediately:
            await self._trigger_provisioned_sync(
                db,
                result,
                connection_schema,
                sc.id,
                obj_in.readable_collection_id,
                ctx,
            )

        return response

    # ------------------------------------------------------------------
    # Branch: Auth provider
    # ------------------------------------------------------------------

    async def _create_with_auth_provider(
        self,
        db: AsyncSession,
        obj_in: SourceConnectionCreate,
        entry: SourceRegistryEntry,
        ctx: ApiContext,
    ) -> SourceConnectionSchema:
        auth = obj_in.authentication
        if not isinstance(auth, AuthProviderAuthentication):
            raise HTTPException(
                status_code=400, detail="Auth provider authentication requires provider config"
            )

        provider_conn = await self._conn_repo.get_by_readable_id(db, auth.provider_readable_id, ctx)
        if not provider_conn:
            raise HTTPException(
                status_code=404,
                detail=f"Auth provider '{auth.provider_readable_id}' not found",
            )

        if provider_conn.short_name not in (entry.supported_auth_providers or []):
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Source '{entry.short_name}' does not support "
                    f"'{provider_conn.short_name}' as an auth provider. "
                    f"Supported: {entry.supported_auth_providers}"
                ),
            )

        validated_auth_config = None
        if auth.provider_config:
            from airweave.core.auth_provider_service import auth_provider_service

            validated_auth_config = await auth_provider_service.validate_auth_provider_config(
                db, provider_conn.short_name, auth.provider_config
            )

        validated_config = self._validate_config_fields(entry, obj_in.config, ctx)

        async with UnitOfWork(db) as uow:
            connection = await self._create_connection(
                uow.session, obj_in.name, entry, None, ctx, uow
            )
            await uow.session.flush()

            connection_schema = schemas.Connection.model_validate(connection, from_attributes=True)

            result = await self._sync_lifecycle.provision_sync(
                db=uow.session,
                name=obj_in.name,
                source_connection_id=connection.id,
                destination_connection_ids=[],
                collection_id=None,
                collection_readable_id=obj_in.readable_collection_id,
                source_entry=entry,
                schedule_config=obj_in.schedule,
                run_immediately=obj_in.sync_immediately,
                ctx=ctx,
                uow=uow,
            )

            sc = await self._create_source_connection_record(
                uow.session,
                obj_in=obj_in,
                connection_id=connection.id,
                collection_id=obj_in.readable_collection_id,
                sync_id=result.sync_id if result else None,
                config=validated_config,
                is_authenticated=True,
                ctx=ctx,
                uow=uow,
                auth_provider_id=provider_conn.readable_id,
                auth_provider_config=validated_auth_config,
            )
            await uow.session.flush()

            if result and result.cron_schedule:
                await self._sync_lifecycle.create_schedule(
                    uow.session,
                    sync_id=result.sync_id,
                    cron_schedule=result.cron_schedule,
                    ctx=ctx,
                    uow=uow,
                )

            await uow.commit()
            await uow.session.refresh(sc)

        response = await self._response_builder.build_response(db, sc, ctx)

        if result and result.sync_job and obj_in.sync_immediately:
            await self._trigger_provisioned_sync(
                db,
                result,
                connection_schema,
                sc.id,
                obj_in.readable_collection_id,
                ctx,
            )

        return response

    # ------------------------------------------------------------------
    # Validation helpers
    # ------------------------------------------------------------------

    def _validate_auth_fields(self, entry: SourceRegistryEntry, credentials: dict) -> Any:
        if not entry.auth_config_ref:
            raise HTTPException(
                status_code=422,
                detail=f"Source '{entry.short_name}' does not support direct auth",
            )
        try:
            return entry.auth_config_ref(**credentials)
        except ValidationError as e:
            errors = "; ".join(
                f"{'.'.join(str(x) for x in err['loc'])}: {err['msg']}" for err in e.errors()
            )
            raise HTTPException(status_code=422, detail=f"Invalid auth fields: {errors}") from e
        except Exception as e:
            raise HTTPException(status_code=422, detail=str(e)) from e

    @staticmethod
    def _as_mapping(value: Any) -> Dict[str, Any]:
        """Coerce various shapes (ConfigValues, Pydantic models, plain dicts, etc.) into a dict."""
        from collections.abc import Mapping

        if value is None:
            return {}
        if isinstance(value, Mapping):
            return dict(value)
        if hasattr(value, "model_dump"):
            return value.model_dump()
        if hasattr(value, "dict"):
            return value.dict()
        if hasattr(value, "values"):
            v = value.values
            if isinstance(v, Mapping):
                return dict(v)
            return v
        if isinstance(value, list) and all(
            isinstance(x, dict) and "key" in x and "value" in x for x in value
        ):
            return {x["key"]: x["value"] for x in value}
        raise TypeError(f"config_fields must be mapping-like; got {type(value).__name__}")

    def _validate_config_fields(
        self,
        entry: SourceRegistryEntry,
        config: Any,
        ctx: ApiContext,
    ) -> Dict[str, Any]:
        if not config:
            return {}

        if not entry.config_ref:
            try:
                return self._as_mapping(config)
            except Exception:
                return {}

        try:
            payload = self._as_mapping(config)
        except Exception:
            payload = {}

        enabled_features = ctx.organization.enabled_features or []
        for field_name, field_info in entry.config_ref.model_fields.items():
            extra = field_info.json_schema_extra or {}
            flag = extra.get("feature_flag")
            if flag and flag not in enabled_features:
                if field_name in payload and payload[field_name] is not None:
                    raise HTTPException(
                        status_code=403,
                        detail=(
                            f"The '{field_info.title or field_name}' feature requires "
                            f"'{flag}' to be enabled for your organization."
                        ),
                    )

        try:
            model = entry.config_ref.model_validate(payload)
            return model.model_dump()
        except ValidationError as e:
            errors = "; ".join(
                f"{'.'.join(str(x) for x in err.get('loc', []))}: {err.get('msg')}"
                for err in e.errors()
            )
            raise HTTPException(status_code=422, detail=f"Invalid config fields: {errors}") from e
        except Exception as e:
            raise HTTPException(status_code=422, detail=str(e)) from e

    def _extract_template_configs(
        self,
        entry: SourceRegistryEntry,
        validated_config: Dict[str, Any],
        ctx: ApiContext,
    ) -> Optional[Dict[str, str]]:
        if not entry.config_ref or not validated_config:
            return None
        if not hasattr(entry.config_ref, "get_template_config_fields"):
            return None
        template_fields = entry.config_ref.get_template_config_fields()
        if not template_fields:
            return None
        if hasattr(entry.config_ref, "validate_template_configs"):
            try:
                entry.config_ref.validate_template_configs(validated_config)
            except ValueError as e:
                raise HTTPException(status_code=422, detail=str(e)) from e
        return {k: str(validated_config[k]) for k in template_fields if k in validated_config}

    # ------------------------------------------------------------------
    # Record creation helpers
    # ------------------------------------------------------------------

    async def _create_credential(
        self,
        db: AsyncSession,
        entry: SourceRegistryEntry,
        auth_fields: Any,
        auth_method: AuthenticationMethod,
        ctx: ApiContext,
        uow: UnitOfWork,
    ) -> IntegrationCredential:
        fields_dict = (
            auth_fields.model_dump() if hasattr(auth_fields, "model_dump") else auth_fields
        )
        encrypted = encrypt_credentials(fields_dict)

        oauth_type = None
        if auth_method in (
            AuthenticationMethod.OAUTH_BROWSER,
            AuthenticationMethod.OAUTH_TOKEN,
            AuthenticationMethod.OAUTH_BYOC,
        ):
            oauth_type = entry.oauth_type

        cred_in = IntegrationCredentialCreateEncrypted(
            name=f"{entry.name} - {ctx.organization.id}",
            description=f"Credentials for {entry.name}",
            integration_short_name=entry.short_name,
            integration_type=IntegrationType.SOURCE,
            authentication_method=auth_method,
            oauth_type=oauth_type,
            encrypted_credentials=encrypted,
            auth_config_class=entry.auth_config_ref.__name__ if entry.auth_config_ref else None,
        )
        return await self._cred_repo.create_encrypted(db, obj_in=cred_in, ctx=ctx, uow=uow)

    async def _create_connection(
        self,
        db: AsyncSession,
        name: str,
        entry: SourceRegistryEntry,
        credential_id: Optional[UUID],
        ctx: ApiContext,
        uow: UnitOfWork,
    ) -> Connection:
        conn_in = ConnectionCreate(
            name=name,
            integration_type=IntegrationType.SOURCE,
            integration_credential_id=credential_id,
            status=ConnectionStatus.ACTIVE,
            short_name=entry.short_name,
        )
        return await self._conn_repo.create(db, obj_in=conn_in, ctx=ctx, uow=uow)

    async def _create_source_connection_record(
        self,
        db: AsyncSession,
        *,
        obj_in: SourceConnectionCreate,
        connection_id: Optional[UUID],
        collection_id: str,
        sync_id: Optional[UUID],
        config: Optional[Dict[str, Any]],
        is_authenticated: bool,
        ctx: ApiContext,
        uow: UnitOfWork,
        auth_provider_id: Optional[str] = None,
        auth_provider_config: Optional[Dict[str, Any]] = None,
    ) -> SourceConnection:
        sc_data: Dict[str, Any] = {
            "name": obj_in.name,
            "description": obj_in.description,
            "short_name": obj_in.short_name,
            "config_fields": config,
            "connection_id": connection_id,
            "readable_collection_id": collection_id,
            "sync_id": sync_id,
            "is_authenticated": is_authenticated,
        }
        if auth_provider_id:
            sc_data["readable_auth_provider_id"] = auth_provider_id
            sc_data["auth_provider_config"] = auth_provider_config
        return await self._sc_repo.create(db, obj_in=sc_data, ctx=ctx, uow=uow)

    async def _create_proxy_url(
        self,
        db: AsyncSession,
        provider_auth_url: str,
        ctx: ApiContext,
        uow: UnitOfWork,
    ) -> Tuple[str, datetime, UUID]:
        proxy_expires = datetime.now(timezone.utc) + timedelta(hours=24)
        code = await self._sc_repo.generate_unique_redirect_code(db, length=8)
        redirect_sess = await self._sc_repo.create_redirect_session(
            db, code=code, final_url=provider_auth_url, expires_at=proxy_expires, ctx=ctx, uow=uow
        )
        proxy_url = f"{core_settings.api_url}/source-connections/authorize/{code}"
        return proxy_url, proxy_expires, redirect_sess.id

    async def _create_init_session(
        self,
        db: AsyncSession,
        obj_in: SourceConnectionCreate,
        entry: SourceRegistryEntry,
        state: str,
        ctx: ApiContext,
        uow: UnitOfWork,
        *,
        redirect_session_id: Optional[UUID] = None,
        template_configs: Optional[dict] = None,
        additional_overrides: Optional[Dict[str, Any]] = None,
    ) -> Any:
        auth = obj_in.authentication
        client_id: Optional[str] = None
        client_secret: Optional[str] = None
        oauth_client_mode = "platform_default"

        if isinstance(auth, OAuthBrowserAuthentication):
            nested_id = auth.client_id or auth.consumer_key
            nested_secret = auth.client_secret or auth.consumer_secret
            if (nested_id and not nested_secret) or (nested_secret and not nested_id):
                raise HTTPException(
                    status_code=422,
                    detail="Custom OAuth requires both client_id and client_secret or neither",
                )
            if auth.client_id and auth.client_secret:
                client_id, client_secret = auth.client_id, auth.client_secret
                oauth_client_mode = "byoc_nested"
            elif auth.consumer_key and auth.consumer_secret:
                client_id, client_secret = auth.consumer_key, auth.consumer_secret
                oauth_client_mode = "byoc_nested"

        exclude_fields = {
            "client_id",
            "client_secret",
            "token_inject",
            "redirect_url",
            "auth_mode",
            "custom_client",
            "auth_method",
            "authentication",
        }
        payload = obj_in.model_dump(exclude=exclude_fields, exclude_none=True)

        overrides: Dict[str, Any] = {
            "client_id": client_id,
            "client_secret": client_secret,
            "oauth_client_mode": oauth_client_mode,
            "redirect_url": getattr(obj_in, "redirect_url", core_settings.app_url),
            "oauth_redirect_uri": f"{core_settings.api_url}/source-connections/callback",
            "template_configs": template_configs,
        }
        if additional_overrides:
            overrides.update(additional_overrides)

        expires_at = datetime.now(timezone.utc) + timedelta(minutes=30)

        return await self._sc_repo.create_init_session(
            db,
            obj_in={
                "organization_id": ctx.organization.id,
                "short_name": entry.short_name,
                "payload": payload,
                "overrides": overrides,
                "state": state,
                "status": ConnectionInitStatus.PENDING,
                "expires_at": expires_at,
                "redirect_session_id": redirect_session_id,
            },
            ctx=ctx,
            uow=uow,
        )

    # ------------------------------------------------------------------
    # Post-commit trigger
    # ------------------------------------------------------------------

    async def _trigger_provisioned_sync(
        self,
        db: AsyncSession,
        result: SyncProvisionResult,
        connection: schemas.Connection,
        source_connection_id: UUID,
        readable_collection_id: str,
        ctx: ApiContext,
    ) -> None:
        try:
            collection_schema = schemas.Collection.model_validate(
                await self._collection_repo.get_by_readable_id(db, readable_collection_id, ctx),
                from_attributes=True,
            )
        except Exception:
            ctx.logger.warning("Failed to load collection for sync trigger")
            return

        try:
            await self._event_bus.publish(
                SyncLifecycleEvent.pending(
                    organization_id=ctx.organization.id,
                    source_connection_id=source_connection_id,
                    sync_job_id=result.sync_job.id,
                    sync_id=result.sync.id,
                    collection_id=collection_schema.id,
                    source_type=connection.short_name,
                    collection_name=collection_schema.name,
                    collection_readable_id=collection_schema.readable_id,
                )
            )
        except Exception as e:
            ctx.logger.warning(f"Failed to publish sync.pending event: {e}")

        await self._temporal_workflow_service.run_source_connection_workflow(
            sync=result.sync,
            sync_job=result.sync_job,
            collection=collection_schema,
            connection=connection,
            ctx=ctx,
        )
