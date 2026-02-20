"""OAuth callback service — completes browser-based OAuth1/2 callback flows.

Ported from:
- source_connection_service.complete_oauth1_callback L1810-1883
- source_connection_service.complete_oauth2_callback L1885-1941
- source_connection_service._finalize_oauth_callback L1943-2004
- source_connection_service_helpers.reconstruct_context_from_session L177-222
- source_connection_service_helpers.complete_oauth1_connection L1385-1460
- source_connection_service_helpers.complete_oauth2_connection L1462-1535
- source_connection_service_helpers._complete_oauth_connection_common L1537-1718
"""

import uuid as uuid_mod
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from airweave import crud, schemas
from airweave.api.context import ApiContext
from airweave.core import credentials
from airweave.core.shared_models import AuthMethod, ConnectionStatus, SyncJobStatus
from airweave.db.unit_of_work import UnitOfWork
from airweave.domains.oauth.protocols import (
    OAuthFlowServiceProtocol,
    OAuthInitSessionRepositoryProtocol,
)
from airweave.domains.source_connections.protocols import ResponseBuilderProtocol
from airweave.domains.sources.protocols import SourceRegistryProtocol
from airweave.models.connection_init_session import ConnectionInitSession, ConnectionInitStatus
from airweave.models.integration_credential import IntegrationType
from airweave.schemas.source_connection import (
    AuthenticationMethod,
    SourceConnection as SourceConnectionSchema,
)


