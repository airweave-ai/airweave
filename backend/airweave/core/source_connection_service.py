"""Clean source connection service with auth method inference."""

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from airweave import crud, schemas
from airweave.analytics import business_events
from airweave.api.context import ApiContext
from airweave.core.auth_provider_service import auth_provider_service
from airweave.core.config import settings as core_settings
from airweave.core.shared_models import SyncJobStatus
from airweave.core.sync_service import sync_service
from airweave.core.temporal_service import temporal_service
from airweave.crud import connection_init_session
from airweave.db.unit_of_work import UnitOfWork
from airweave.models.connection_init_session import ConnectionInitStatus
from airweave.platform.auth.services import oauth2_service
from airweave.platform.auth.settings import integration_settings
from airweave.platform.sources._base import BaseSource
from airweave.schemas.source_connection import (
    AuthenticationMethod,
    AuthProviderAuthentication,
    DirectAuthentication,
    OAuthBrowserAuthentication,
    OAuthTokenAuthentication,
    SourceConnection,
    SourceConnectionCreate,
    SourceConnectionListItem,
    SourceConnectionUpdate,
)


class SourceConnectionService:
    """Service for managing source connections and their lifecycle."""

    def _get_default_cron_schedule(self, ctx: ApiContext) -> str:
        """Generate a default daily cron schedule based on current UTC time.

        Returns:
            A cron expression for daily execution at the current UTC time.
        """
        from datetime import datetime, timezone

        now_utc = datetime.now(timezone.utc)
        minute = now_utc.minute
        hour = now_utc.hour
        # Format: minute hour day_of_month month day_of_week
        # e.g., "30 14 * * *" = run at 14:30 every day
        cron_schedule = f"{minute} {hour} * * *"
        ctx.logger.info(
            f"No cron schedule provided, defaulting to daily at {hour:02d}:{minute:02d} UTC"
        )
        return cron_schedule

    """Clean service with automatic auth method inference.

    Key improvements:
    - Auth method automatically inferred from request body
    - Uses AuthenticationMethod enum consistently
    - Clean separation of concerns
    """

    def _determine_auth_method(
        self, obj_in: SourceConnectionCreate, source_class: type[BaseSource]
    ) -> AuthenticationMethod:
        """Determine authentication method from the nested authentication object.

        Args:
            obj_in: The source connection creation request
            source_class: The source class to check supported auth methods

        Returns:
            The determined authentication method

        Raises:
            HTTPException: If authentication type cannot be determined
        """
        auth = obj_in.authentication

        # If no authentication provided, infer based on source capabilities
        if auth is None:
            return AuthenticationMethod.OAUTH_BROWSER

        if isinstance(auth, DirectAuthentication):
            return AuthenticationMethod.DIRECT
        elif isinstance(auth, OAuthTokenAuthentication):
            return AuthenticationMethod.OAUTH_TOKEN
        elif isinstance(auth, OAuthBrowserAuthentication):
            # Check if BYOC based on presence of client credentials
            if auth.client_id and auth.client_secret:
                return AuthenticationMethod.OAUTH_BYOC
            else:
                return AuthenticationMethod.OAUTH_BROWSER
        elif isinstance(auth, AuthProviderAuthentication):
            return AuthenticationMethod.AUTH_PROVIDER
        else:
            raise HTTPException(status_code=400, detail="Invalid authentication configuration")

    async def create(
        self,
        db: AsyncSession,
        *,
        obj_in: SourceConnectionCreate,
        ctx: ApiContext,
    ) -> SourceConnection:
        """Create a source connection with nested authentication.

        The authentication method is determined by the type of the authentication field.
        """
        # Get source and validate
        source = await self._get_and_validate_source(db, obj_in.short_name)
        source_class = self._get_source_class(source.class_name)

        # Generate default name if not provided
        if obj_in.name is None:
            obj_in.name = f"{source.name} Connection"

        # Determine auth method from nested authentication type
        auth_method = self._determine_auth_method(obj_in, source_class)

        # Validate that source supports the auth method
        if not source_class.supports_auth_method(auth_method):
            supported = source_class.get_supported_auth_methods()
            raise HTTPException(
                status_code=400,
                detail=f"Source {obj_in.short_name} does not support this authentication method. "
                f"Supported methods: {[m.value for m in supported]}",
            )

        # Route based on auth method
        if auth_method == AuthenticationMethod.DIRECT:
            source_connection = await self._create_with_direct_auth(db, obj_in=obj_in, ctx=ctx)
        elif auth_method == AuthenticationMethod.OAUTH_BROWSER:
            source_connection = await self._create_with_oauth_browser(db, obj_in=obj_in, ctx=ctx)
        elif auth_method == AuthenticationMethod.OAUTH_TOKEN:
            source_connection = await self._create_with_oauth_token(db, obj_in=obj_in, ctx=ctx)
        elif auth_method == AuthenticationMethod.OAUTH_BYOC:
            source_connection = await self._create_with_oauth_byoc(db, obj_in=obj_in, ctx=ctx)
        elif auth_method == AuthenticationMethod.AUTH_PROVIDER:
            source_connection = await self._create_with_auth_provider(db, obj_in=obj_in, ctx=ctx)
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported authentication method: {auth_method.value}",
            )

        # Track analytics
        business_events.track_source_connection_created(
            ctx=ctx,
            connection_id=source_connection.id,
            source_short_name=source_connection.short_name,
        )

        return source_connection

    async def get(
        self,
        db: AsyncSession,
        *,
        id: UUID,
        ctx: ApiContext,
    ) -> SourceConnection:
        """Get a source connection with complete details."""
        source_conn = await crud.source_connection.get(db, id=id, ctx=ctx)
        if not source_conn:
            raise HTTPException(status_code=404, detail="Source connection not found")

        return await self._build_source_connection_response(db, source_conn, ctx)

    async def list(
        self,
        db: AsyncSession,
        *,
        ctx: ApiContext,
        readable_collection_id: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[SourceConnectionListItem]:
        """List source connections with complete stats."""
        # Use the new CRUD method that fetches all data efficiently
        connections_with_stats = await crud.source_connection.get_multi_with_stats(
            db, ctx=ctx, collection_id=readable_collection_id, skip=skip, limit=limit
        )

        # Transform to schema objects
        result = []
        for data in connections_with_stats:
            # Extract last job status for status computation
            last_job = data.get("last_job", {})
            last_job_status = last_job.get("status") if last_job else None

            # Build clean list item
            result.append(
                SourceConnectionListItem(
                    # Core fields
                    id=data["id"],
                    name=data["name"],
                    short_name=data["short_name"],
                    readable_collection_id=data["readable_collection_id"],
                    created_at=data["created_at"],
                    modified_at=data["modified_at"],
                    # Authentication
                    is_authenticated=data["is_authenticated"],
                    authentication_method=data.get("authentication_method"),
                    # Stats
                    entity_count=data.get("entity_count", 0),
                    # Hidden fields for status computation
                    is_active=data.get("is_active", True),
                    last_job_status=last_job_status,
                )
            )

        return result

    async def update(
        self,
        db: AsyncSession,
        *,
        id: UUID,
        obj_in: SourceConnectionUpdate,
        ctx: ApiContext,
    ) -> SourceConnection:
        """Update a source connection."""
        source_conn = await crud.source_connection.get(db, id=id, ctx=ctx)
        if not source_conn:
            raise HTTPException(status_code=404, detail="Source connection not found")

        async with UnitOfWork(db) as uow:
            # Update fields
            update_data = obj_in.model_dump(exclude_unset=True)

            # Handle config update
            if "config" in update_data:
                validated_config = await self._validate_config_fields(
                    uow.session, source_conn.short_name, update_data["config"], ctx
                )
                update_data["config_fields"] = validated_config
                del update_data["config"]

            # Handle schedule update
            if "schedule" in update_data and update_data["schedule"]:
                if source_conn.sync_id:
                    await self._update_sync_schedule(
                        uow.session,
                        source_conn.sync_id,
                        update_data["schedule"].get("cron"),
                        ctx,
                        uow,
                    )
                    del update_data["schedule"]

            # Handle credential update (direct auth only)
            if "credentials" in update_data:
                auth_method = self._determine_auth_method(source_conn)
                if auth_method != AuthenticationMethod.DIRECT:
                    raise HTTPException(
                        status_code=400,
                        detail="Credentials can only be updated for direct authentication",
                    )
                await self._update_auth_fields(
                    uow.session, source_conn, update_data["credentials"], ctx, uow
                )
                del update_data["credentials"]

            # Update source connection
            if update_data:
                source_conn = await crud.source_connection.update(
                    uow.session,
                    db_obj=source_conn,
                    obj_in=update_data,
                    ctx=ctx,
                    uow=uow,
                )

            await uow.commit()
            await uow.session.refresh(source_conn)

        return await self._build_source_connection_response(db, source_conn, ctx)

    async def delete(
        self,
        db: AsyncSession,
        *,
        id: UUID,
        ctx: ApiContext,
    ) -> SourceConnection:
        """Delete a source connection and all related data."""
        source_conn = await crud.source_connection.get(db, id=id, ctx=ctx)
        if not source_conn:
            raise HTTPException(status_code=404, detail="Source connection not found")

        # Build response before deletion
        response = await self._build_source_connection_response(db, source_conn, ctx)

        # Clean up data
        if source_conn.sync_id:
            # Clean up destination data
            if source_conn.readable_collection_id:
                await self._cleanup_destination_data(db, source_conn, ctx)

            # Clean up Temporal schedules
            await self._cleanup_temporal_schedules(source_conn.sync_id, db, ctx)

        # Delete the source connection
        await crud.source_connection.remove(db, id=id, ctx=ctx)

        return response

    # Private creation handlers
    async def _create_with_direct_auth(
        self,
        db: AsyncSession,
        obj_in: SourceConnectionCreate,
        ctx: ApiContext,
    ) -> SourceConnection:
        """Create connection with direct authentication credentials."""
        from airweave.schemas.source_connection import DirectAuthentication

        source = await self._get_and_validate_source(db, obj_in.short_name)

        # Extract credentials from nested authentication
        if not obj_in.authentication or not isinstance(obj_in.authentication, DirectAuthentication):
            raise HTTPException(
                status_code=400, detail="Direct authentication requires credentials"
            )

        # Validate credentials
        validated_auth = await self._validate_auth_fields(
            db, obj_in.short_name, obj_in.authentication.credentials, ctx
        )
        validated_config = await self._validate_config_fields(
            db, obj_in.short_name, obj_in.config, ctx
        )

        # Validate credentials with source
        await self._validate_direct_auth(db, source, validated_auth, validated_config, ctx)

        async with UnitOfWork(db) as uow:
            # Get collection
            collection = await self._get_collection(uow.session, obj_in.readable_collection_id, ctx)

            # Create credential
            credential = await self._create_integration_credential(
                uow.session,
                source,
                validated_auth,
                ctx,
                uow,
                AuthenticationMethod.DIRECT,
            )
            await uow.session.flush()

            # Create connection
            connection = await self._create_connection(
                uow.session, obj_in.name, source, credential.id, ctx, uow
            )
            await uow.session.flush()

            # Create sync WITHOUT Temporal schedule (we'll create it after source_connection is set)
            cron_schedule = obj_in.schedule.cron if obj_in.schedule else None
            if cron_schedule is None:
                cron_schedule = self._get_default_cron_schedule(ctx)

            sync, sync_job = await self._create_sync_without_schedule(
                uow.session,
                obj_in.name,
                connection.id,
                collection.id,
                cron_schedule,
                obj_in.sync_immediately,
                ctx,
                uow,
            )
            await uow.session.flush()

            # Create source connection
            source_conn = await self._create_source_connection(
                uow.session,
                obj_in,
                connection.id,
                collection.readable_id,
                sync.id,
                validated_config,
                is_authenticated=True,
                ctx=ctx,
                uow=uow,
            )
            await uow.session.flush()

            # Now create the Temporal schedule after source_connection is linked to sync
            if cron_schedule and sync.id:
                from airweave.platform.temporal.schedule_service import temporal_schedule_service

                await temporal_schedule_service.create_or_update_schedule(
                    sync_id=sync.id,
                    cron_schedule=cron_schedule,
                    db=uow.session,
                    ctx=ctx,
                )

            # Convert to schemas while still in session
            if sync_job and obj_in.sync_immediately:
                # Ensure all models are flushed and refreshed before converting
                await uow.session.flush()
                await uow.session.refresh(sync_job)
                await uow.session.refresh(collection)

                sync_schema = schemas.Sync.model_validate(sync, from_attributes=True)
                sync_job_schema = schemas.SyncJob.model_validate(sync_job, from_attributes=True)
                collection_schema = schemas.Collection.model_validate(
                    collection, from_attributes=True
                )

            await uow.commit()
            await uow.session.refresh(source_conn)

            response = await self._build_source_connection_response(uow.session, source_conn, ctx)

        # Trigger sync if requested
        if sync_job and obj_in.sync_immediately:
            await self._trigger_sync_workflow(
                db, response, sync_schema, sync_job_schema, collection_schema, ctx
            )

        return response

    async def _create_with_oauth_browser(
        self,
        db: AsyncSession,
        obj_in: SourceConnectionCreate,
        ctx: ApiContext,
    ) -> SourceConnection:
        """Create shell connection and start OAuth browser flow."""
        from airweave.schemas.source_connection import OAuthBrowserAuthentication

        source = await self._get_and_validate_source(db, obj_in.short_name)

        # Extract OAuth config from nested authentication (or use defaults)
        oauth_auth = None
        if obj_in.authentication is not None:
            if not isinstance(obj_in.authentication, OAuthBrowserAuthentication):
                raise HTTPException(
                    status_code=400, detail="Invalid authentication type for OAuth browser"
                )
            oauth_auth = obj_in.authentication
        else:
            # Create default OAuth browser authentication
            oauth_auth = OAuthBrowserAuthentication()

        # Validate config
        validated_config = await self._validate_config_fields(
            db, obj_in.short_name, obj_in.config, ctx
        )

        # Generate OAuth URL
        oauth_settings = await integration_settings.get_by_short_name(source.short_name)
        if not oauth_settings:
            raise HTTPException(
                status_code=400,
                detail=f"OAuth not configured for source: {source.short_name}",
            )

        import secrets

        state = secrets.token_urlsafe(24)
        api_callback = f"{core_settings.api_url}/source-connections/callback"

        # Use custom client if provided
        client_id = oauth_auth.client_id if oauth_auth.client_id else None

        provider_auth_url = await oauth2_service.generate_auth_url_with_redirect(
            oauth_settings,
            redirect_uri=api_callback,
            client_id=client_id,
            state=state,
        )

        async with UnitOfWork(db) as uow:
            # Create shell source connection
            source_conn = await self._create_source_connection(
                uow.session,
                obj_in,
                connection_id=None,
                collection_id=obj_in.readable_collection_id,
                sync_id=None,
                config_fields=validated_config,
                is_authenticated=False,
                ctx=ctx,
                uow=uow,
            )

            # Generate proxy URL first to get the redirect_session_id
            proxy_url, proxy_expiry, redirect_session_id = await self._create_proxy_url(
                uow.session, provider_auth_url, ctx, uow
            )

            # Create init session with the redirect_session_id
            init_session = await self._create_init_session(
                uow.session, obj_in, state, ctx, uow, redirect_session_id=redirect_session_id
            )

            # Link them
            source_conn.connection_init_session_id = init_session.id
            uow.session.add(source_conn)

            # Add auth URL to response
            source_conn.authentication_url = proxy_url
            source_conn.authentication_url_expiry = proxy_expiry

            await uow.commit()
            await uow.session.refresh(source_conn)

            response = await self._build_source_connection_response(uow.session, source_conn, ctx)

        return response

    async def _create_with_oauth_token(
        self,
        db: AsyncSession,
        obj_in: SourceConnectionCreate,
        ctx: ApiContext,
    ) -> SourceConnection:
        """Create connection with injected OAuth token."""
        from airweave.schemas.source_connection import OAuthTokenAuthentication

        source = await self._get_and_validate_source(db, obj_in.short_name)

        # Extract token from nested authentication
        if not obj_in.authentication or not isinstance(
            obj_in.authentication, OAuthTokenAuthentication
        ):
            raise HTTPException(
                status_code=400, detail="OAuth token authentication requires an access token"
            )

        # Build OAuth credentials
        oauth_creds = {
            "access_token": obj_in.authentication.access_token,
            "refresh_token": obj_in.authentication.refresh_token,
            "token_type": "Bearer",
        }
        if obj_in.authentication.expires_at:
            oauth_creds["expires_at"] = obj_in.authentication.expires_at.isoformat()

        # Validate config
        validated_config = await self._validate_config_fields(
            db, obj_in.short_name, obj_in.config, ctx
        )

        # Validate token
        await self._validate_oauth_token(
            db, source, obj_in.authentication.access_token, validated_config, ctx
        )

        async with UnitOfWork(db) as uow:
            # Get collection
            collection = await self._get_collection(uow.session, obj_in.readable_collection_id, ctx)

            # Create credential with OAuth tokens
            credential = await self._create_integration_credential(
                uow.session,
                source,
                oauth_creds,
                ctx,
                uow,
                AuthenticationMethod.OAUTH_TOKEN,
            )
            await uow.session.flush()

            # Create connection
            connection = await self._create_connection(
                uow.session, obj_in.name, source, credential.id, ctx, uow
            )
            await uow.session.flush()

            # Create sync WITHOUT Temporal schedule (we'll create it after source_connection is set)
            cron_schedule = obj_in.schedule.cron if obj_in.schedule else None
            if cron_schedule is None:
                cron_schedule = self._get_default_cron_schedule(ctx)

            sync, sync_job = await self._create_sync_without_schedule(
                uow.session,
                obj_in.name,
                connection.id,
                collection.id,
                cron_schedule,
                obj_in.sync_immediately,
                ctx,
                uow,
            )
            await uow.session.flush()

            # Create source connection
            source_conn = await self._create_source_connection(
                uow.session,
                obj_in,
                connection.id,
                collection.readable_id,
                sync.id,
                validated_config,
                is_authenticated=True,
                ctx=ctx,
                uow=uow,
            )
            await uow.session.flush()

            # Now create the Temporal schedule after source_connection is linked to sync
            if cron_schedule and sync.id:
                from airweave.platform.temporal.schedule_service import temporal_schedule_service

                await temporal_schedule_service.create_or_update_schedule(
                    sync_id=sync.id,
                    cron_schedule=cron_schedule,
                    db=uow.session,
                    ctx=ctx,
                )

            # Convert to schemas while still in session
            if sync_job and obj_in.sync_immediately:
                # Ensure all models are flushed and refreshed before converting
                await uow.session.flush()
                await uow.session.refresh(sync_job)
                await uow.session.refresh(collection)

                sync_schema = schemas.Sync.model_validate(sync, from_attributes=True)
                sync_job_schema = schemas.SyncJob.model_validate(sync_job, from_attributes=True)
                collection_schema = schemas.Collection.model_validate(
                    collection, from_attributes=True
                )

            await uow.commit()
            await uow.session.refresh(source_conn)

            response = await self._build_source_connection_response(uow.session, source_conn, ctx)

        # Trigger sync if requested
        if sync_job and obj_in.sync_immediately:
            await self._trigger_sync_workflow(
                db, response, sync_schema, sync_job_schema, collection_schema, ctx
            )

        return response

    async def _create_with_oauth_byoc(
        self,
        db: AsyncSession,
        obj_in: SourceConnectionCreate,
        ctx: ApiContext,
    ) -> SourceConnection:
        """Create connection with bring-your-own-client OAuth."""
        from airweave.schemas.source_connection import OAuthBrowserAuthentication

        # Verify client credentials are present
        if not obj_in.authentication or not isinstance(
            obj_in.authentication, OAuthBrowserAuthentication
        ):
            raise HTTPException(
                status_code=400,
                detail="BYOC OAuth requires OAuth browser authentication with client credentials",
            )

        if not obj_in.authentication.client_id or not obj_in.authentication.client_secret:
            raise HTTPException(
                status_code=400, detail="BYOC OAuth requires client_id and client_secret"
            )

        # Use the browser flow with custom client
        return await self._create_with_oauth_browser(db, obj_in, ctx)

    async def _create_with_auth_provider(
        self,
        db: AsyncSession,
        obj_in: SourceConnectionCreate,
        ctx: ApiContext,
    ) -> SourceConnection:
        """Create connection using external auth provider."""
        from airweave.schemas.source_connection import AuthProviderAuthentication

        source = await self._get_and_validate_source(db, obj_in.short_name)

        # Extract provider info from nested authentication
        if not obj_in.authentication or not isinstance(
            obj_in.authentication, AuthProviderAuthentication
        ):
            raise HTTPException(
                status_code=400,
                detail="Auth provider authentication requires provider configuration",
            )

        # Validate auth provider exists
        auth_provider_conn = await crud.connection.get_by_readable_id(
            db, readable_id=obj_in.authentication.provider_readable_id, ctx=ctx
        )
        if not auth_provider_conn:
            raise HTTPException(
                status_code=404,
                detail=f"Auth provider '{obj_in.authentication.provider_readable_id}' not found",
            )

        # Validate provider config
        validated_auth_config = None
        if obj_in.authentication.provider_config:
            validated_auth_config = await auth_provider_service.validate_auth_provider_config(
                db, auth_provider_conn.short_name, obj_in.authentication.provider_config
            )

        # Validate source config
        validated_config = await self._validate_config_fields(
            db, obj_in.short_name, obj_in.config, ctx
        )

        async with UnitOfWork(db) as uow:
            # Get collection
            collection = await self._get_collection(uow.session, obj_in.readable_collection_id, ctx)

            # Create connection (no credential - auth provider handles it)
            connection = await self._create_connection(
                uow.session, obj_in.name, source, None, ctx, uow
            )
            await uow.session.flush()

            # Create sync WITHOUT Temporal schedule (we'll create it after source_connection is set)
            cron_schedule = obj_in.schedule.cron if obj_in.schedule else None
            if cron_schedule is None:
                cron_schedule = self._get_default_cron_schedule(ctx)

            sync, sync_job = await self._create_sync_without_schedule(
                uow.session,
                obj_in.name,
                connection.id,
                collection.id,
                cron_schedule,
                obj_in.sync_immediately,
                ctx,
                uow,
            )
            await uow.session.flush()

            # Create source connection
            source_conn = await self._create_source_connection(
                uow.session,
                obj_in,
                connection.id,
                collection.readable_id,
                sync.id,
                validated_config,
                is_authenticated=True,
                ctx=ctx,
                uow=uow,
                auth_provider_id=auth_provider_conn.readable_id,
                auth_provider_config=validated_auth_config,
            )
            await uow.session.flush()

            # Now create the Temporal schedule after source_connection is linked to sync
            if cron_schedule and sync.id:
                from airweave.platform.temporal.schedule_service import temporal_schedule_service

                await temporal_schedule_service.create_or_update_schedule(
                    sync_id=sync.id,
                    cron_schedule=cron_schedule,
                    db=uow.session,
                    ctx=ctx,
                )

            # Convert to schemas while still in session
            if sync_job and obj_in.sync_immediately:
                # Ensure all models are flushed and refreshed before converting
                await uow.session.flush()
                await uow.session.refresh(sync_job)
                await uow.session.refresh(collection)

                sync_schema = schemas.Sync.model_validate(sync, from_attributes=True)
                sync_job_schema = schemas.SyncJob.model_validate(sync_job, from_attributes=True)
                collection_schema = schemas.Collection.model_validate(
                    collection, from_attributes=True
                )

            await uow.commit()
            await uow.session.refresh(source_conn)

            response = await self._build_source_connection_response(uow.session, source_conn, ctx)

        # Trigger sync if requested
        if sync_job and obj_in.sync_immediately:
            await self._trigger_sync_workflow(
                db, response, sync_schema, sync_job_schema, collection_schema, ctx
            )

        return response

    # Helper methods

    async def _trigger_sync_workflow(
        self,
        db: AsyncSession,
        source_conn: schemas.SourceConnection,
        sync: schemas.Sync,
        sync_job: schemas.SyncJob,
        collection: schemas.Collection,
        ctx: ApiContext,
    ) -> None:
        """Trigger Temporal workflow for sync.

        Note: All parameters except db and ctx should be Pydantic schemas, not SQLAlchemy models.
        """
        # Get sync DAG
        sync_dag = await crud.sync_dag.get_by_sync_id(db, sync_id=sync.id, ctx=ctx)
        if not sync_dag:
            ctx.logger.error(f"Sync DAG not found for sync {sync.id}")
            return

        # Convert sync_dag to schema (it's the only model we fetch here)
        sync_dag_schema = schemas.SyncDag.model_validate(sync_dag, from_attributes=True)

        # Trigger workflow - all inputs are already schemas
        await temporal_service.run_source_connection_workflow(
            sync=sync,
            sync_job=sync_job,
            sync_dag=sync_dag_schema,
            collection=collection,
            source_connection=source_conn,
            ctx=ctx,
        )

    async def _get_and_validate_source(self, db: AsyncSession, short_name: str) -> schemas.Source:
        """Get and validate source exists."""
        source = await crud.source.get_by_short_name(db, short_name=short_name)
        if not source:
            raise HTTPException(status_code=404, detail=f"Source '{short_name}' not found")
        return source

    def _get_source_class(self, class_name: str) -> type[BaseSource]:
        """Get source class by name."""
        # Import the source module dynamically
        module_name = class_name.replace("Source", "").lower()

        # Handle special cases
        if module_name.startswith("google") and len(module_name) > 6:
            module_name = "google_" + module_name[6:]
        elif module_name.startswith("outlook") and len(module_name) > 7:
            module_name = "outlook_" + module_name[7:]

        module = __import__(f"airweave.platform.sources.{module_name}", fromlist=[class_name])
        return getattr(module, class_name)

    async def run(
        self,
        db: AsyncSession,
        *,
        id: UUID,
        ctx: ApiContext,
        force_full_sync: bool = False,
    ) -> schemas.SourceConnectionJob:
        """Trigger a sync run for a source connection."""
        source_conn = await crud.source_connection.get(db, id=id, ctx=ctx)
        if not source_conn:
            raise HTTPException(status_code=404, detail="Source connection not found")

        if not source_conn.sync_id:
            raise HTTPException(status_code=400, detail="Source connection has no associated sync")

        # Get sync_dag for the workflow
        sync_dag = await crud.sync_dag.get_by_sync_id(db, sync_id=source_conn.sync_id, ctx=ctx)
        if not sync_dag:
            raise HTTPException(
                status_code=400, detail="Source connection has no sync DAG configured"
            )

        # Run through Temporal
        collection = await crud.collection.get_by_readable_id(
            db, readable_id=source_conn.readable_collection_id, ctx=ctx
        )

        collection_schema = schemas.Collection.model_validate(collection, from_attributes=True)
        source_connection_schema = await self._build_source_connection_response(
            db, source_conn, ctx
        )
        sync_dag_schema = schemas.SyncDag.model_validate(sync_dag, from_attributes=True)

        # Trigger sync through Temporal only
        sync, sync_job = await sync_service.trigger_sync_run(
            db, sync_id=source_conn.sync_id, ctx=ctx
        )

        await temporal_service.run_source_connection_workflow(
            sync=sync,
            sync_job=sync_job,
            sync_dag=sync_dag_schema,
            collection=collection_schema,
            source_connection=source_connection_schema,
            ctx=ctx,
            force_full_sync=force_full_sync,
        )

        # Convert sync_job to SourceConnectionJob using the built-in conversion method
        sync_job_schema = schemas.SyncJob.model_validate(sync_job, from_attributes=True)
        return sync_job_schema.to_source_connection_job(source_connection_schema.id)

    async def get_jobs(
        self,
        db: AsyncSession,
        *,
        id: UUID,
        ctx: ApiContext,
        limit: int = 100,
    ) -> List[schemas.SourceConnectionJob]:
        """Get sync jobs for a source connection."""
        source_conn = await crud.source_connection.get(db, id=id, ctx=ctx)
        if not source_conn:
            raise HTTPException(status_code=404, detail="Source connection not found")

        if not source_conn.sync_id:
            return []

        sync_jobs = await sync_service.list_sync_jobs(
            db, ctx=ctx, sync_id=source_conn.sync_id, limit=limit
        )

        return [self._sync_job_to_source_connection_job(job, source_conn.id) for job in sync_jobs]

    async def cancel_job(
        self,
        db: AsyncSession,
        *,
        source_connection_id: UUID,
        job_id: UUID,
        ctx: ApiContext,
    ) -> schemas.SourceConnectionJob:
        """Cancel a running sync job for a source connection.

        Updates the job status in the database to CANCELLED and sends
        a cancellation request to the Temporal workflow if it's running.
        """
        # Verify source connection exists and user has access
        source_conn = await crud.source_connection.get(db, id=source_connection_id, ctx=ctx)
        if not source_conn:
            raise HTTPException(status_code=404, detail="Source connection not found")

        if not source_conn.sync_id:
            raise HTTPException(status_code=400, detail="Source connection has no associated sync")

        # Get the sync job and verify it belongs to this source connection
        sync_job = await crud.sync_job.get(db, id=job_id, ctx=ctx)
        if not sync_job:
            raise HTTPException(status_code=404, detail="Sync job not found")

        if sync_job.sync_id != source_conn.sync_id:
            raise HTTPException(
                status_code=400, detail="Sync job does not belong to this source connection"
            )

        # Check if job is in a cancellable state
        if sync_job.status not in [SyncJobStatus.PENDING, SyncJobStatus.RUNNING]:
            raise HTTPException(
                status_code=400, detail=f"Cannot cancel job in {sync_job.status} state"
            )

        # Update job status to CANCELLED in database
        from airweave.core.sync_job_service import sync_job_service

        await sync_job_service.update_status(
            sync_job_id=job_id,
            status=SyncJobStatus.CANCELLED,
            ctx=ctx,
            completed_at=datetime.utcnow(),
        )

        # Cancel the Temporal workflow if it's running
        if sync_job.status == SyncJobStatus.RUNNING:
            try:
                cancelled = await temporal_service.cancel_sync_job_workflow(str(job_id))
                if cancelled:
                    ctx.logger.info(f"Successfully cancelled Temporal workflow for job {job_id}")
                else:
                    ctx.logger.warning(f"No running Temporal workflow found for job {job_id}")
            except Exception as e:
                ctx.logger.error(f"Failed to cancel Temporal workflow for job {job_id}: {e}")
                # Continue even if Temporal cancellation fails - the DB status is already updated

        # Fetch the updated job from database
        await db.refresh(sync_job)

        # Convert to SourceConnectionJob response
        sync_job_schema = schemas.SyncJob.model_validate(sync_job, from_attributes=True)
        return sync_job_schema.to_source_connection_job(source_connection_id)

    async def complete_oauth_callback(
        self,
        db: AsyncSession,
        *,
        state: str,
        code: str,
    ) -> schemas.SourceConnection:
        """Complete OAuth flow from callback.

        This method reconstructs the ApiContext from the stored session data
        since OAuth callbacks come from external providers without platform auth.

        Returns:
            Source connection with authentication details
        """
        # Find init session without auth validation
        init_session = await connection_init_session.get_by_state_no_auth(db, state=state)
        if not init_session:
            raise HTTPException(status_code=404, detail="OAuth session not found or expired")

        if init_session.status != ConnectionInitStatus.PENDING:
            raise HTTPException(
                status_code=400, detail=f"OAuth session already {init_session.status}"
            )

        # Reconstruct ApiContext from session data
        ctx = await self._reconstruct_context_from_session(db, init_session)

        # Find shell source connection
        source_conn_shell = await crud.source_connection.get_by_query_and_org(
            db, ctx=ctx, connection_init_session_id=init_session.id
        )
        if not source_conn_shell:
            raise HTTPException(status_code=404, detail="Source connection shell not found")

        # Exchange code for token
        token_response = await self._exchange_oauth_code(
            db, init_session.short_name, code, init_session.overrides, ctx
        )

        # Validate token
        await self._validate_oauth_token(
            db,
            await crud.source.get_by_short_name(db, short_name=init_session.short_name),
            token_response.access_token,
            None,
            ctx,
        )

        # Complete the connection - also creates a sync if run_immediately is True
        source_conn = await self._complete_oauth_connection(
            db, source_conn_shell, init_session, token_response, ctx
        )

        # Build the proper response model with redirect URL
        source_conn_response = await self._build_source_connection_response(db, source_conn, ctx)

        # Trigger Temporal workflow if a sync was created with run_immediately
        # The OAuth callback always sets run_immediately=True
        if source_conn.sync_id:
            # Get the sync and check if a job was created
            sync = await crud.sync.get(db, id=source_conn.sync_id, ctx=ctx)
            if sync:
                # Get the latest sync job
                jobs = await crud.sync_job.get_all_by_sync_id(db, sync_id=sync.id)
                if jobs and len(jobs) > 0:
                    # Get the most recent job (first in list)
                    sync_job = jobs[0]
                    # Only trigger if the job is pending (not already running)
                    if sync_job.status == SyncJobStatus.PENDING:
                        # Get collection for the workflow
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

                            # Get sync_dag
                            sync_dag = await crud.sync_dag.get_by_sync_id(
                                db, sync_id=sync.id, ctx=ctx
                            )
                            if sync_dag:
                                sync_dag_schema = schemas.SyncDag.model_validate(
                                    sync_dag, from_attributes=True
                                )

                                # Trigger the workflow
                                await temporal_service.run_source_connection_workflow(
                                    sync=sync_schema,
                                    sync_job=sync_job_schema,
                                    sync_dag=sync_dag_schema,
                                    collection=collection_schema,
                                    source_connection=source_conn_response,
                                    ctx=ctx,
                                )

        return source_conn_response

    # Import helper methods from existing helpers
    from airweave.core.source_connection_service_helpers import (
        source_connection_helpers,
    )

    _validate_auth_fields = source_connection_helpers.validate_auth_fields
    _validate_config_fields = source_connection_helpers.validate_config_fields
    _validate_direct_auth = source_connection_helpers.validate_direct_auth
    _validate_oauth_token = source_connection_helpers.validate_oauth_token
    _create_integration_credential = source_connection_helpers.create_integration_credential
    _create_connection = source_connection_helpers.create_connection
    _get_collection = source_connection_helpers.get_collection
    _create_sync = source_connection_helpers.create_sync
    _create_sync_without_schedule = source_connection_helpers.create_sync_without_schedule
    _create_source_connection = source_connection_helpers.create_source_connection
    _build_source_connection_response = source_connection_helpers.build_source_connection_response
    _create_init_session = source_connection_helpers.create_init_session
    _create_proxy_url = source_connection_helpers.create_proxy_url
    _update_sync_schedule = source_connection_helpers.update_sync_schedule
    _update_auth_fields = source_connection_helpers.update_auth_fields
    _cleanup_destination_data = source_connection_helpers.cleanup_destination_data
    _cleanup_temporal_schedules = source_connection_helpers.cleanup_temporal_schedules
    _sync_job_to_source_connection_job = source_connection_helpers.sync_job_to_source_connection_job
    _reconstruct_context_from_session = source_connection_helpers.reconstruct_context_from_session
    _exchange_oauth_code = source_connection_helpers.exchange_oauth_code
    _complete_oauth_connection = source_connection_helpers.complete_oauth_connection


# Singleton instance
source_connection_service = SourceConnectionService()
