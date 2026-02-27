"""OAuth callback service — completes browser-based OAuth1/2 callback flows.

Replaces the legacy source_connection_service callback methods and
source_connection_service_helpers completion logic with proper DI.
"""

from collections.abc import Mapping
from typing import Any, Dict
from uuid import UUID, uuid4

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from airweave import schemas
from airweave.api.context import ApiContext
from airweave.core.events.source_connection import SourceConnectionLifecycleEvent
from airweave.core.events.sync import SyncLifecycleEvent
from airweave.core.logging import logger
from airweave.core.protocols.encryption import CredentialEncryptor
from airweave.core.protocols.event_bus import EventBus
from airweave.core.shared_models import AuthMethod, ConnectionStatus, SyncJobStatus
from airweave.db.unit_of_work import UnitOfWork
from airweave.domains.collections.protocols import CollectionRepositoryProtocol
from airweave.domains.connections.protocols import ConnectionRepositoryProtocol
from airweave.domains.credentials.protocols import IntegrationCredentialRepositoryProtocol
from airweave.domains.oauth.protocols import (
    OAuthFlowServiceProtocol,
    OAuthInitSessionRepositoryProtocol,
    OAuthSourceRepositoryProtocol,
)
from airweave.domains.oauth.types import OAuth1TokenResponse
from airweave.domains.organizations.repository import OrganizationRepositoryProtocol
from airweave.domains.source_connections.protocols import (
    ResponseBuilderProtocol,
    SourceConnectionRepositoryProtocol,
)
from airweave.domains.sources.protocols import SourceRegistryProtocol
from airweave.domains.sources.types import SourceRegistryEntry
from airweave.domains.syncs.protocols import (
    SyncJobRepositoryProtocol,
    SyncLifecycleServiceProtocol,
    SyncRecordServiceProtocol,
    SyncRepositoryProtocol,
)
from airweave.domains.temporal.protocols import TemporalWorkflowServiceProtocol
from airweave.models.collection import Collection
from airweave.models.connection_init_session import ConnectionInitSession, ConnectionInitStatus
from airweave.models.integration_credential import IntegrationType
from airweave.models.source import Source
from airweave.models.source_connection import SourceConnection
from airweave.platform.auth.schemas import OAuth1Settings, OAuth2TokenResponse
from airweave.platform.auth.settings import integration_settings
from airweave.schemas.source_connection import (
    AuthenticationMethod,
    ScheduleConfig,
)
from airweave.schemas.source_connection import (
    SourceConnection as SourceConnectionSchema,
)