class OAuthCallbackService:
    """Completes browser-based OAuth1/2 callback flows end-to-end.

    Responsibilities:
    1. Exchange authorization code/verifier for tokens (via OAuthFlowService)
    2. Reconstruct ApiContext from stored init session
    3. Wire up credential + connection on the shell source connection
    4. Trigger initial sync if requested
    """

    def __init__(
        self,
        *,
        oauth_flow_service: OAuthFlowServiceProtocol,
        init_session_repo: OAuthInitSessionRepositoryProtocol,
        response_builder: ResponseBuilderProtocol,
        source_registry: SourceRegistryProtocol,
        event_bus: Any,
    ) -> None:
        self._oauth_flow_service = oauth_flow_service
        self._init_session_repo = init_session_repo
        self._response_builder = response_builder
        self._source_registry = source_registry
        self._event_bus = event_bus

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def complete_oauth2_callback(
        self,
        db: AsyncSession,
        *,
        state: str,
        code: str,
    ) -> SourceConnectionSchema:
        """Complete OAuth2 flow from callback.

        Ported from source_connection_service.complete_oauth2_callback L1885-1941.
        """
        init_session = await self._init_session_repo.get_by_state_no_auth(db, state=state)
        if not init_session:
            raise HTTPException(status_code=404, detail="OAuth2 session not found or expired")

        if init_session.status != ConnectionInitStatus.PENDING:
            raise HTTPException(
                status_code=400, detail=f"OAuth session already {init_session.status}"
            )

        ctx = await self._reconstruct_context(db, init_session)

        source_conn_shell = await crud.source_connection.get_by_query_and_org(
            db, ctx=ctx, connection_init_session_id=init_session.id
        )
        if not source_conn_shell:
            raise HTTPException(status_code=404, detail="Source connection shell not found")

        token_response = await self._oauth_flow_service.complete_oauth2_callback(
            init_session.short_name, code, init_session.overrides, ctx
        )

        source = await crud.source.get_by_short_name(db, short_name=init_session.short_name)
        if source:
            try:
                entry = self._source_registry.get(init_session.short_name)
                source_cls = entry.source_class_ref
                source_instance = await source_cls.create(
                    access_token=token_response.access_token, config=None
                )
                source_instance.set_logger(ctx.logger)
                if hasattr(source_instance, "validate"):
                    is_valid = await source_instance.validate()
                    if not is_valid:
                        ctx.logger.warning(
                            f"OAuth2 token validation failed for {init_session.short_name}"
                        )
            except Exception as e:
                ctx.logger.warning(f"OAuth2 token validation skipped: {e}")

        source_conn = await self._complete_oauth2_connection(
            db, source_conn_shell, init_session, token_response, ctx
        )

        return await self._finalize_callback(db, source_conn, ctx)

    async def complete_oauth1_callback(
        self,
        db: AsyncSession,
        *,
        oauth_token: str,
        oauth_verifier: str,
    ) -> SourceConnectionSchema:
        """Complete OAuth1 flow from callback.

        Ported from source_connection_service.complete_oauth1_callback L1810-1883.
        """
        init_session = await self._init_session_repo.get_by_oauth_token_no_auth(
            db, oauth_token=oauth_token
        )
        if not init_session:
            raise HTTPException(
                status_code=404,
                detail=(
                    "OAuth1 session not found or expired. Request token may have been used already."
                ),
            )

        if init_session.status != ConnectionInitStatus.PENDING:
            raise HTTPException(
                status_code=400, detail=f"OAuth session already {init_session.status}"
            )

        ctx = await self._reconstruct_context(db, init_session)

        source_conn_shell = await crud.source_connection.get_by_query_and_org(
            db, ctx=ctx, connection_init_session_id=init_session.id
        )
        if not source_conn_shell:
            raise HTTPException(status_code=404, detail="Source connection shell not found")

        from airweave.platform.auth.schemas import OAuth1Settings
        from airweave.platform.auth.settings import integration_settings

        oauth_settings = await integration_settings.get_by_short_name(init_session.short_name)

        if not isinstance(oauth_settings, OAuth1Settings):
            raise HTTPException(
                status_code=400,
                detail=f"Source {init_session.short_name} is not configured for OAuth1",
            )

        token_response = await self._oauth_flow_service.complete_oauth1_callback(
            init_session.short_name,
            oauth_verifier,
            init_session.overrides,
            oauth_settings,
            ctx,
        )

        source_conn = await self._complete_oauth1_connection(
            db, source_conn_shell, init_session, token_response, ctx
        )

        return await self._finalize_callback(db, source_conn, ctx)

    # ------------------------------------------------------------------
    # Private: context reconstruction
    # ------------------------------------------------------------------

    async def _reconstruct_context(
        self, db: AsyncSession, init_session: ConnectionInitSession
    ) -> ApiContext:
        """Reconstruct ApiContext from stored session data.

        Ported from source_connection_service_helpers.reconstruct_context_from_session L177-222.
        """
        from airweave.core.logging import logger

        organization = await crud.organization.get(
            db, id=init_session.organization_id, skip_access_validation=True
        )
        organization_schema = schemas.Organization.model_validate(
            organization, from_attributes=True
        )

        request_id = str(uuid_mod.uuid4())

        base_logger = logger.with_context(
            request_id=request_id,
            organization_id=str(organization_schema.id),
            organization_name=organization_schema.name,
            auth_method=AuthMethod.OAUTH_CALLBACK.value,
            context_base="oauth",
        )

        return ApiContext(
            request_id=request_id,
            organization=organization_schema,
            user=None,
            auth_method=AuthMethod.OAUTH_CALLBACK,
            auth_metadata={"session_id": str(init_session.id)},
            logger=base_logger,
        )

    # ------------------------------------------------------------------
    # Private: OAuth1 / OAuth2 connection completion
    # ------------------------------------------------------------------

    async def _complete_oauth1_connection(
        self,
        db: AsyncSession,
        source_conn_shell: Any,
        init_session: ConnectionInitSession,
        token_response: Any,
        ctx: ApiContext,
    ) -> Any:
        """Complete OAuth1 connection after callback.

        Ported from source_connection_service_helpers.complete_oauth1_connection L1385-1460.
        """
        source = await crud.source.get_by_short_name(db, short_name=init_session.short_name)
        if not source:
            raise HTTPException(
                status_code=404, detail=f"Source '{init_session.short_name}' not found"
            )

        init_session_id = init_session.id
        payload = init_session.payload or {}
        overrides = init_session.overrides or {}

        auth_fields: Dict[str, Any] = {
            "oauth_token": token_response.oauth_token,
            "oauth_token_secret": token_response.oauth_token_secret,
        }

        consumer_key = overrides.get("consumer_key")
        consumer_secret = overrides.get("consumer_secret")

        if consumer_key:
            auth_fields["consumer_key"] = consumer_key
        if consumer_secret:
            auth_fields["consumer_secret"] = consumer_secret

        from airweave.platform.auth.schemas import OAuth1Settings
        from airweave.platform.auth.settings import integration_settings

        try:
            platform_settings = await integration_settings.get_by_short_name(
                init_session.short_name
            )
            if isinstance(platform_settings, OAuth1Settings):
                is_byoc = (
                    consumer_key is not None and consumer_key != platform_settings.consumer_key
                )
            else:
                is_byoc = False
        except Exception:
            is_byoc = False

        auth_method_to_save = (
            AuthenticationMethod.OAUTH_BYOC if is_byoc else AuthenticationMethod.OAUTH_BROWSER
        )

        return await self._complete_connection_common(
            db,
            source,
            source_conn_shell,
            init_session_id,
            payload,
            auth_fields,
            auth_method_to_save,
            is_oauth1=True,
            ctx=ctx,
        )

    async def _complete_oauth2_connection(
        self,
        db: AsyncSession,
        source_conn_shell: Any,
        init_session: ConnectionInitSession,
        token_response: Any,
        ctx: ApiContext,
    ) -> Any:
        """Complete OAuth2 connection after callback.

        Ported from source_connection_service_helpers.complete_oauth2_connection L1462-1535.
        """
        source = await crud.source.get_by_short_name(db, short_name=init_session.short_name)
        if not source:
            raise HTTPException(
                status_code=404, detail=f"Source '{init_session.short_name}' not found"
            )

        init_session_id = init_session.id
        payload = init_session.payload or {}
        overrides = init_session.overrides or {}

        auth_fields: Dict[str, Any] = token_response.model_dump()

        if overrides.get("client_id"):
            auth_fields["client_id"] = overrides["client_id"]
        if overrides.get("client_secret"):
            auth_fields["client_secret"] = overrides["client_secret"]

        auth_method_to_save = (
            AuthenticationMethod.OAUTH_BYOC
            if (overrides.get("client_id") and overrides.get("client_secret"))
            else AuthenticationMethod.OAUTH_BROWSER
        )

        if init_session.short_name == "salesforce" and "instance_url" in auth_fields:
            instance_url_from_response = auth_fields.get("instance_url", "")
            if instance_url_from_response:
                instance_url_normalized = instance_url_from_response.replace(
                    "https://", ""
                ).replace("http://", "")

                if not payload.get("config"):
                    payload["config"] = {}
                payload["config"]["instance_url"] = instance_url_normalized

                ctx.logger.info(
                    f"Updated Salesforce instance_url from OAuth response: "
                    f"{instance_url_normalized}"
                )

        return await self._complete_connection_common(
            db,
            source,
            source_conn_shell,
            init_session_id,
            payload,
            auth_fields,
            auth_method_to_save,
            is_oauth1=False,
            ctx=ctx,
        )

    # ------------------------------------------------------------------
    # Private: shared completion logic
    # ------------------------------------------------------------------

    async def _complete_connection_common(  # noqa: C901
        self,
        db: AsyncSession,
        source: Any,
        source_conn_shell: Any,
        init_session_id: UUID,
        payload: Dict[str, Any],
        auth_fields: Dict[str, Any],
        auth_method_to_save: AuthenticationMethod,
        is_oauth1: bool,
        ctx: ApiContext,
    ) -> Any:
        """Common logic for completing OAuth connections (shared by OAuth1/OAuth2).

        Ported from source_connection_service_helpers._complete_oauth_connection_common L1537-1718.
        """
        validated_config = self._validate_config(source, payload.get("config"), ctx)

        auth_type_name = "OAuth1" if is_oauth1 else "OAuth2"

        async with UnitOfWork(db) as uow:
            encrypted = credentials.encrypt(auth_fields)

            cred_in = schemas.IntegrationCredentialCreateEncrypted(
                name=f"{source.name} {auth_type_name} Credential",
                description=f"{auth_type_name} credentials for {source.name}",
                integration_short_name=source.short_name,
                integration_type=IntegrationType.SOURCE,
                authentication_method=auth_method_to_save,
                oauth_type=getattr(source, "oauth_type", None),
                encrypted_credentials=encrypted,
                auth_config_class=source.auth_config_class,
            )
            credential = await crud.integration_credential.create(
                uow.session, obj_in=cred_in, ctx=ctx, uow=uow
            )

            await uow.session.flush()
            await uow.session.refresh(credential)

            conn_in = schemas.ConnectionCreate(
                name=payload.get("name", f"Connection to {source.name}"),
                integration_type=IntegrationType.SOURCE,
                status=ConnectionStatus.ACTIVE,
                integration_credential_id=credential.id,
                short_name=source.short_name,
            )
            connection = await crud.connection.create(uow.session, obj_in=conn_in, ctx=ctx, uow=uow)

            collection = await self._get_collection(
                uow.session,
                payload.get("readable_collection_id") or source_conn_shell.readable_collection_id,
                ctx,
            )

            await db.flush()
            await db.refresh(connection)

            try:
                entry = self._source_registry.get(source.short_name)
                source_class = entry.source_class_ref
            except KeyError:
                from airweave.platform.locator import resource_locator

                source_class = resource_locator.get_source(source)

            is_federated = getattr(source_class, "federated_search", False)

            if is_federated:
                ctx.logger.info(
                    f"Skipping sync creation for federated search source '{source.short_name}'. "
                    "Federated search sources are searched at query time."
                )
                sc_update: Dict[str, Any] = {
                    "config_fields": validated_config,
                    "readable_collection_id": collection.readable_id,
                    "sync_id": None,
                    "connection_id": connection.id,
                    "is_authenticated": True,
                }
                source_conn = await crud.source_connection.update(
                    uow.session,
                    db_obj=source_conn_shell,
                    obj_in=sc_update,
                    ctx=ctx,
                    uow=uow,
                )
            else:
                cron_schedule = (
                    payload.get("schedule", {}).get("cron")
                    if isinstance(payload.get("schedule"), dict)
                    else payload.get("cron_schedule")
                )
                if cron_schedule is None:
                    if getattr(source_class, "supports_continuous", False):
                        cron_schedule = "*/5 * * * *"
                        ctx.logger.info(
                            "No cron schedule provided for continuous source '%s', "
                            "defaulting to 5-minute incremental syncs",
                            source.short_name,
                        )
                    else:
                        now_utc = datetime.now(timezone.utc)
                        minute = now_utc.minute
                        hour = now_utc.hour
                        cron_schedule = f"{minute} {hour} * * *"
                        ctx.logger.info(
                            "No cron schedule provided, defaulting to daily full sync "
                            "at %02d:%02d UTC",
                            hour,
                            minute,
                        )

                # TODO: replace with SyncLifecycleService.provision_sync
                from airweave.core.source_connection_service_helpers import (
                    source_connection_helpers,
                )

                sync, sync_job = await source_connection_helpers.create_sync_without_schedule(
                    uow.session,
                    name=payload.get("name") or source.name,
                    connection_id=connection.id,
                    collection_id=collection.id,
                    collection_readable_id=collection.readable_id,
                    cron_schedule=cron_schedule,
                    run_immediately=True,
                    ctx=ctx,
                    uow=uow,
                )

                sc_update = {
                    "config_fields": validated_config,
                    "readable_collection_id": collection.readable_id,
                    "sync_id": sync.id,
                    "connection_id": connection.id,
                    "is_authenticated": True,
                }
                source_conn = await crud.source_connection.update(
                    uow.session,
                    db_obj=source_conn_shell,
                    obj_in=sc_update,
                    ctx=ctx,
                    uow=uow,
                )

                await uow.session.flush()

                # TODO: replace with SyncLifecycleService.provision_sync
                from airweave.platform.temporal.schedule_service import (
                    temporal_schedule_service,
                )

                await temporal_schedule_service.create_or_update_schedule(
                    sync_id=sync.id,
                    cron_schedule=cron_schedule,
                    db=uow.session,
                    ctx=ctx,
                    uow=uow,
                )

            await self._init_session_repo.mark_completed(
                uow.session,
                session_id=init_session_id,
                final_connection_id=sc_update["connection_id"],
                ctx=ctx,
            )

            await uow.commit()
            await uow.session.refresh(source_conn)

        return source_conn

    # ------------------------------------------------------------------
    # Private: finalization (response + sync trigger)
    # ------------------------------------------------------------------

    async def _finalize_callback(
        self,
        db: AsyncSession,
        source_conn: Any,
        ctx: ApiContext,
    ) -> SourceConnectionSchema:
        """Build response and trigger sync workflow if needed.

        Ported from source_connection_service._finalize_oauth_callback L1943-2004.
        """
        source_conn_response = await self._response_builder.build_response(db, source_conn, ctx)

        if source_conn.sync_id:
            sync = await crud.sync.get(db, id=source_conn.sync_id, ctx=ctx)
            if sync:
                jobs = await crud.sync_job.get_all_by_sync_id(db, sync_id=sync.id)
                if jobs and len(jobs) > 0:
                    sync_job = jobs[0]
                    if sync_job.status == SyncJobStatus.PENDING:
                        collection = await crud.collection.get_by_readable_id(
                            db, readable_id=source_conn.readable_collection_id, ctx=ctx
                        )
                        if collection:
                            collection_schema = schemas.Collection.model_validate(
                                collection, from_attributes=True
                            )
                            sync_job_schema = schemas.SyncJob.model_validate(
                                sync_job, from_attributes=True
                            )
                            sync_schema = schemas.Sync.model_validate(sync, from_attributes=True)

                            connection_schema = await self._get_connection_for_source_connection(
                                db=db, source_connection=source_conn, ctx=ctx
                            )

                            from airweave.core.temporal_service import temporal_service

                            await temporal_service.run_source_connection_workflow(
                                sync=sync_schema,
                                sync_job=sync_job_schema,
                                collection=collection_schema,
                                connection=connection_schema,
                                ctx=ctx,
                            )

        return source_conn_response

    # ------------------------------------------------------------------
    # Private: inline helpers
    # ------------------------------------------------------------------

    def _validate_config(
        self,
        source: Any,
        config_fields: Any,
        ctx: ApiContext,
    ) -> Dict[str, Any]:
        """Validate config fields using source_registry. Synchronous since no DB needed."""
        if not config_fields:
            return {}

        try:
            entry = self._source_registry.get(source.short_name)
        except KeyError:
            return {}

        if not entry.config_ref:
            from collections.abc import Mapping

            if isinstance(config_fields, Mapping):
                return dict(config_fields)
            if hasattr(config_fields, "model_dump"):
                return config_fields.model_dump()
            return {}

        try:
            from collections.abc import Mapping

            if isinstance(config_fields, Mapping):
                payload = dict(config_fields)
            elif hasattr(config_fields, "model_dump"):
                payload = config_fields.model_dump()
            elif hasattr(config_fields, "dict"):
                payload = config_fields.dict()
            elif hasattr(config_fields, "values"):
                v = config_fields.values
                payload = dict(v) if isinstance(v, Mapping) else v
            else:
                payload = config_fields

            config_class = entry.config_ref
            if hasattr(config_class, "model_validate"):
                model = config_class.model_validate(payload)
            else:
                model = config_class(**payload)

            if hasattr(model, "model_dump"):
                return model.model_dump()
            if hasattr(model, "dict"):
                return model.dict()
            return dict(model) if isinstance(model, dict) else payload

        except Exception as e:
            from pydantic import ValidationError

            if isinstance(e, ValidationError):
                errors = "; ".join(
                    [
                        f"{'.'.join(str(x) for x in err.get('loc', []))}: {err.get('msg')}"
                        for err in e.errors()
                    ]
                )
                raise HTTPException(
                    status_code=422, detail=f"Invalid config fields: {errors}"
                ) from e
            raise HTTPException(status_code=422, detail=str(e)) from e

    async def _get_collection(
        self, db: AsyncSession, collection_id: str, ctx: ApiContext
    ) -> schemas.Collection:
        """Inline helper: get collection by readable ID."""
        if not collection_id:
            raise HTTPException(status_code=400, detail="Collection is required")

        collection = await crud.collection.get_by_readable_id(
            db, readable_id=collection_id, ctx=ctx
        )
        if not collection:
            raise HTTPException(status_code=404, detail=f"Collection '{collection_id}' not found")
        return collection

    async def _get_connection_for_source_connection(
        self, db: AsyncSession, source_connection: Any, ctx: ApiContext
    ) -> schemas.Connection:
        """Inline helper: get Connection for a SourceConnection."""
        if not source_connection.connection_id:
            raise ValueError(f"Source connection {source_connection.id} has no connection_id")

        connection = await crud.connection.get(db=db, id=source_connection.connection_id, ctx=ctx)
        if not connection:
            raise ValueError(f"Connection {source_connection.connection_id} not found")

        return schemas.Connection.model_validate(connection, from_attributes=True)
