"""Helper methods for source connection service v2."""

from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple
from uuid import UUID

if TYPE_CHECKING:
    from airweave.platform.auth.oauth1_service import OAuth1TokenResponse
    from airweave.platform.auth.schemas import OAuth2TokenResponse

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from airweave import crud, schemas
from airweave.api.context import ApiContext
from airweave.core import credentials
from airweave.core.config import settings as core_settings
from airweave.core.constants.reserved_ids import (
    NATIVE_VESPA_UUID,
)
from airweave.core.shared_models import (
    AuthMethod,
    ConnectionStatus,
    FeatureFlag,
    SourceConnectionStatus,
    SyncJobStatus,
    SyncStatus,
)
from airweave.crud import connection_init_session, redirect_session
from airweave.db.unit_of_work import UnitOfWork
from airweave.models.connection_init_session import (
    ConnectionInitSession,
    ConnectionInitStatus,
)
from airweave.models.integration_credential import IntegrationType
from airweave.models.source_connection import SourceConnection
from airweave.platform.auth.oauth1_service import oauth1_service
from airweave.platform.auth.oauth2_service import oauth2_service
from airweave.platform.auth.schemas import OAuth1Settings
from airweave.platform.configs._base import ConfigValues
from airweave.platform.configs.auth import AuthConfig
from airweave.platform.locator import resource_locator
from airweave.schemas.source_connection import (
    AuthenticationMethod,
    SourceConnectionJob,
)