class OAuthCallbackService:
    """Completes browser-based OAuth1/2 callback flows end-to-end.

    Responsibilities:
    1. Exchange authorization code/verifier for tokens (via OAuthFlowService)
    2. Reconstruct ApiContext from stored init session
    3. Wire up credential + connection on the shell source connection
    4. Provision sync via SyncLifecycleService
    5. Trigger initial sync workflow if requested
    """

    def __init__(
        self,
        *,
        oauth_flow_service: OAuthFlowServiceProtocol,
        init_session_repo: OAuthInitSessionRepositoryProtocol,
        response_builder: ResponseBuilderProtocol,
        source_registry: SourceRegistryProtocol,
        sync_lifecycle: SyncLifecycleServiceProtocol,
        sync_record_service: SyncRecordServiceProtocol,
        temporal_workflow_service: TemporalWorkflowServiceProtocol,
        event_bus: EventBus,
        organization_repo: OrganizationRepositoryProtocol,
        source_repo: OAuthSourceRepositoryProtocol,
        sc_repo: SourceConnectionRepositoryProtocol,
        credential_repo: IntegrationCredentialRepositoryProtocol,
        connection_repo: ConnectionRepositoryProtocol,
        collection_repo: CollectionRepositoryProtocol,
        sync_repo: SyncRepositoryProtocol,
        sync_job_repo: SyncJobRepositoryProtocol,
        credential_encryptor: CredentialEncryptor,
    ) -> None:
        """Store callback orchestration dependencies."""
        self._oauth_flow_service = oauth_flow_service
        self._init_session_repo = init_session_repo
        self._response_builder = response_builder
        self._source_registry = source_registry
        self._sync_lifecycle = sync_lifecycle
        self._sync_record_service = sync_record_service
        self._temporal_workflow_service = temporal_workflow_service
        self._event_bus = event_bus
        self._organization_repo = organization_repo
        self._source_repo = source_repo
        self._sc_repo = sc_repo
        self._credential_repo = credential_repo
        self._connection_repo = connection_repo
        self._collection_repo = collection_repo
        self._sync_repo = sync_repo
        self._sync_job_repo = sync_job_repo
        self._credential_encryptor = credential_encryptor

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def complete_oauth_callback(
        self,
        db: AsyncSession,
        *,
        state: str | None = None,
        code: str | None = None,
        oauth_token: str | None = None,
        oauth_verifier: str | None = None,
    ) -> SourceConnectionSchema:
        """Complete OAuth callback, auto-detecting OAuth1 vs OAuth2 params."""
        if oauth_token and oauth_verifier:
            return await self.complete_oauth1_callback(
                db,
                oauth_token=oauth_token,
                oauth_verifier=oauth_verifier,
            )

        if state and code:
            return await self.complete_oauth2_callback(
                db,
                state=state,
                code=code,
            )

        raise HTTPException(
            status_code=400,
            detail=(
                "Invalid OAuth callback: missing required parameters. "
                "Expected either (state + code) for OAuth2 or "
                "(oauth_token + oauth_verifier) for OAuth1"
            ),
        )

    async def complete_oauth2_callback(
        self,
        db: AsyncSession,
        *,
        state: str,
        code: str,
    ) -> SourceConnectionSchema:
        """Complete OAuth2 flow from callback."""
        init_session = await self._init_session_repo.get_by_state_no_auth(db, state=state)
        if not init_session:
            raise HTTPException(status_code=404, detail="OAuth2 session not found or expired")

        if init_session.status != ConnectionInitStatus.PENDING:
            raise HTTPException(
                status_code=400, detail=f"OAuth session already {init_session.status}"
            )

        ctx = await self._reconstruct_context(db, init_session)

        source_conn_shell = await self._sc_repo.get_by_init_session(
            db, init_session_id=init_session.id, ctx=ctx
        )
        if not source_conn_shell:
            raise HTTPException(status_code=404, detail="Source connection shell not found")

        token_response = await self._oauth_flow_service.complete_oauth2_callback(
            init_session.short_name, code, init_session.overrides, ctx
        )

        source = await self._source_repo.get_by_short_name(db, short_name=init_session.short_name)
        await self._validate_oauth2_token_or_raise(
            source=source,
            access_token=token_response.access_token,
            ctx=ctx,
        )

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
        """Complete OAuth1 flow from callback."""
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

        source_conn_shell = await self._sc_repo.get_by_init_session(
            db, init_session_id=init_session.id, ctx=ctx
        )
        if not source_conn_shell:
            raise HTTPException(status_code=404, detail="Source connection shell not found")

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
        """Reconstruct ApiContext from stored session data."""
        organization = await self._organization_repo.get_by_id(
            db, organization_id=init_session.organization_id, skip_access_validation=True
        )
        organization_schema = schemas.Organization.model_validate(
            organization, from_attributes=True
        )

        request_id = str(uuid4())

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
        source_conn_shell: SourceConnection,
        init_session: ConnectionInitSession,
        token_response: OAuth1TokenResponse,
        ctx: ApiContext,
    ) -> SourceConnection:
        """Complete OAuth1 connection after callback."""
        source = await self._source_repo.get_by_short_name(db, short_name=init_session.short_name)
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
        source_conn_shell: SourceConnection,
        init_session: ConnectionInitSession,
        token_response: OAuth2TokenResponse,
        ctx: ApiContext,
    ) -> SourceConnection:
        """Complete OAuth2 connection after callback."""
        source = await self._source_repo.get_by_short_name(db, short_name=init_session.short_name)
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
        source: Source,
        source_conn_shell: SourceConnection,
        init_session_id: UUID,
        payload: Dict[str, Any],
        auth_fields: Dict[str, Any],
        auth_method_to_save: AuthenticationMethod,
        is_oauth1: bool,
        ctx: ApiContext,
    ) -> SourceConnection:
        """Common logic for completing OAuth connections (shared by OAuth1/OAuth2)."""
        validated_config = self._validate_config(source, payload.get("config"))

        auth_type_name = "OAuth1" if is_oauth1 else "OAuth2"

        async with UnitOfWork(db) as uow:
            encrypted = self._credential_encryptor.encrypt(auth_fields)

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
            credential = await self._credential_repo.create(
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
            connection = await self._connection_repo.create(
                uow.session, obj_in=conn_in, ctx=ctx, uow=uow
            )

            collection = await self._get_collection(
                uow.session,
                payload.get("readable_collection_id") or source_conn_shell.readable_collection_id,
                ctx,
            )

            await uow.session.flush()
            await uow.session.refresh(connection)

            entry: SourceRegistryEntry = self._source_registry.get(source.short_name)
            source_class = entry.source_class_ref

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
                source_conn = await self._sc_repo.update(
                    uow.session,
                    db_obj=source_conn_shell,
                    obj_in=sc_update,
                    ctx=ctx,
                    uow=uow,
                )
            else:
                schedule_config = None
                raw_cron = (
                    payload.get("schedule", {}).get("cron")
                    if isinstance(payload.get("schedule"), dict)
                    else payload.get("cron_schedule")
                )
                if raw_cron:
                    schedule_config = ScheduleConfig(cron=raw_cron)

                destination_ids = await self._sync_record_service.resolve_destination_ids(
                    uow.session, ctx
                )

                sync_result = await self._sync_lifecycle.provision_sync(
                    uow.session,
                    name=payload.get("name") or source.name,
                    source_connection_id=connection.id,
                    destination_connection_ids=destination_ids,
                    collection_id=collection.id,
                    collection_readable_id=collection.readable_id,
                    source_entry=entry,
                    schedule_config=schedule_config,
                    run_immediately=True,
                    ctx=ctx,
                    uow=uow,
                )

                sc_update = {
                    "config_fields": validated_config,
                    "readable_collection_id": collection.readable_id,
                    "sync_id": sync_result.sync_id if sync_result else None,
                    "connection_id": connection.id,
                    "is_authenticated": True,
                }
                source_conn = await self._sc_repo.update(
                    uow.session,
                    db_obj=source_conn_shell,
                    obj_in=sc_update,
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

    async def _validate_oauth2_token_or_raise(
        self,
        *,
        source: Source | None,
        access_token: str,
        ctx: ApiContext,
    ) -> None:
        """Validate OAuth2 token using source implementation; fail callback if invalid."""
        if not source:
            return

        try:
            source_cls = self._source_registry.get(source.short_name).source_class_ref

            source_instance = await source_cls.create(access_token=access_token, config=None)
            source_instance.set_logger(ctx.logger)

            if hasattr(source_instance, "validate"):
                is_valid = await source_instance.validate()
                if not is_valid:
                    raise HTTPException(status_code=400, detail="OAuth token is invalid")
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Token validation failed: {e}") from e

    # ------------------------------------------------------------------
    # Private: finalization (response + sync trigger)
    # ------------------------------------------------------------------

    async def _finalize_callback(
        self,
        db: AsyncSession,
        source_conn: SourceConnection,
        ctx: ApiContext,
    ) -> SourceConnectionSchema:
        """Build response and trigger sync workflow if needed."""
        source_conn_response = await self._response_builder.build_response(db, source_conn, ctx)

        if source_conn.sync_id:
            sync = await self._sync_repo.get(db, id=source_conn.sync_id, ctx=ctx)
            if sync:
                jobs = await self._sync_job_repo.get_all_by_sync_id(db, sync_id=sync.id, ctx=ctx)
                if jobs and len(jobs) > 0:
                    sync_job = jobs[0]
                    if sync_job.status == SyncJobStatus.PENDING:
                        collection = await self._collection_repo.get_by_readable_id(
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

                            if not source_conn.connection_id:
                                raise ValueError(
                                    f"Source connection {source_conn.id} has no connection_id"
                                )
                            conn_model = await self._connection_repo.get(
                                db, id=source_conn.connection_id, ctx=ctx
                            )
                            if not conn_model:
                                raise ValueError(
                                    f"Connection {source_conn.connection_id} not found"
                                )
                            connection_schema = schemas.Connection.model_validate(
                                conn_model, from_attributes=True
                            )

                            try:
                                await self._event_bus.publish(
                                    SyncLifecycleEvent.pending(
                                        organization_id=ctx.organization.id,
                                        source_connection_id=source_conn.id,
                                        sync_job_id=sync_job_schema.id,
                                        sync_id=sync_schema.id,
                                        collection_id=collection_schema.id,
                                        source_type=connection_schema.short_name,
                                        collection_name=collection_schema.name,
                                        collection_readable_id=collection_schema.readable_id,
                                    )
                                )
                            except Exception as e:
                                ctx.logger.warning(f"Failed to publish sync.pending event: {e}")

                            await self._temporal_workflow_service.run_source_connection_workflow(
                                sync=sync_schema,
                                sync_job=sync_job_schema,
                                collection=collection_schema,
                                connection=connection_schema,
                                ctx=ctx,
                            )

        await self._event_bus.publish(
            SourceConnectionLifecycleEvent.auth_completed(
                organization_id=ctx.organization.id,
                source_connection_id=source_conn_response.id,
                source_type=source_conn_response.short_name,
                collection_readable_id=source_conn_response.readable_collection_id,
            )
        )

        return source_conn_response

    # ------------------------------------------------------------------
    # Private: inline helpers
    # ------------------------------------------------------------------

    def _validate_config(
        self,
        source: Source,
        config_fields: Mapping[str, Any] | None,
    ) -> Dict[str, Any]:
        """Validate config fields using source_registry."""
        if not config_fields:
            return {}

        try:
            entry = self._source_registry.get(source.short_name)
        except KeyError:
            raise HTTPException(
                status_code=500,
                detail=f"Source '{source.short_name}' is not registered",
            )

        if not isinstance(config_fields, Mapping):
            raise HTTPException(status_code=422, detail="Invalid config fields: expected object")

        payload = dict(config_fields)

        if not entry.config_ref:
            return payload

        try:
            config_class = entry.config_ref
            model = config_class.model_validate(payload)
            return model.model_dump()

        except Exception as e:
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
    ) -> Collection:
        """Get collection by readable ID."""
        if not collection_id:
            raise HTTPException(status_code=400, detail="Collection is required")

        collection = await self._collection_repo.get_by_readable_id(
            db, readable_id=collection_id, ctx=ctx
        )
        if not collection:
            raise HTTPException(status_code=404, detail=f"Collection '{collection_id}' not found")
        return collection
