"""Clean source connection service with auth method inference."""

import asyncio
from datetime import datetime
from typing import TYPE_CHECKING, Any, Optional, Tuple
from uuid import UUID

if TYPE_CHECKING:
    from airweave.platform.auth.schemas import OAuth1Settings, OAuth2Settings

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from airweave import crud, schemas
from airweave.analytics import business_events
from airweave.api.context import ApiContext
from airweave.core.auth_provider_service import auth_provider_service
from airweave.core.config import settings as core_settings
from airweave.core.events.sync import SyncLifecycleEvent
from airweave.core.shared_models import SyncJobStatus
from airweave.core.source_connection_service_helpers import source_connection_helpers
from airweave.core.temporal_service import temporal_service
from airweave.crud import connection_init_session
from airweave.db.unit_of_work import UnitOfWork
from airweave.models.connection_init_session import ConnectionInitStatus
from airweave.platform.auth.oauth2_service import oauth2_service
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
    SourceConnectionUpdate,
)


class SourceConnectionService:
    """Service for managing source connections and their lifecycle."""

    def _get_default_daily_cron_schedule(self, ctx: ApiContext) -> str:
        """Generate a default daily cron schedule based on current UTC time.

        Returns:
            A cron expression for daily execution at the current UTC time.
        """
        from datetime import timezone

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

    def _get_default_continuous_cron_schedule(self, ctx: ApiContext) -> str:
        """Get default cron schedule for continuous sources.

        Returns:
            A cron expression for 5-minute intervals.
        """
        ctx.logger.info("Continuous source defaulting to 5-minute schedule")
        return "*/5 * * * *"

    def _determine_schedule_for_source(
        self, obj_in: Any, source: schemas.Source, ctx: ApiContext
    ) -> Optional[str]:
        """Determine the appropriate schedule based on source type and input.

        Args:
            obj_in: The source connection creation input
            source: The source model
            ctx: API context

        Returns:
            CRON schedule string or None if no schedule should be created
        """
        # Check if schedule has a cron value first
        if hasattr(obj_in, "schedule") and obj_in.schedule and hasattr(obj_in.schedule, "cron"):
            # If cron is explicitly None, no schedule
            if obj_in.schedule.cron is None:
                ctx.logger.info("Schedule cron explicitly set to null, no schedule will be created")
                return None
            return obj_in.schedule.cron

        # For auth provider connections, schedule is typically omitted and becomes None
        # We should still create default schedules for these
        # The only way to explicitly disable schedule is to pass schedule: {cron: null}

        # Determine defaults based on source type
        if getattr(source, "supports_continuous", False):
            return self._get_default_continuous_cron_schedule(ctx)
        else:
            # For regular sources, default to daily
            return self._get_default_daily_cron_schedule(ctx)

    def _validate_cron_schedule_for_source(
        self, cron_schedule: str, source: schemas.Source, ctx: ApiContext
    ) -> None:
        """Validate CRON schedule based on source capabilities.

        Args:
            cron_schedule: The CRON expression to validate
            source: The source model
            ctx: API context

        Raises:
            HTTPException: If the schedule is invalid for the source
        """
        import re

        if not cron_schedule:
            return

        # Parse the CRON expression to check if it's minute-level
        # We need to distinguish between:
        # - "*/N * * * *" where N < 60 - runs every N minutes (minute-level)
        # - "* * * * *" - runs every minute (minute-level)
        # - "0 * * * *" - runs at minute 0 of every hour (hourly, not minute-level)
        # - "30 2 * * *" - runs at 2:30 AM daily (daily, not minute-level)

        # Check for patterns that run more frequently than hourly
        # Pattern 1: */N where N < 60 (e.g., */5, */15, */30)
        interval_pattern = r"^\*/([1-5]?[0-9]) \* \* \* \*$"
        match = re.match(interval_pattern, cron_schedule)

        if match:
            interval = int(match.group(1))
            if interval < 60:
                # This is sub-hourly (minute-level)
                if not source.supports_continuous:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Source '{source.short_name}' does not support continuous syncs. "
                        f"Minimum schedule interval is 1 hour (e.g., '0 * * * *' for hourly).",
                    )
                # For continuous sources, sub-hourly is allowed
                ctx.logger.info(
                    f"Source '{source.short_name}' supports continuous syncs, "
                    f"allowing minute-level schedule: {cron_schedule}"
                )
                return

        # Pattern 2: * * * * * (every minute)
        if cron_schedule == "* * * * *":
            if not source.supports_continuous:
                raise HTTPException(
                    status_code=400,
                    detail=f"Source '{source.short_name}' does not support continuous syncs. "
                    f"Minimum schedule interval is 1 hour (e.g., '0 * * * *' for hourly).",
                )
            ctx.logger.info(
                f"Source '{source.short_name}' supports continuous syncs, "
                f"allowing every-minute schedule: {cron_schedule}"
            )

        # All other patterns (including "0 * * * *" for hourly) are allowed

    async def _validate_and_extract_template_configs(
        self,
        db: AsyncSession,
        source: schemas.Source,
        validated_config: Optional[dict],
        ctx: ApiContext,
    ) -> Optional[dict]:
        """Validate and extract template config fields for OAuth flows.

        Template configs are config fields that are required before OAuth can begin
        (e.g., instance URLs like Zendesk subdomain).

        Args:
            db: Database session
            source: Source model
            validated_config: Already validated config dictionary
            ctx: API context

        Returns:
            Dictionary of template configs or None if not applicable

        Raises:
            HTTPException: If required template configs are missing or invalid
        """
        template_configs = None
        if source.config_class and validated_config is not None:
            from airweave.platform.locator import resource_locator

            try:
                config_class = resource_locator.get_config(source.config_class)

                # Check if this source has template config fields
                template_config_fields = config_class.get_template_config_fields()

                if template_config_fields:
                    # Validate template config fields are present
                    # (even if validated_config is empty dict)
                    try:
                        config_class.validate_template_configs(validated_config)
                        template_configs = config_class.extract_template_configs(validated_config)

                        ctx.logger.info(
                            f"✅ Validated template configs for {source.short_name}: "
                            f"{list(template_configs.keys())}"
                        )
                    except ValueError as e:
                        raise HTTPException(status_code=422, detail=str(e))
            except HTTPException:
                # Re-raise HTTP exceptions (like validation errors)
                raise
            except Exception as e:
                # Log but don't fail if config class not found (backward compatibility)
                ctx.logger.warning(f"Could not load config class for {source.short_name}: {e}")

        return template_configs

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
            # Check if BYOC based on presence of custom credentials
            # OAuth2 BYOC: client_id + client_secret
            # OAuth1 BYOC: consumer_key + consumer_secret
            has_oauth2_byoc = auth.client_id and auth.client_secret
            has_oauth1_byoc = auth.consumer_key and auth.consumer_secret

            if has_oauth2_byoc or has_oauth1_byoc:
                return AuthenticationMethod.OAUTH_BYOC
            else:
                return AuthenticationMethod.OAUTH_BROWSER
        elif isinstance(auth, AuthProviderAuthentication):
            return AuthenticationMethod.AUTH_PROVIDER
        else:
            raise HTTPException(status_code=400, detail="Invalid authentication configuration")

    async def create(  # noqa: C901
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

        # Validate BYOC requirement: If source requires BYOC, auth method must be OAUTH_BYOC
        if source_class.requires_byoc and auth_method == AuthenticationMethod.OAUTH_BROWSER:
            raise HTTPException(
                status_code=400,
                detail=f"Source {obj_in.short_name} requires custom OAuth client credentials. "
                "Please provide client_id and client_secret in the authentication configuration.",
            )

        # Handle the edge case where authentication was None (defaults to OAuth browser)
        # and Pydantic couldn't determine the default
        if obj_in.sync_immediately is None:
            if auth_method in [AuthenticationMethod.OAUTH_BROWSER, AuthenticationMethod.OAUTH_BYOC]:
                obj_in.sync_immediately = False
            else:
                # Direct, OAuth token, and auth provider default to True
                obj_in.sync_immediately = True

        # Validate OAuth browser/BYOC cannot have sync_immediately=true
        if auth_method in [AuthenticationMethod.OAUTH_BROWSER, AuthenticationMethod.OAUTH_BYOC]:
            if obj_in.sync_immediately:
                raise HTTPException(
                    status_code=400,
                    detail="OAuth connections cannot use sync_immediately. "
                    "Sync will start after authentication.",
                )

        # Route based on auth method
        if auth_method == AuthenticationMethod.DIRECT:
            source_connection = await self._create_with_direct_auth(db, obj_in=obj_in, ctx=ctx)
        elif auth_method == AuthenticationMethod.OAUTH_BROWSER:
            # Determine OAuth1 vs OAuth2
            oauth_settings = await integration_settings.get_by_short_name(obj_in.short_name)
            from airweave.platform.auth.schemas import OAuth1Settings

            if isinstance(oauth_settings, OAuth1Settings):
                source_connection = await self._create_with_oauth1_browser(
                    db, obj_in=obj_in, oauth_settings=oauth_settings, ctx=ctx
                )
            else:
                source_connection = await self._create_with_oauth2_browser(
                    db, obj_in=obj_in, oauth_settings=oauth_settings, ctx=ctx
                )
        elif auth_method == AuthenticationMethod.OAUTH_TOKEN:
            source_connection = await self._create_with_oauth_token(db, obj_in=obj_in, ctx=ctx)
        elif auth_method == AuthenticationMethod.OAUTH_BYOC:
            # Determine OAuth1 vs OAuth2 BYOC
            oauth_settings = await integration_settings.get_by_short_name(obj_in.short_name)
            from airweave.platform.auth.schemas import OAuth1Settings

            if isinstance(oauth_settings, OAuth1Settings):
                source_connection = await self._create_with_oauth1_byoc(
                    db, obj_in=obj_in, oauth_settings=oauth_settings, ctx=ctx
                )
            else:
                source_connection = await self._create_with_oauth2_byoc(
                    db, obj_in=obj_in, oauth_settings=oauth_settings, ctx=ctx
                )
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

            connection_schema = schemas.Connection.model_validate(connection, from_attributes=True)

            # Handle sync creation with schedule
            sync_id, sync, sync_job = await self._handle_sync_creation(
                uow, obj_in, source, connection.id, collection.id, collection.readable_id, ctx
            )

            # Create source connection
            source_conn = await self._create_source_connection(
                uow.session,
                obj_in,
                connection.id,
                collection.readable_id,
                sync_id,
                validated_config,
                is_authenticated=True,
                ctx=ctx,
                uow=uow,
            )
            await uow.session.flush()

            # Create Temporal schedule if needed
            cron_schedule = self._determine_schedule_for_source(obj_in, source, ctx)
            await self._create_temporal_schedule_if_needed(uow, cron_schedule, sync_id, ctx)

            # Prepare schemas for workflow if needed
            (
                sync_schema,
                sync_job_schema,
                collection_schema,
            ) = await self._prepare_sync_schemas_for_workflow(
                uow, sync, sync_job, collection, obj_in
            )

            await uow.commit()
            await uow.session.refresh(source_conn)

        # Build response with the main db session after commit
        response = await self._build_source_connection_response(db, source_conn, ctx)

        # Trigger sync if requested
        if sync_job and obj_in.sync_immediately:
            await self._trigger_sync_workflow(
                db,
                connection_schema,
                sync_schema,
                sync_job_schema,
                collection_schema,
                ctx,
                source_connection_id=response.id,
            )

        return response

    async def _create_with_oauth1_browser(
        self,
        db: AsyncSession,
        obj_in: SourceConnectionCreate,
        oauth_settings: "OAuth1Settings",
        ctx: ApiContext,
        custom_consumer_key: Optional[str] = None,
        custom_consumer_secret: Optional[str] = None,
    ) -> SourceConnection:
        """Create shell connection and start OAuth1 browser flow.

        OAuth1 flow:
        1. Get request token from provider
        2. Store request token credentials
        3. Redirect user to authorization URL with request token
        4. After approval, exchange verifier for access token (handled in callback)

        Args:
            db: Database session
            obj_in: Source connection creation request
            oauth_settings: OAuth1 integration settings
            ctx: API context
            custom_consumer_key: Optional custom consumer key for BYOC
            custom_consumer_secret: Optional custom consumer secret for BYOC
        """
        source = await self._get_and_validate_source(db, obj_in.short_name)

        # Validate config
        validated_config = await self._validate_config_fields(
            db, obj_in.short_name, obj_in.config, ctx
        )

        import secrets

        state = secrets.token_urlsafe(24)

        api_callback = f"{core_settings.api_url}/source-connections/callback"

        # Use custom consumer credentials if provided (BYOC), otherwise platform defaults
        consumer_key = custom_consumer_key or oauth_settings.consumer_key
        consumer_secret = custom_consumer_secret or oauth_settings.consumer_secret

        # Step 1: Get request token from OAuth1 provider
        from airweave.platform.auth.oauth1_service import oauth1_service

        flow_type = "OAuth1 BYOC" if custom_consumer_key else "OAuth1"
        ctx.logger.info(f"Starting {flow_type} flow for {source.short_name}")

        request_token_response = await oauth1_service.get_request_token(
            request_token_url=oauth_settings.request_token_url,
            consumer_key=consumer_key,
            consumer_secret=consumer_secret,
            callback_url=api_callback,
            logger=ctx.logger,
        )

        # Step 2: Store request token credentials for later exchange
        oauth1_overrides = {
            "oauth_token": request_token_response.oauth_token,
            "oauth_token_secret": request_token_response.oauth_token_secret,
            "consumer_key": consumer_key,
            "consumer_secret": consumer_secret,
        }

        # Step 3: Build authorization URL with request token
        provider_auth_url = oauth1_service.build_authorization_url(
            authorization_url=oauth_settings.authorization_url,
            oauth_token=request_token_response.oauth_token,
            scope=oauth_settings.scope,
            expiration=oauth_settings.expiration,
        )

        ctx.logger.debug(f"OAuth1 request token obtained for {source.short_name}")

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

            # Create init session with OAuth1 credentials
            init_session = await self._create_init_session(
                uow.session,
                obj_in,
                state,
                ctx,
                uow,
                redirect_session_id=redirect_session_id,
                additional_overrides=oauth1_overrides,
            )

            # Link them
            source_conn.connection_init_session_id = init_session.id
            uow.session.add(source_conn)

            # Add auth URL to response
            source_conn.authentication_url = proxy_url
            source_conn.authentication_url_expiry = proxy_expiry

            await uow.commit()
            await uow.session.refresh(source_conn)

        # Build response with the main db session after commit
        response = await self._build_source_connection_response(db, source_conn, ctx)

        return response

    async def _create_with_oauth2_browser(
        self,
        db: AsyncSession,
        obj_in: SourceConnectionCreate,
        oauth_settings: "OAuth2Settings",
        ctx: ApiContext,
    ) -> SourceConnection:
        """Create shell connection and start OAuth2 browser flow.

        OAuth2 flow:
        1. Generate authorization URL (with optional PKCE)
        2. Redirect user to authorization URL
        3. After approval, exchange code for access token (handled in callback)
        """
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

        # Enforce BYOC if required by the source
        if source.requires_byoc:
            if not oauth_auth.client_id or not oauth_auth.client_secret:
                raise HTTPException(
                    status_code=400,
                    detail=f"Source '{source.name}' requires BYOC (Bring Your Own Credentials). "
                    f"You must provide both client_id and client_secret in the auth object.",
                )

        # Validate config
        validated_config = await self._validate_config_fields(
            db, obj_in.short_name, obj_in.config, ctx
        )

        # Validate and extract template config fields for OAuth flow
        template_configs = await self._validate_and_extract_template_configs(
            db, source, validated_config, ctx
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

        # Generate authorization URL with PKCE support if required
        provider_auth_url, code_verifier = await oauth2_service.generate_auth_url_with_redirect(
            oauth_settings,
            redirect_uri=api_callback,
            client_id=client_id,
            state=state,
            template_configs=template_configs,
        )

        # Store PKCE code verifier if present (will be used during token exchange)
        oauth2_overrides = {}
        if code_verifier:
            oauth2_overrides["code_verifier"] = code_verifier
            ctx.logger.debug(
                f"Generated PKCE challenge for {source.short_name} (code_verifier stored)"
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

            # Create init session with OAuth2 PKCE overrides
            init_session = await self._create_init_session(
                uow.session,
                obj_in,
                state,
                ctx,
                uow,
                redirect_session_id=redirect_session_id,
                template_configs=template_configs,
                additional_overrides=oauth2_overrides,
            )

            # Link them
            source_conn.connection_init_session_id = init_session.id
            uow.session.add(source_conn)

            # Add auth URL to response
            source_conn.authentication_url = proxy_url
            source_conn.authentication_url_expiry = proxy_expiry

            await uow.commit()
            await uow.session.refresh(source_conn)

        # Build response with the main db session after commit
        response = await self._build_source_connection_response(db, source_conn, ctx)

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
            connection_schema = schemas.Connection.model_validate(connection, from_attributes=True)

            # Handle sync creation with schedule
            sync_id, sync, sync_job = await self._handle_sync_creation(
                uow, obj_in, source, connection.id, collection.id, collection.readable_id, ctx
            )

            # Create source connection
            source_conn = await self._create_source_connection(
                uow.session,
                obj_in,
                connection.id,
                collection.readable_id,
                sync_id,
                validated_config,
                is_authenticated=True,
                ctx=ctx,
                uow=uow,
            )
            await uow.session.flush()

            # Create Temporal schedule if needed
            cron_schedule = self._determine_schedule_for_source(obj_in, source, ctx)
            await self._create_temporal_schedule_if_needed(uow, cron_schedule, sync_id, ctx)

            # Prepare schemas for workflow if needed
            (
                sync_schema,
                sync_job_schema,
                collection_schema,
            ) = await self._prepare_sync_schemas_for_workflow(
                uow, sync, sync_job, collection, obj_in
            )

            await uow.commit()
            await uow.session.refresh(source_conn)

        # Build response with the main db session after commit
        response = await self._build_source_connection_response(db, source_conn, ctx)

        # Trigger sync if requested
        if sync_job and obj_in.sync_immediately:
            await self._trigger_sync_workflow(
                db,
                connection_schema,
                sync_schema,
                sync_job_schema,
                collection_schema,
                ctx,
                source_connection_id=response.id,
            )

        return response

    async def _create_with_oauth1_byoc(
        self,
        db: AsyncSession,
        obj_in: SourceConnectionCreate,
        oauth_settings: "OAuth1Settings",
        ctx: ApiContext,
    ) -> SourceConnection:
        """Create connection with bring-your-own-client OAuth1.

        User provides their own consumer_key and consumer_secret instead of using
        the platform's credentials.
        """
        from airweave.schemas.source_connection import OAuthBrowserAuthentication

        # Verify consumer credentials are present
        if not obj_in.authentication or not isinstance(
            obj_in.authentication, OAuthBrowserAuthentication
        ):
            raise HTTPException(
                status_code=400,
                detail=(
                    "OAuth1 BYOC requires OAuth browser authentication with consumer credentials"
                ),
            )

        if not obj_in.authentication.consumer_key or not obj_in.authentication.consumer_secret:
            raise HTTPException(
                status_code=400, detail="OAuth1 BYOC requires consumer_key and consumer_secret"
            )

        # Delegate to OAuth1 browser flow with custom consumer credentials
        return await self._create_with_oauth1_browser(
            db,
            obj_in=obj_in,
            oauth_settings=oauth_settings,
            ctx=ctx,
            custom_consumer_key=obj_in.authentication.consumer_key,
            custom_consumer_secret=obj_in.authentication.consumer_secret,
        )

    async def _create_with_oauth2_byoc(
        self,
        db: AsyncSession,
        obj_in: SourceConnectionCreate,
        oauth_settings: "OAuth2Settings",
        ctx: ApiContext,
    ) -> SourceConnection:
        """Create connection with bring-your-own-client OAuth2.

        User provides their own client_id and client_secret instead of using
        the platform's credentials.
        """
        from airweave.schemas.source_connection import OAuthBrowserAuthentication

        # Verify client credentials are present
        if not obj_in.authentication or not isinstance(
            obj_in.authentication, OAuthBrowserAuthentication
        ):
            raise HTTPException(
                status_code=400,
                detail="OAuth2 BYOC requires OAuth browser authentication with client credentials",
            )

        if not obj_in.authentication.client_id or not obj_in.authentication.client_secret:
            raise HTTPException(
                status_code=400, detail="OAuth2 BYOC requires client_id and client_secret"
            )

        # Use the OAuth2 browser flow with custom client credentials
        # The oauth2_browser handler already supports custom client_id via oauth_auth parameter
        return await self._create_with_oauth2_browser(
            db, obj_in=obj_in, oauth_settings=oauth_settings, ctx=ctx
        )

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

        # Validate that the source supports this auth provider
        supported_providers = auth_provider_service.get_supported_providers_for_source(
            obj_in.short_name
        )
        if auth_provider_conn.short_name not in supported_providers:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Source '{obj_in.short_name}' does not support "
                    f"'{auth_provider_conn.short_name}' as an auth provider. "
                    f"Supported providers: {supported_providers}"
                ),
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

            # Handle sync creation with schedule
            sync_id, sync, sync_job = await self._handle_sync_creation(
                uow, obj_in, source, connection.id, collection.id, collection.readable_id, ctx
            )

            # Create source connection
            source_conn = await self._create_source_connection(
                uow.session,
                obj_in,
                connection.id,
                collection.readable_id,
                sync_id,
                validated_config,
                is_authenticated=True,
                ctx=ctx,
                uow=uow,
                auth_provider_id=auth_provider_conn.readable_id,
                auth_provider_config=validated_auth_config,
            )
            await uow.session.flush()

            # Create Temporal schedule if needed
            cron_schedule = self._determine_schedule_for_source(obj_in, source, ctx)
            await self._create_temporal_schedule_if_needed(uow, cron_schedule, sync_id, ctx)

            # Prepare schemas for workflow if needed
            (
                sync_schema,
                sync_job_schema,
                collection_schema,
            ) = await self._prepare_sync_schemas_for_workflow(
                uow, sync, sync_job, collection, obj_in
            )

            await uow.commit()
            await uow.session.refresh(source_conn)

        # Build response with the main db session after commit
        response = await self._build_source_connection_response(db, source_conn, ctx)

        # Trigger sync if requested
        if sync_job and obj_in.sync_immediately:
            # Get the Connection object for the workflow
            connection_schema = (
                await source_connection_helpers.get_connection_for_source_connection(
                    db=db, source_connection=source_conn, ctx=ctx
                )
            )
            await self._trigger_sync_workflow(
                db,
                connection_schema,
                sync_schema,
                sync_job_schema,
                collection_schema,
                ctx,
                source_connection_id=response.id,
            )

        return response

    # Helper methods

    async def _handle_sync_creation(
        self,
        uow,
        obj_in: SourceConnectionCreate,
        source: schemas.Source,
        connection_id: UUID,
        collection_id: UUID,
        collection_readable_id: str,
        ctx: ApiContext,
    ) -> Tuple[Optional[UUID], Optional[schemas.Sync], Optional[schemas.SyncJob]]:
        """Common logic for creating sync with schedule during source connection creation.

        Args:
            uow: Unit of work
            obj_in: Source connection creation input
            source: Source model
            connection_id: Connection ID (model.connection.id)
            collection_id: Collection ID
            collection_readable_id: Collection readable ID
            ctx: API context

        Returns:
            Tuple of (sync_id, sync_schema, sync_job_schema) where schemas may be None
        """
        # Check if this is a federated search source - these don't need syncs
        source_class = self._get_source_class(source.class_name)
        if getattr(source_class, "federated_search", False):
            ctx.logger.info(
                f"Skipping sync creation for federated search source '{source.short_name}'. "
                "Federated search sources are searched at query time."
            )
            return None, None, None

        # Determine schedule based on source type and input
        cron_schedule = self._determine_schedule_for_source(obj_in, source, ctx)

        # Only create sync if we have a schedule or need immediate run
        if not cron_schedule and not obj_in.sync_immediately:
            return None, None, None

        # Validate the schedule if provided
        if cron_schedule:
            self._validate_cron_schedule_for_source(cron_schedule, source, ctx)

        # Create sync WITHOUT Temporal schedule (we'll create it after source_connection is set)
        sync, sync_job = await self._create_sync_without_schedule(
            uow.session,
            obj_in.name,
            connection_id,
            collection_id,
            collection_readable_id,
            cron_schedule,
            obj_in.sync_immediately,
            ctx,
            uow,
        )
        await uow.session.flush()

        sync_id = sync.id if sync else None
        return sync_id, sync, sync_job

    async def _create_temporal_schedule_if_needed(
        self,
        uow,
        cron_schedule: Optional[str],
        sync_id: Optional[UUID],
        ctx: ApiContext,
    ) -> None:
        """Create Temporal schedule if we have both a cron schedule and sync_id.

        Args:
            uow: Unit of work
            cron_schedule: CRON expression
            sync_id: Sync ID
            ctx: API context
        """
        if cron_schedule and sync_id:
            from airweave.platform.temporal.schedule_service import temporal_schedule_service

            await temporal_schedule_service.create_or_update_schedule(
                sync_id=sync_id,
                cron_schedule=cron_schedule,
                db=uow.session,
                ctx=ctx,
                uow=uow,
            )

    async def _prepare_sync_schemas_for_workflow(
        self,
        uow,
        sync: Optional[schemas.Sync],
        sync_job: Optional[schemas.SyncJob],
        collection: schemas.Collection,
        obj_in: SourceConnectionCreate,
    ) -> Tuple[Optional[schemas.Sync], Optional[schemas.SyncJob], Optional[schemas.Collection]]:
        """Prepare sync schemas for Temporal workflow if immediate sync is requested.

        Args:
            uow: Unit of work
            sync: Sync schema
            sync_job: Sync job schema
            collection: Collection model
            obj_in: Source connection creation input

        Returns:
            Tuple of (sync_schema, sync_job_schema, collection_schema) or (None, None, None)
        """
        if sync_job and obj_in.sync_immediately:
            # Ensure all models are flushed and refreshed before converting
            await uow.session.flush()
            await uow.session.refresh(sync_job)
            await uow.session.refresh(collection)

            sync_schema = schemas.Sync.model_validate(sync, from_attributes=True)
            sync_job_schema = schemas.SyncJob.model_validate(sync_job, from_attributes=True)
            collection_schema = schemas.Collection.model_validate(collection, from_attributes=True)

            return sync_schema, sync_job_schema, collection_schema

        return None, None, None

    async def _trigger_sync_workflow(
        self,
        db: AsyncSession,
        connection: schemas.Connection,
        sync: schemas.Sync,
        sync_job: schemas.SyncJob,
        collection: schemas.Collection,
        ctx: ApiContext,
        source_connection_id: Optional[UUID] = None,
    ) -> None:
        """Trigger Temporal workflow for sync.

        Also publishes sync.pending so every sync path (sync_immediately,
        manual /run, scheduled) emits the full lifecycle.

        Note: All parameters except db and ctx should be Pydantic schemas, not SQLAlchemy models.
        """
        # Publish sync.pending event
        if source_connection_id:
            from airweave.core.container import container

            if container is not None:
                try:
                    await container.event_bus.publish(
                        SyncLifecycleEvent.pending(
                            organization_id=ctx.organization.id,
                            source_connection_id=source_connection_id,
                            sync_job_id=sync_job.id,
                            sync_id=sync.id,
                            collection_id=collection.id,
                            source_type=connection.short_name,
                            collection_name=collection.name,
                            collection_readable_id=collection.readable_id,
                        )
                    )
                except Exception as e:
                    ctx.logger.warning(f"Failed to publish sync.pending event: {e}")

        # Trigger workflow - all inputs are already schemas
        await temporal_service.run_source_connection_workflow(
            sync=sync,
            sync_job=sync_job,
            collection=collection,
            connection=connection,
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

        # Handle special cases where the module name contains underscores
        # that get lost when lowercasing the class name.
        if module_name.startswith("google") and len(module_name) > 6:
            module_name = "google_" + module_name[6:]
        elif module_name.startswith("outlook") and len(module_name) > 7:
            module_name = "outlook_" + module_name[7:]
        elif module_name.startswith("zoho") and len(module_name) > 4:
            module_name = "zoho_" + module_name[4:]
        elif module_name == "filestub":
            module_name = "file_stub"

        module = __import__(f"airweave.platform.sources.{module_name}", fromlist=[class_name])
        return getattr(module, class_name)

    async def cancel_job(
        self,
        db: AsyncSession,
        *,
        source_connection_id: UUID,
        job_id: UUID,
        ctx: ApiContext,
    ) -> schemas.SourceConnectionJob:
        """Cancel a running sync job for a source connection.

        Sends a cancellation request to the Temporal workflow and marks the
        job as CANCELLING locally. Final CANCELLED state is set by the
        workflow when it processes the cancellation.
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

        # Set transitional status to CANCELLING immediately
        from airweave.core.sync_job_service import sync_job_service

        await sync_job_service.update_status(
            sync_job_id=job_id,
            status=SyncJobStatus.CANCELLING,
            ctx=ctx,
        )

        # Fire-and-forget cancellation request to Temporal
        cancel_result = await temporal_service.cancel_sync_job_workflow(str(job_id), ctx)

        if not cancel_result["success"]:
            # Actual Temporal connectivity/availability error - revert status
            fallback_status = (
                SyncJobStatus.RUNNING
                if sync_job.status == SyncJobStatus.RUNNING
                else SyncJobStatus.PENDING
            )
            await sync_job_service.update_status(
                sync_job_id=job_id,
                status=fallback_status,
                ctx=ctx,
            )
            raise HTTPException(
                status_code=502, detail="Failed to request cancellation from Temporal"
            )

        # If workflow wasn't found, mark job as CANCELLED directly since there's nothing running
        if not cancel_result["workflow_found"]:
            ctx.logger.info(f"Workflow not found for job {job_id} - marking as CANCELLED directly")
            from airweave.core.datetime_utils import utc_now_naive

            await sync_job_service.update_status(
                sync_job_id=job_id,
                status=SyncJobStatus.CANCELLED,
                ctx=ctx,
                completed_at=utc_now_naive(),
                error="Workflow not found in Temporal - may have already completed",
            )

        # Fetch the updated job from database
        await db.refresh(sync_job)

        # Convert to SourceConnectionJob response
        sync_job_schema = schemas.SyncJob.model_validate(sync_job, from_attributes=True)
        return sync_job_schema.to_source_connection_job(source_connection_id)

    async def complete_oauth1_callback(
        self,
        db: AsyncSession,
        *,
        oauth_token: str,
        oauth_verifier: str,
    ) -> schemas.SourceConnection:
        """Complete OAuth1 flow from callback.

        OAuth1 doesn't send our state parameter back, so we look up the session
        by oauth_token (the request token we stored during authorization).

        Args:
            db: Database session
            oauth_token: OAuth1 request token (matches what we stored)
            oauth_verifier: OAuth1 verifier code from user authorization

        Returns:
            Completed source connection with authentication details
        """
        # Find init session by oauth_token (stored in overrides during authorization)
        init_session = await connection_init_session.get_by_oauth_token_no_auth(
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

        # Reconstruct ApiContext from session data
        ctx = await self._reconstruct_context_from_session(db, init_session)

        # Find shell source connection
        source_conn_shell = await crud.source_connection.get_by_query_and_org(
            db, ctx=ctx, connection_init_session_id=init_session.id
        )
        if not source_conn_shell:
            raise HTTPException(status_code=404, detail="Source connection shell not found")

        # Get OAuth1 settings
        from airweave.platform.auth.schemas import OAuth1Settings
        from airweave.platform.auth.settings import integration_settings

        oauth_settings = await integration_settings.get_by_short_name(init_session.short_name)

        if not isinstance(oauth_settings, OAuth1Settings):
            raise HTTPException(
                status_code=400,
                detail=f"Source {init_session.short_name} is not configured for OAuth1",
            )

        # Exchange verifier for access token
        token_response = await self._exchange_oauth1_code(
            init_session.short_name,
            oauth_verifier,
            init_session.overrides,
            oauth_settings,
            ctx,
        )

        # Complete OAuth1 connection
        source_conn = await self._complete_oauth1_connection(
            db, source_conn_shell, init_session, token_response, ctx
        )

        return await self._finalize_oauth_callback(db, source_conn, ctx)

    async def complete_oauth2_callback(
        self,
        db: AsyncSession,
        *,
        state: str,
        code: str,
    ) -> schemas.SourceConnection:
        """Complete OAuth2 flow from callback.

        Args:
            db: Database session
            state: OAuth2 state parameter for CSRF protection
            code: OAuth2 authorization code

        Returns:
            Completed source connection with authentication details
        """
        # Find init session by state
        init_session = await connection_init_session.get_by_state_no_auth(db, state=state)
        if not init_session:
            raise HTTPException(status_code=404, detail="OAuth2 session not found or expired")

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
        token_response = await self._exchange_oauth2_code(
            init_session.short_name, code, init_session.overrides, ctx
        )

        # Validate OAuth2 token
        await self._validate_oauth_token(
            db,
            await crud.source.get_by_short_name(db, short_name=init_session.short_name),
            token_response.access_token,
            None,
            ctx,
        )

        # Complete OAuth2 connection
        source_conn = await self._complete_oauth2_connection(
            db, source_conn_shell, init_session, token_response, ctx
        )

        return await self._finalize_oauth_callback(db, source_conn, ctx)

    async def _finalize_oauth_callback(
        self,
        db: AsyncSession,
        source_conn: Any,
        ctx: ApiContext,
    ) -> schemas.SourceConnection:
        """Common finalization logic for OAuth callbacks (OAuth1 and OAuth2).

        Builds response and triggers sync workflow if needed.

        Args:
            db: Database session
            source_conn: Completed source connection
            ctx: API context

        Returns:
            Source connection response schema
        """
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

                            # Get the Connection object (not SourceConnection)
                            connection_schema = await self._get_connection_for_source_connection(
                                db=db, source_connection=source_conn, ctx=ctx
                            )

                            # Trigger the workflow
                            await temporal_service.run_source_connection_workflow(
                                sync=sync_schema,
                                sync_job=sync_job_schema,
                                collection=collection_schema,
                                connection=connection_schema,
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
    _get_connection_for_source_connection = (
        source_connection_helpers.get_connection_for_source_connection
    )
    _create_sync_without_schedule = source_connection_helpers.create_sync_without_schedule
    _create_source_connection = source_connection_helpers.create_source_connection
    # [code blue] deprecate once source_connections domain is live
    _build_source_connection_response = source_connection_helpers.build_source_connection_response
    _create_init_session = source_connection_helpers.create_init_session
    _create_proxy_url = source_connection_helpers.create_proxy_url
    _reconstruct_context_from_session = source_connection_helpers.reconstruct_context_from_session
    _exchange_oauth1_code = source_connection_helpers.exchange_oauth1_code
    _exchange_oauth2_code = source_connection_helpers.exchange_oauth2_code
    _complete_oauth1_connection = source_connection_helpers.complete_oauth1_connection
    _complete_oauth2_connection = source_connection_helpers.complete_oauth2_connection


# Singleton instance
source_connection_service = SourceConnectionService()