class SourceConnectionHelpers:
    """Helper methods for source connection service."""

    async def _get_destination_connection_ids(
        self, db: AsyncSession, ctx: ApiContext
    ) -> list[UUID]:
        """Get destination connection IDs based on feature flags.

        Writes to Vespa as the primary (and only) vector database destination.

        Args:
            db: Database session
            ctx: API context with organization and feature flags

        Returns:
            List of destination connection IDs (Vespa + S3 if enabled)
        """
        from sqlalchemy import and_, select

        from airweave.models.connection import Connection

        # Vespa is the sole vector database destination (Qdrant deprecated)
        destination_ids = [NATIVE_VESPA_UUID]

        # Add S3 if feature flag enabled
        if ctx.has_feature(FeatureFlag.S3_DESTINATION):
            # Find S3 connection for this organization
            stmt = select(Connection).where(
                and_(
                    Connection.organization_id == ctx.organization.id,
                    Connection.short_name == "s3",
                    Connection.integration_type == "DESTINATION",
                )
            )
            result = await db.execute(stmt)
            s3_connection = result.scalar_one_or_none()

            if s3_connection:
                destination_ids.append(s3_connection.id)
                ctx.logger.info("S3 destination enabled for sync (feature flag active)")
            else:
                ctx.logger.warning(
                    "S3_DESTINATION feature enabled but no S3 connection configured. "
                    "Configure S3 in organization settings."
                )

        return destination_ids

    async def _validate_destination_consistency(
        self,
        db: AsyncSession,
        collection_readable_id: str,
        new_destination_ids: List[UUID],
        ctx: ApiContext,
    ) -> None:
        """Validate that new source uses same destination as existing sources.

        Ensures all sources in a collection write to the same vector database.

        Args:
            db: Database session
            collection_readable_id: Collection readable ID
            new_destination_ids: Destination IDs for the new source connection
            ctx: API context

        Raises:
            HTTPException: If destinations don't match existing sources
        """
        from airweave.models.sync_connection import SyncConnection

        # Get existing source connections for this collection
        existing_sources = await crud.source_connection.get_for_collection(
            db, readable_collection_id=collection_readable_id, ctx=ctx
        )

        if not existing_sources:
            return  # No existing sources, any destination is valid

        # Get destination from first existing source with a sync
        for source in existing_sources:
            if not source.sync_id:
                continue

            # Get the sync's destination connections via SyncConnection
            result = await db.execute(
                select(SyncConnection.connection_id).where(SyncConnection.sync_id == source.sync_id)
            )
            existing_dest_ids = [row[0] for row in result.fetchall()]

            if not existing_dest_ids:
                continue

            # Check Vespa consistency
            existing_uses_vespa = NATIVE_VESPA_UUID in existing_dest_ids
            new_uses_vespa = NATIVE_VESPA_UUID in new_destination_ids

            if existing_uses_vespa and not new_uses_vespa:
                raise HTTPException(
                    status_code=400,
                    detail=f"Collection '{collection_readable_id}' uses Vespa destination. "
                    "Cannot add source with a different destination.",
                )

            # Found a valid comparison, done
            break

    async def reconstruct_context_from_session(
        self, db: AsyncSession, init_session: ConnectionInitSession
    ) -> ApiContext:
        """Reconstruct ApiContext from stored session data.

        Used for OAuth callbacks where the user is not authenticated with the platform.

        Args:
            db: Database session
            init_session: The ConnectionInitSession containing org and user info

        Returns:
            Reconstructed ApiContext for the session's organization
        """
        import uuid

        from airweave.core.logging import logger

        # Get the organization from the session
        organization = await crud.organization.get(
            db, id=init_session.organization_id, skip_access_validation=True
        )
        organization_schema = schemas.Organization.model_validate(
            organization, from_attributes=True
        )

        # Generate a request ID for tracking
        request_id = str(uuid.uuid4())

        # Create logger with context
        base_logger = logger.with_context(
            request_id=request_id,
            organization_id=str(organization_schema.id),
            organization_name=organization_schema.name,
            auth_method=AuthMethod.OAUTH_CALLBACK.value,  # Special auth method for OAuth callbacks
            context_base="oauth",
        )

        return ApiContext(
            request_id=request_id,
            organization=organization_schema,
            user=None,  # No user context for OAuth callbacks
            auth_method=AuthMethod.OAUTH_CALLBACK,
            auth_metadata={"session_id": str(init_session.id)},
            logger=base_logger,
        )

    @staticmethod
    def _as_mapping(value: Any) -> Dict[str, Any]:
        """Coerce various shapes (ConfigValues, Pydantic models, plain dicts, etc.) into a dict."""
        from collections.abc import Mapping

        if value is None:
            return {}

        # Already a mapping
        if isinstance(value, Mapping):
            return dict(value)

        # Pydantic v2 / v1 models
        if hasattr(value, "model_dump"):
            return value.model_dump()
        if hasattr(value, "dict"):
            return value.dict()

        # Common FE wrapper like ConfigValues(values=...)
        if hasattr(value, "values"):
            v = value.values
            if isinstance(v, Mapping):
                return dict(v)
            return v  # hope it's already a plain mapping-like

        # Optional: list-of-pairs [{key, value}, ...]
        if isinstance(value, list) and all(
            isinstance(x, dict) and "key" in x and "value" in x for x in value
        ):
            return {x["key"]: x["value"] for x in value}

        raise TypeError(f"config_fields must be mapping-like; got {type(value).__name__}")

    # [code blue] replace with source_registry.get(short_name).auth_config_ref
    async def validate_auth_fields(
        self, db: AsyncSession, short_name: str, auth_fields: dict, ctx: ApiContext
    ) -> AuthConfig:
        """Validate authentication fields against source schema."""
        source = await crud.source.get_by_short_name(db, short_name=short_name)
        if not source:
            raise HTTPException(status_code=404, detail=f"Source '{short_name}' not found")

        if not source.auth_config_class:
            raise HTTPException(
                status_code=422,
                detail=f"Source {source.name} does not support direct auth",
            )

        try:
            auth_config_class = resource_locator.get_auth_config(source.auth_config_class)
            auth_config = auth_config_class(**auth_fields)
            return auth_config
        except Exception as e:
            from pydantic import ValidationError

            if isinstance(e, ValidationError):
                errors = "; ".join([f"{err['loc'][0]}: {err['msg']}" for err in e.errors()])
                raise HTTPException(status_code=422, detail=f"Invalid auth fields: {errors}") from e
            raise HTTPException(status_code=422, detail=str(e)) from e

    async def validate_config_fields(  # noqa: C901
        self,
        db: AsyncSession,
        short_name: str,
        config_fields: Any,
        ctx: ApiContext,
    ) -> Dict[str, Any]:
        """Validate configuration fields against source schema, returning a plain dict.

        Also strips fields that have feature flags not enabled for the organization.
        """
        source = await crud.source.get_by_short_name(db, short_name=short_name)
        if not source:
            raise HTTPException(status_code=404, detail=f"Source '{short_name}' not found")

        # Nothing provided
        if not config_fields:
            return {}

        # If the source doesn't declare a config class, still normalize to a dict for consistency
        if not source.config_class:
            try:
                return self._as_mapping(config_fields)
            except Exception:
                return {}

        # Source declares a config class -> unwrap then validate with Pydantic
        try:
            payload = self._as_mapping(config_fields)
            config_class = resource_locator.get_config(source.config_class)

            # Check for feature-flag protected fields that the organization doesn't have access to
            # This prevents users from bypassing UI restrictions via API/SDK
            enabled_features = ctx.organization.enabled_features or []

            for field_name, field_info in config_class.model_fields.items():
                json_schema_extra = field_info.json_schema_extra or {}
                feature_flag = json_schema_extra.get("feature_flag")

                if feature_flag and feature_flag not in enabled_features:
                    # Feature flag required but not enabled - reject if user tried to use this field
                    if field_name in payload and payload[field_name] is not None:
                        ctx.logger.warning(
                            f"Rejected config field '{field_name}' for {short_name}: "
                            f"feature flag '{feature_flag}' not enabled for organization"
                        )
                        field_title = field_info.title or field_name
                        raise HTTPException(
                            status_code=403,
                            detail=(
                                f"The '{field_title}' feature requires the '{feature_flag}' "
                                f"feature to be enabled for your organization. "
                                f"Please contact support to enable this feature."
                            ),
                        )

            # Pydantic v2 first, fall back to v1 constructor
            if hasattr(config_class, "model_validate"):
                model = config_class.model_validate(payload)
            else:
                model = config_class(**payload)

            # Always return a plain dict
            if hasattr(model, "model_dump"):
                return model.model_dump()
            if hasattr(model, "dict"):
                return model.dict()
            # As a last resort
            return dict(model) if isinstance(model, dict) else payload

        except Exception as e:
            from pydantic import ValidationError

            if isinstance(e, ValidationError):
                # Make FastAPI-friendly error details
                def _loc(err):
                    loc = err.get("loc", [])
                    return ".".join(str(x) for x in loc) if loc else "<root>"

                errors = "; ".join([f"{_loc(err)}: {err.get('msg')}" for err in e.errors()])
                raise HTTPException(
                    status_code=422, detail=f"Invalid config fields: {errors}"
                ) from e
            raise HTTPException(status_code=422, detail=str(e)) from e

    # [code blue] replace with SourceLifecycleService.validate()
    async def validate_direct_auth(
        self,
        db: AsyncSession,
        source: schemas.Source,
        auth_fields: AuthConfig,
        config_fields: Optional[ConfigValues],
        ctx: ApiContext,
    ) -> Dict[str, Any]:
        """Validate direct authentication credentials."""
        try:
            source_cls = resource_locator.get_source(source)
            source_instance = await source_cls.create(auth_fields, config=config_fields)
            source_instance.set_logger(ctx.logger)

            if hasattr(source_instance, "validate"):
                is_valid = await source_instance.validate()
                if not is_valid:
                    raise HTTPException(
                        status_code=400, detail="Authentication credentials are invalid"
                    )
            else:
                raise HTTPException(
                    status_code=400,
                    detail=f"No validate method found for {source.short_name}",
                )
            return {"valid": True, "source": source.short_name}
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Validation failed: {str(e)}") from e

    # [code blue] replace with SourceLifecycleService.validate()
    async def validate_oauth_token(
        self,
        db: AsyncSession,
        source: schemas.Source,
        access_token: str,
        config_fields: Optional[ConfigValues],
        ctx: ApiContext,
        credentials: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Validate OAuth access token.

        Args:
            db: Database session
            source: Source model
            access_token: OAuth access token (for backward compatibility)
            config_fields: Optional config fields
            ctx: API context
            credentials: Full OAuth credentials dict (includes access_token, instance_url, etc.)
        """
        try:
            source_cls = resource_locator.get_source(source)

            source_instance = await source_cls.create(
                access_token=access_token, config=config_fields
            )

            source_instance.set_logger(ctx.logger)

            if hasattr(source_instance, "validate"):
                is_valid = await source_instance.validate()
                if not is_valid:
                    raise HTTPException(status_code=400, detail="OAuth token is invalid")
            return {"valid": True, "source": source.short_name}
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Token validation failed: {str(e)}") from e

    async def create_integration_credential(
        self,
        db: AsyncSession,
        source: schemas.Source,
        auth_fields: Dict[str, Any],
        ctx: ApiContext,
        uow: Any,
        auth_method: AuthenticationMethod = AuthenticationMethod.DIRECT,
    ) -> Any:
        """Create integration credential.

        Args:
            db: Database session
            source: Source model object
            auth_fields: Authentication fields to encrypt
            ctx: API context
            uow: Unit of work
            auth_method: Authentication method being used
        """
        # Convert Pydantic model to dict if necessary
        if hasattr(auth_fields, "model_dump"):
            auth_fields_dict = auth_fields.model_dump()
        else:
            auth_fields_dict = auth_fields

        encrypted = credentials.encrypt(auth_fields_dict)

        # Get OAuth type from source if it's an OAuth method
        oauth_type = None
        if auth_method in [
            AuthenticationMethod.OAUTH_BROWSER,
            AuthenticationMethod.OAUTH_TOKEN,
            AuthenticationMethod.OAUTH_BYOC,
        ]:
            oauth_type = getattr(source, "oauth_type", None)

        cred_in = schemas.IntegrationCredentialCreateEncrypted(
            name=f"{source.name} - {ctx.organization.id}",
            description=f"Credentials for {source.name}",
            integration_short_name=source.short_name,
            integration_type=IntegrationType.SOURCE,
            authentication_method=auth_method,
            oauth_type=oauth_type,
            encrypted_credentials=encrypted,
            auth_config_class=source.auth_config_class,
        )
        return await crud.integration_credential.create(db, obj_in=cred_in, ctx=ctx, uow=uow)

    async def create_connection(
        self,
        db: AsyncSession,
        name: str,
        source: schemas.Source,
        credential_id: Optional[UUID],
        ctx: ApiContext,
        uow: Any,
    ) -> Any:
        """Create connection."""
        conn_in = schemas.ConnectionCreate(
            name=name,
            integration_type=IntegrationType.SOURCE,
            integration_credential_id=credential_id,
            status=ConnectionStatus.ACTIVE,
            short_name=source.short_name,
        )
        return await crud.connection.create(db, obj_in=conn_in, ctx=ctx, uow=uow)

    async def get_collection(
        self, db: AsyncSession, collection_id: str, ctx: ApiContext
    ) -> schemas.Collection:
        """Get or validate collection exists."""
        if not collection_id:
            # This should never happen with proper typing, but kept for safety
            raise HTTPException(status_code=400, detail="Collection is required")

        collection = await crud.collection.get_by_readable_id(
            db, readable_id=collection_id, ctx=ctx
        )
        if not collection:
            raise HTTPException(status_code=404, detail=f"Collection '{collection_id}' not found")
        return collection

    async def create_sync_without_schedule(
        self,
        db: AsyncSession,
        name: str,
        connection_id: UUID,
        collection_id: UUID,
        collection_readable_id: str,
        cron_schedule: Optional[str],
        run_immediately: bool,
        ctx: ApiContext,
        uow: Any,
    ) -> Tuple[schemas.Sync, Optional[schemas.SyncJob]]:
        """Create sync without creating Temporal schedule (for deferred schedule creation).

        Connection ID here is the model.connection.id, not the model.source_connection.id
        Collection ID is not used directly by sync, but kept for consistency
        """
        from airweave.core.sync_service import sync_service

        # Get destination connection IDs based on feature flags
        destination_ids = await self._get_destination_connection_ids(db, ctx)

        # Validate destination consistency with existing sources in collection
        await self._validate_destination_consistency(
            db, collection_readable_id, destination_ids, ctx
        )

        sync_in = schemas.SyncCreate(
            name=f"Sync for {name}",
            description=f"Auto-generated sync for {name}",
            source_connection_id=connection_id,
            destination_connection_ids=destination_ids,
            cron_schedule=cron_schedule,
            status=SyncStatus.ACTIVE,
            run_immediately=run_immediately,
        )
        # Call the internal method with skip_temporal_schedule=True
        return await sync_service._create_and_run_with_uow(
            db, sync_in=sync_in, ctx=ctx, uow=uow, skip_temporal_schedule=True
        )

    async def create_source_connection(
        self,
        db: AsyncSession,
        obj_in: Any,  # Can be legacy SourceConnectionCreate or discriminated union
        connection_id: Optional[UUID],
        collection_id: str,
        sync_id: Optional[UUID],
        config_fields: Optional[Dict[str, Any]],
        is_authenticated: bool,
        ctx: ApiContext,
        uow: Any,
        auth_provider_id: Optional[str] = None,
        auth_provider_config: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """Create source connection record."""
        # Get source type - handle both field names
        source_type = getattr(obj_in, "source_type", None) or getattr(obj_in, "short_name", None)

        sc_data = {
            "name": obj_in.name,
            "description": obj_in.description,
            "short_name": source_type,
            "config_fields": config_fields,
            "connection_id": connection_id,
            "readable_collection_id": collection_id,
            "sync_id": sync_id,
            "is_authenticated": is_authenticated,
        }

        if auth_provider_id:
            sc_data["readable_auth_provider_id"] = auth_provider_id
            sc_data["auth_provider_config"] = auth_provider_config

        return await crud.source_connection.create(db, obj_in=sc_data, ctx=ctx, uow=uow)

    def determine_auth_method(self, source_conn: Any) -> AuthenticationMethod:
        """Determine authentication method from existing database fields.

        This is a wrapper around the shared function for backward compatibility.
        """
        from airweave.schemas.source_connection import determine_auth_method

        return determine_auth_method(source_conn)

    def compute_status(
        self, source_conn: Any, last_job_status: Optional[SyncJobStatus] = None
    ) -> SourceConnectionStatus:
        """Compute status from current state.

        This is a wrapper around the shared function for backward compatibility.
        """
        from airweave.schemas.source_connection import compute_status

        return compute_status(source_conn, last_job_status)

    # [code blue] deprecate once source_connections domain is live — replaced by
    # domains.source_connections.response.ResponseBuilder.build_response
    async def build_source_connection_response(  # noqa: C901
        self,
        db: AsyncSession,
        source_conn: SourceConnection,
        ctx: ApiContext,
    ) -> schemas.SourceConnection:
        """Build complete source connection response object.

        Args:
            db: Database session
            source_conn: Source connection object
            ctx: API context
        """
        from airweave.schemas.source_connection import compute_status, determine_auth_method

        # Build authentication details
        actual_auth_method = None

        # First check if this is an auth provider connection
        if (
            hasattr(source_conn, "readable_auth_provider_id")
            and source_conn.readable_auth_provider_id
        ):
            actual_auth_method = schemas.AuthenticationMethod.AUTH_PROVIDER
        # Otherwise, load the connection and its credential to get the actual auth method
        elif source_conn.connection_id:
            from airweave.crud import connection as crud_connection
            from airweave.crud import integration_credential as crud_credential

            # Load the connection
            connection = await crud_connection.get(db, id=source_conn.connection_id, ctx=ctx)
            if connection and connection.integration_credential_id:
                # Load the credential
                credential = await crud_credential.get(
                    db, id=connection.integration_credential_id, ctx=ctx
                )
                if credential and hasattr(credential, "authentication_method"):
                    # Map the stored authentication method string to the API enum
                    auth_method_str = credential.authentication_method
                    if auth_method_str == "oauth_token":
                        actual_auth_method = schemas.AuthenticationMethod.OAUTH_TOKEN
                    elif auth_method_str == "oauth_browser":
                        actual_auth_method = schemas.AuthenticationMethod.OAUTH_BROWSER
                    elif auth_method_str == "oauth_byoc":
                        actual_auth_method = schemas.AuthenticationMethod.OAUTH_BYOC
                    elif auth_method_str == "direct":
                        actual_auth_method = schemas.AuthenticationMethod.DIRECT
                    elif auth_method_str == "auth_provider":
                        actual_auth_method = schemas.AuthenticationMethod.AUTH_PROVIDER

        # Fall back to the deprecated method if we couldn't determine from credential
        if actual_auth_method is None:
            actual_auth_method = determine_auth_method(source_conn)

        auth_info = {
            "method": actual_auth_method,
            "authenticated": source_conn.is_authenticated,
        }

        # Add authenticated timestamp
        if source_conn.is_authenticated:
            auth_info["authenticated_at"] = source_conn.created_at

        # Add auth provider info
        if (
            hasattr(source_conn, "readable_auth_provider_id")
            and source_conn.readable_auth_provider_id
        ):
            auth_info["provider_id"] = source_conn.readable_auth_provider_id
            auth_info["provider_readable_id"] = source_conn.readable_auth_provider_id

        # Add OAuth pending info
        if (
            hasattr(source_conn, "connection_init_session_id")
            and source_conn.connection_init_session_id
        ):
            # Load the connection init session to get the redirect URL and auth URL
            from sqlalchemy import select
            from sqlalchemy.orm import selectinload

            from airweave.models import ConnectionInitSession

            # Explicitly load with the redirect_session relationship
            stmt = (
                select(ConnectionInitSession)
                .where(ConnectionInitSession.id == source_conn.connection_init_session_id)
                .where(ConnectionInitSession.organization_id == ctx.organization.id)
                .options(selectinload(ConnectionInitSession.redirect_session))
            )
            result = await db.execute(stmt)
            init_session = result.scalar_one_or_none()
            if init_session:
                # Get redirect URL from overrides
                if init_session.overrides:
                    redirect_url = init_session.overrides.get("redirect_url")
                    if redirect_url:
                        auth_info["redirect_url"] = redirect_url

                # Get auth URL from linked redirect session
                if init_session.redirect_session and not source_conn.is_authenticated:
                    # Construct the auth URL from the redirect session
                    auth_info["auth_url"] = (
                        f"{core_settings.api_url}/source-connections/authorize/"
                        f"{init_session.redirect_session.code}"
                    )
                    auth_info["auth_url_expires"] = init_session.redirect_session.expires_at

        # Check for auth URL (set during OAuth flow creation as temporary attribute)
        elif hasattr(source_conn, "authentication_url") and source_conn.authentication_url:
            auth_info["auth_url"] = source_conn.authentication_url
            if hasattr(source_conn, "authentication_url_expiry"):
                auth_info["auth_url_expires"] = source_conn.authentication_url_expiry

        auth = schemas.AuthenticationDetails(**auth_info)

        # Fetch schedule info if sync exists
        schedule = None
        if hasattr(source_conn, "sync_id") and source_conn.sync_id:
            try:
                schedule_info = await crud.source_connection.get_schedule_info(db, source_conn)
                if schedule_info:
                    schedule = schemas.ScheduleDetails(
                        cron=schedule_info.get("cron_expression"),
                        next_run=schedule_info.get("next_run_at"),
                        continuous=schedule_info.get("is_continuous", False),
                        cursor_field=schedule_info.get("cursor_field"),
                        cursor_value=schedule_info.get("cursor_value"),
                    )
            except Exception as e:
                ctx.logger.warning(f"Failed to get schedule info: {e}")

        # Fetch sync details if sync exists
        sync_details = None
        if hasattr(source_conn, "sync_id") and source_conn.sync_id:
            try:
                from airweave.core.sync_service import sync_service as _sync_service

                job = await _sync_service.get_last_sync_job(
                    db, ctx=ctx, sync_id=source_conn.sync_id
                )
                if job:
                    # Build SyncJobDetails
                    duration_seconds = None
                    if job.completed_at and job.started_at:
                        duration_seconds = (job.completed_at - job.started_at).total_seconds()

                    # Calculate entity metrics
                    entities_inserted = getattr(job, "entities_inserted", 0) or 0
                    entities_updated = getattr(job, "entities_updated", 0) or 0
                    entities_deleted = getattr(job, "entities_deleted", 0) or 0
                    entities_skipped = getattr(job, "entities_skipped", 0) or 0

                    entities_failed = entities_skipped

                    last_job = schemas.SyncJobDetails(
                        id=job.id,
                        status=job.status,
                        started_at=getattr(job, "started_at", None),
                        completed_at=getattr(job, "completed_at", None),
                        duration_seconds=duration_seconds,
                        entities_inserted=entities_inserted,
                        entities_updated=entities_updated,
                        entities_deleted=entities_deleted,
                        entities_failed=entities_failed,
                        error=getattr(job, "error", None),
                    )

                    # Create SyncDetails
                    sync_details = schemas.SyncDetails(
                        total_runs=1,  # Simplified - we only have last job
                        successful_runs=1 if job.status == SyncJobStatus.COMPLETED else 0,
                        failed_runs=1 if job.status == SyncJobStatus.FAILED else 0,
                        last_job=last_job,
                    )

            except Exception as e:
                ctx.logger.warning(f"Failed to get sync details: {e}")

        # Fetch entity summary if sync exists
        entities = None
        if hasattr(source_conn, "sync_id") and source_conn.sync_id:
            try:
                entity_counts = await crud.entity_count.get_counts_per_sync_and_type(
                    db, source_conn.sync_id
                )

                if entity_counts:
                    total_entities = sum(count_data.count for count_data in entity_counts)
                    by_type = {}
                    for count_data in entity_counts:
                        by_type[count_data.entity_definition_name] = schemas.EntityTypeStats(
                            count=count_data.count,
                            last_updated=count_data.modified_at,
                        )

                    entities = schemas.EntitySummary(
                        total_entities=total_entities,
                        by_type=by_type,
                    )
            except Exception as e:
                ctx.logger.warning(f"Failed to get entity summary: {e}")

        # Compute status based on last job
        last_job_status = None
        if sync_details and sync_details.last_job:
            last_job_status = sync_details.last_job.status

        # Get federated_search from source model
        federated_search = False
        try:
            source_model = await crud.source.get_by_short_name(db, source_conn.short_name)
            if source_model:
                federated_search = getattr(source_model, "federated_search", False)
        except Exception as e:
            ctx.logger.warning(f"Failed to get federated_search for {source_conn.short_name}: {e}")

        # Build and return the complete response
        return schemas.SourceConnection(
            id=source_conn.id,
            organization_id=source_conn.organization_id,
            name=source_conn.name,
            description=source_conn.description,
            short_name=source_conn.short_name,
            readable_collection_id=source_conn.readable_collection_id,
            status=compute_status(source_conn, last_job_status),
            created_at=source_conn.created_at,
            modified_at=source_conn.modified_at,
            auth=auth,
            config=source_conn.config_fields if hasattr(source_conn, "config_fields") else None,
            schedule=schedule,
            sync=sync_details,
            sync_id=getattr(source_conn, "sync_id", None),
            entities=entities,
            federated_search=federated_search,
        )

    async def update_sync_schedule(
        self,
        db: AsyncSession,
        sync_id: UUID,
        cron_schedule: Optional[str],
        ctx: ApiContext,
        uow: UnitOfWork,
    ) -> None:
        """Update sync schedule in database and Temporal."""
        sync = await crud.sync.get(db, id=sync_id, ctx=ctx)
        if sync:
            # Update in database
            sync_update = schemas.SyncUpdate(cron_schedule=cron_schedule)
            await crud.sync.update(db, db_obj=sync, obj_in=sync_update, ctx=ctx, uow=uow)

            # Update in Temporal
            from airweave.platform.temporal.schedule_service import temporal_schedule_service

            if cron_schedule is None:
                # If cron_schedule is None, delete the Temporal schedule
                await temporal_schedule_service.delete_all_schedules_for_sync(
                    sync_id=sync_id, db=db, ctx=ctx
                )
            else:
                # Otherwise create or update the schedule
                await temporal_schedule_service.create_or_update_schedule(
                    sync_id=sync_id,
                    cron_schedule=cron_schedule,
                    db=db,
                    ctx=ctx,
                    uow=uow,
                )

    async def update_auth_fields(
        self,
        db: AsyncSession,
        source_conn: Any,
        auth_fields: Any,
        ctx: ApiContext,
        uow: Any,
    ) -> None:
        """Update authentication fields."""
        validated_auth = await self.validate_auth_fields(
            db, source_conn.short_name, auth_fields, ctx
        )
        if hasattr(validated_auth, "model_dump"):
            serializable_auth = validated_auth.model_dump()
        elif hasattr(validated_auth, "dict"):
            serializable_auth = validated_auth.dict()
        else:
            serializable_auth = validated_auth

        connection = await crud.connection.get(db, id=source_conn.connection_id, ctx=ctx)
        if connection and connection.integration_credential_id:
            credential = await crud.integration_credential.get(
                db, id=connection.integration_credential_id, ctx=ctx
            )
            if credential:
                credential_update = schemas.IntegrationCredentialUpdate(
                    encrypted_credentials=credentials.encrypt(serializable_auth)
                )
                await crud.integration_credential.update(
                    db, db_obj=credential, obj_in=credential_update, ctx=ctx, uow=uow
                )

    # [code blue] deprecate once source_connections domain is live — replaced by
    # domains.source_connections.response.ResponseBuilder.map_sync_job
    def sync_job_to_source_connection_job(
        self, job: Any, source_connection_id: UUID
    ) -> SourceConnectionJob:
        """Convert sync job to source connection job."""
        return SourceConnectionJob(
            id=job.id,
            source_connection_id=source_connection_id,
            status=job.status,
            started_at=job.started_at,
            completed_at=job.completed_at,
            duration_seconds=(
                (job.completed_at - job.started_at).total_seconds()
                if job.completed_at and job.started_at
                else None
            ),
            entities_inserted=getattr(job, "entities_inserted", 0),
            entities_updated=getattr(job, "entities_updated", 0),
            entities_deleted=getattr(job, "entities_deleted", 0),
            entities_failed=getattr(job, "entities_failed", 0),
            error=job.error if hasattr(job, "error") else None,
        )

    async def create_init_session(  # noqa: C901
        self,
        db: AsyncSession,
        obj_in: Any,  # Can be OAuthBrowserCreate or legacy SourceConnectionCreate
        state: str,
        ctx: ApiContext,
        uow: Any,
        redirect_session_id: Optional[UUID] = None,
        template_configs: Optional[dict] = None,
        additional_overrides: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """Create connection init session for OAuth flow.

        Flow resolution for OAuth client credentials (explicit order):
          1) BYOC nested in authentication (OAuthBrowserAuthentication)
          2) Legacy custom_client (object with client_id/client_secret)
          3) Top-level client_id/client_secret on the request
          4) Platform default (no client overrides)

        For BYOC, both client_id and client_secret are REQUIRED; otherwise 422.

        Args:
            db: Database session
            obj_in: Input schema
            state: OAuth state token
            ctx: API context
            uow: Unit of work
            redirect_session_id: Optional redirect session ID
            template_configs: Optional pre-validated template configs (e.g., instance_url)
            additional_overrides: Additional data to store in overrides (e.g., PKCE code_verifier)
        """
        # Handle both new and legacy schemas
        source_type = getattr(obj_in, "source_type", None) or getattr(obj_in, "short_name", None)

        # Build payload - exclude OAuth-specific fields (and the whole authentication object
        # to avoid leaking secrets)
        exclude_fields = {
            "client_id",
            "client_secret",
            "token_inject",
            "redirect_url",
            "auth_mode",
            "custom_client",
            "auth_method",
            "authentication",  # prevent client_secret leakage into payload
        }
        payload = obj_in.model_dump(
            exclude=exclude_fields,
            exclude_none=True,
        )

        # ---- Resolve client credentials with explicit, named flows ----
        client_id: Optional[str] = None
        client_secret: Optional[str] = None
        oauth_client_mode = "platform_default"

        def _require_both_or_neither(cid: Optional[str], csec: Optional[str]) -> None:
            if (cid and not csec) or (csec and not cid):
                raise HTTPException(
                    status_code=422,
                    detail="Custom OAuth requires both client_id and client_secret or neither",
                )

        # 1) BYOC nested under authentication
        auth_obj = getattr(obj_in, "authentication", None)
        nested_id = getattr(auth_obj, "client_id", None) if auth_obj is not None else None
        nested_secret = getattr(auth_obj, "client_secret", None) if auth_obj is not None else None
        if nested_id or nested_secret:
            _require_both_or_neither(nested_id, nested_secret)
            if nested_id and nested_secret:
                client_id, client_secret = nested_id, nested_secret
                oauth_client_mode = "byoc_nested"
        else:
            # 2) Legacy custom_client
            custom_client = getattr(obj_in, "custom_client", None)
            if custom_client:
                cc_id = getattr(custom_client, "client_id", None)
                cc_secret = getattr(custom_client, "client_secret", None)
                if cc_id or cc_secret:
                    _require_both_or_neither(cc_id, cc_secret)
                    if cc_id and cc_secret:
                        client_id, client_secret = cc_id, cc_secret
                        oauth_client_mode = "byoc_custom_client"
            # 3) Top-level request fields
            elif hasattr(obj_in, "client_id") or hasattr(obj_in, "client_secret"):
                top_id = getattr(obj_in, "client_id", None)
                top_secret = getattr(obj_in, "client_secret", None)
                if top_id or top_secret:
                    _require_both_or_neither(top_id, top_secret)
                    if top_id and top_secret:
                        client_id, client_secret = top_id, top_secret
                        oauth_client_mode = "byoc_top_level"

        # 4) Platform default: keep client_id/client_secret as None

        # NOTE: template_configs is passed in pre-validated by caller (source_connection_service)
        # No need to re-validate here - just use what was passed in

        overrides = {
            "client_id": client_id,
            "client_secret": client_secret,
            "oauth_client_mode": oauth_client_mode,
            # Final UI redirect (not the provider callback). Defaults to app URL.
            "redirect_url": getattr(obj_in, "redirect_url", core_settings.app_url),
            # OAuth provider callback that this backend handles:
            "oauth_redirect_uri": f"{core_settings.api_url}/source-connections/callback",
            # NEW: Store template configs for callback (pre-validated by caller)
            "template_configs": template_configs,
        }

        # Merge additional overrides (e.g., PKCE code_verifier) if provided
        if additional_overrides:
            overrides.update(additional_overrides)

        expires_at = datetime.now(timezone.utc) + timedelta(minutes=30)

        return await connection_init_session.create(
            db,
            obj_in={
                "organization_id": ctx.organization.id,
                "short_name": source_type,
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

    async def create_proxy_url(
        self, db: AsyncSession, provider_auth_url: str, ctx: ApiContext, uow: Any = None
    ) -> Tuple[str, datetime, UUID]:
        """Create proxy URL for OAuth flow.

        Returns:
            Tuple of (proxy_url, proxy_expires, redirect_session_id)
        """
        proxy_ttl = 1440  # 24 hours
        proxy_expires = datetime.now(timezone.utc) + timedelta(minutes=proxy_ttl)
        code8 = await redirect_session.generate_unique_code(db, length=8)

        redirect_sess = await redirect_session.create(
            db,
            code=code8,
            final_url=provider_auth_url,
            expires_at=proxy_expires,
            ctx=ctx,
            uow=uow,
        )

        proxy_url = f"{core_settings.api_url}/source-connections/authorize/{code8}"
        return proxy_url, proxy_expires, redirect_sess.id

    async def exchange_oauth1_code(
        self,
        short_name: str,
        verifier: str,
        overrides: Dict[str, Any],
        oauth_settings: OAuth1Settings,
        ctx: ApiContext,
    ) -> "OAuth1TokenResponse":
        """Exchange OAuth1 verifier for access token.

        Args:
            short_name: Integration short name
            verifier: OAuth verifier from user authorization
            overrides: Session overrides with request token credentials
            oauth_settings: OAuth1 settings
            ctx: API context

        Returns:
            OAuth1TokenResponse with access token credentials
        """
        ctx.logger.info(f"Exchanging OAuth1 verifier for access token: {short_name}")

        return await oauth1_service.exchange_token(
            access_token_url=oauth_settings.access_token_url,
            consumer_key=oauth_settings.consumer_key,
            consumer_secret=oauth_settings.consumer_secret,
            oauth_token=overrides.get("oauth_token", ""),
            oauth_token_secret=overrides.get("oauth_token_secret", ""),
            oauth_verifier=verifier,
            logger=ctx.logger,
        )

    async def exchange_oauth2_code(
        self,
        short_name: str,
        code: str,
        overrides: Dict[str, Any],
        ctx: ApiContext,
    ) -> "OAuth2TokenResponse":
        """Exchange OAuth2 authorization code for access token.

        Supports PKCE for providers like Airtable.

        Args:
            short_name: Integration short name
            code: Authorization code from OAuth provider
            overrides: Session overrides with client credentials and PKCE data
            ctx: API context

        Returns:
            OAuth2TokenResponse with access and refresh tokens
        """
        redirect_uri = (
            overrides.get("oauth_redirect_uri")
            or f"{core_settings.api_url}/source-connections/callback"
        )

        # Extract template configs from overrides
        template_configs = overrides.get("template_configs")
        # Retrieve PKCE code verifier if it was stored during authorization
        code_verifier = overrides.get("code_verifier")

        return await oauth2_service.exchange_authorization_code_for_token_with_redirect(
            ctx=ctx,
            source_short_name=short_name,
            code=code,
            redirect_uri=redirect_uri,
            client_id=overrides.get("client_id"),
            client_secret=overrides.get("client_secret"),
            template_configs=template_configs,
            code_verifier=code_verifier,
        )

    async def complete_oauth1_connection(
        self,
        db: AsyncSession,
        source_conn_shell: schemas.SourceConnection,
        init_session: Any,
        token_response: "OAuth1TokenResponse",
        ctx: ApiContext,
    ) -> Any:
        """Complete OAuth1 connection after callback.

        Builds OAuth1 credentials with oauth_token, oauth_token_secret,
        and consumer credentials for API signing.

        Detects BYOC by checking if consumer credentials differ from defaults.
        """
        source = await crud.source.get_by_short_name(db, short_name=init_session.short_name)
        if not source:
            raise HTTPException(
                status_code=404, detail=f"Source '{init_session.short_name}' not found"
            )

        init_session_id = init_session.id
        payload = init_session.payload or {}
        overrides = init_session.overrides or {}

        # Build OAuth1 credentials
        auth_fields = {
            "oauth_token": token_response.oauth_token,
            "oauth_token_secret": token_response.oauth_token_secret,
        }

        # Add consumer credentials for future API calls (needed for signing)
        consumer_key = overrides.get("consumer_key")
        consumer_secret = overrides.get("consumer_secret")

        if consumer_key:
            auth_fields["consumer_key"] = consumer_key
        if consumer_secret:
            auth_fields["consumer_secret"] = consumer_secret

        # Determine if BYOC by checking if credentials differ from platform defaults
        from airweave.platform.auth.settings import integration_settings

        try:
            platform_settings = await integration_settings.get_by_short_name(
                init_session.short_name
            )
            from airweave.platform.auth.schemas import OAuth1Settings

            if isinstance(platform_settings, OAuth1Settings):
                # Check if user provided custom consumer_key (different from platform default)
                is_byoc = (
                    consumer_key is not None and consumer_key != platform_settings.consumer_key
                )
            else:
                is_byoc = False
        except Exception:
            # If we can't determine, assume not BYOC
            is_byoc = False

        auth_method_to_save = (
            AuthenticationMethod.OAUTH_BYOC if is_byoc else AuthenticationMethod.OAUTH_BROWSER
        )

        # Continue with common logic
        return await self._complete_oauth_connection_common(
            db,
            source,
            source_conn_shell,
            init_session_id,
            payload,
            auth_fields,
            auth_method_to_save,
            is_oauth1=True,  # ✅ Explicit parameter
            ctx=ctx,
        )

    async def complete_oauth2_connection(
        self,
        db: AsyncSession,
        source_conn_shell: schemas.SourceConnection,
        init_session: Any,
        token_response: "OAuth2TokenResponse",
        ctx: ApiContext,
    ) -> Any:
        """Complete OAuth2 connection after callback.

        Builds OAuth2 credentials with access_token, refresh_token,
        and optional BYOC client credentials.
        """
        source = await crud.source.get_by_short_name(db, short_name=init_session.short_name)
        if not source:
            raise HTTPException(
                status_code=404, detail=f"Source '{init_session.short_name}' not found"
            )

        init_session_id = init_session.id
        payload = init_session.payload or {}
        overrides = init_session.overrides or {}

        # Build OAuth2 credentials
        auth_fields = token_response.model_dump()

        # Add BYOC client credentials if present
        if overrides.get("client_id"):
            auth_fields["client_id"] = overrides["client_id"]
        if overrides.get("client_secret"):
            auth_fields["client_secret"] = overrides["client_secret"]

        # Decide which auth method to record based on presence of BYOC client credentials
        auth_method_to_save = (
            AuthenticationMethod.OAUTH_BYOC
            if (overrides.get("client_id") and overrides.get("client_secret"))
            else AuthenticationMethod.OAUTH_BROWSER
        )

        # For Salesforce: extract instance_url from token response and update config
        # Salesforce returns the actual instance_url in the OAuth response
        # (e.g., orgfarm-xxx.salesforce.com)
        # This overrides whatever placeholder the user may have entered
        if init_session.short_name == "salesforce" and "instance_url" in auth_fields:
            # Get the instance_url from OAuth response
            instance_url_from_response = auth_fields.get("instance_url", "")
            if instance_url_from_response:
                # Normalize it (remove https:// if present)
                instance_url_normalized = instance_url_from_response.replace(
                    "https://", ""
                ).replace("http://", "")

                # Update the payload config with the real instance_url
                if not payload.get("config"):
                    payload["config"] = {}
                payload["config"]["instance_url"] = instance_url_normalized

                ctx.logger.info(
                    f"Updated Salesforce instance_url from OAuth response: "
                    f"{instance_url_normalized}"
                )

        # Continue with common logic
        return await self._complete_oauth_connection_common(
            db,
            source,
            source_conn_shell,
            init_session_id,
            payload,
            auth_fields,
            auth_method_to_save,
            is_oauth1=False,  # ✅ Explicit parameter
            ctx=ctx,
        )

    async def _complete_oauth_connection_common(
        self,
        db: AsyncSession,
        source: Any,
        source_conn_shell: schemas.SourceConnection,
        init_session_id: UUID,
        payload: Dict[str, Any],
        auth_fields: Dict[str, Any],
        auth_method_to_save: AuthenticationMethod,
        is_oauth1: bool,
        ctx: ApiContext,
    ) -> Any:
        """Common logic for completing OAuth connections (shared by OAuth1/OAuth2).

        Args:
            db: Database session
            source: Source schema
            source_conn_shell: Shell source connection to complete
            init_session_id: Init session ID
            payload: Request payload from init session
            auth_fields: OAuth credentials (different structure for OAuth1 vs OAuth2)
            auth_method_to_save: Authentication method to record
            is_oauth1: True for OAuth1, False for OAuth2
            ctx: API context
        """
        # Validate config fields if provided (payload uses 'config')
        validated_config = await self.validate_config_fields(
            db, source.short_name, payload.get("config"), ctx
        )

        # Use explicit parameter instead of checking dictionary keys
        auth_type_name = "OAuth1" if is_oauth1 else "OAuth2"

        async with UnitOfWork(db) as uow:
            # Create credential
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

            # Create connection
            conn_in = schemas.ConnectionCreate(
                name=payload.get("name", f"Connection to {source.name}"),
                integration_type=IntegrationType.SOURCE,
                status=ConnectionStatus.ACTIVE,
                integration_credential_id=credential.id,
                short_name=source.short_name,
            )
            connection = await crud.connection.create(uow.session, obj_in=conn_in, ctx=ctx, uow=uow)

            # Get collection (prefer what was originally requested; fall back to shell)
            collection = await self.get_collection(
                uow.session,
                payload.get("readable_collection_id") or source_conn_shell.readable_collection_id,
                ctx,
            )

            # Create sync
            await db.flush()
            await db.refresh(connection)

            # Check if this is a federated search source - these don't need syncs
            source_class = resource_locator.get_source(source)
            is_federated = getattr(source_class, "federated_search", False)

            if is_federated:
                ctx.logger.info(
                    f"Skipping sync creation for federated search source '{source.short_name}'. "
                    "Federated search sources are searched at query time."
                )
                # Update shell source connection without sync
                sc_update = {
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
                # Use the create_sync helper to ensure default schedule is applied
                # Note: We temporarily skip Temporal schedule creation here because
                # the source_connection hasn't been updated with sync_id yet
                cron_schedule = (
                    payload.get("schedule", {}).get("cron")
                    if isinstance(payload.get("schedule"), dict)
                    else payload.get("cron_schedule")
                )
                if cron_schedule is None:
                    if getattr(source_class, "supports_continuous", False):
                        # Continuous connectors should default to fast incremental syncs
                        cron_schedule = "*/5 * * * *"
                        ctx.logger.info(
                            "No cron schedule provided for continuous source '%s', "
                            "defaulting to 5-minute incremental syncs",
                            source.short_name,
                        )
                    else:
                        # Generate default daily schedule anchored to current UTC time
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

                sync, sync_job = await self.create_sync_without_schedule(
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

                # Update shell source connection with sync
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

                # Now that source_connection is linked to sync, create the Temporal schedule
                await uow.session.flush()  # Ensure the source_connection update is visible
                from airweave.platform.temporal.schedule_service import temporal_schedule_service

                await temporal_schedule_service.create_or_update_schedule(
                    sync_id=sync.id,
                    cron_schedule=cron_schedule,
                    db=uow.session,
                    ctx=ctx,
                    uow=uow,
                )

            # Mark init session complete
            await connection_init_session.mark_completed(
                uow.session,
                session_id=init_session_id,
                final_connection_id=sc_update["connection_id"],
                ctx=ctx,
            )

            await uow.commit()
            await uow.session.refresh(source_conn)

        return source_conn

    async def get_connection_for_source_connection(
        self,
        db: AsyncSession,
        source_connection: SourceConnection,
        ctx: ApiContext,
    ) -> schemas.Connection:
        """Get the Connection object for a SourceConnection.

        Args:
            db: Database session
            source_connection: The source connection model
            ctx: API context

        Returns:
            The Connection schema object

        Raises:
            ValueError: If source connection has no connection_id or connection not found
        """
        if not source_connection.connection_id:
            raise ValueError(f"Source connection {source_connection.id} has no connection_id")

        connection = await crud.connection.get(db=db, id=source_connection.connection_id, ctx=ctx)
        if not connection:
            raise ValueError(f"Connection {source_connection.connection_id} not found")

        return schemas.Connection.model_validate(connection, from_attributes=True)


# Singleton instance
source_connection_helpers = SourceConnectionHelpers()
