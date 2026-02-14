"""Response builder for source connections.

Assembles the rich SourceConnection and SourceConnectionListItem
response schemas from multiple data sources. Domain-specific --
each domain builds its own responses.
"""

from typing import Any, Dict, Optional
from uuid import UUID

from airweave import crud, schemas
from airweave.core.config import settings as core_settings
from airweave.core.shared_models import SyncJobStatus
from airweave.schemas.source_connection import (
    AuthenticationDetails,
    AuthenticationMethod,
    SourceConnection,
    SourceConnectionJob,
    SourceConnectionListItem,
    compute_status,
    determine_auth_method,
)


class ResponseBuilder:
    """Builds API response schemas for source connections."""

    async def build_response(self, db: Any, source_conn: Any, ctx: Any) -> SourceConnection:
        """Build complete SourceConnection response from an ORM object.

        Stitches together auth info, schedule, sync details, entity counts,
        and status from multiple tables.
        """
        auth = await self._build_auth_details(db, source_conn, ctx)
        schedule = await self._build_schedule_details(db, source_conn, ctx)
        sync_details = await self._build_sync_details(db, source_conn, ctx)
        entities = await self._build_entity_summary(db, source_conn, ctx)
        federated_search = await self._get_federated_search(db, source_conn, ctx)

        last_job_status = None
        if sync_details and sync_details.last_job:
            last_job_status = sync_details.last_job.status

        return SourceConnection(
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

    def build_list_item(self, data: Dict[str, Any]) -> SourceConnectionListItem:
        """Build a SourceConnectionListItem from a stats dict.

        The dict comes from SourceConnectionRepository.get_multi_with_stats().

        Note: status is a @computed_field on SourceConnectionListItem that
        derives from is_authenticated, is_active, and last_job_status.
        We pass the raw data and let the schema compute it.
        """
        last_job = data.get("last_job")
        last_job_status = last_job.get("status") if last_job else None

        return SourceConnectionListItem(
            id=data["id"],
            name=data["name"],
            short_name=data["short_name"],
            readable_collection_id=data["readable_collection_id"],
            created_at=data["created_at"],
            modified_at=data["modified_at"],
            is_authenticated=data.get("is_authenticated", True),
            authentication_method=data.get("authentication_method"),
            entity_count=data.get("entity_count", 0),
            is_active=data.get("is_active", True),
            last_job_status=last_job_status,
        )

    def map_sync_job(self, job: Any, source_connection_id: UUID) -> SourceConnectionJob:
        """Convert a sync job ORM object to a SourceConnectionJob schema."""
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

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _build_auth_details(
        self, db: Any, source_conn: Any, ctx: Any
    ) -> AuthenticationDetails:
        """Build authentication details section."""
        actual_auth_method = await self._resolve_auth_method(db, source_conn, ctx)

        auth_info: Dict[str, Any] = {
            "method": actual_auth_method,
            "authenticated": source_conn.is_authenticated,
        }

        if source_conn.is_authenticated:
            auth_info["authenticated_at"] = source_conn.created_at

        if (
            hasattr(source_conn, "readable_auth_provider_id")
            and source_conn.readable_auth_provider_id
        ):
            auth_info["provider_id"] = source_conn.readable_auth_provider_id
            auth_info["provider_readable_id"] = source_conn.readable_auth_provider_id

        if (
            hasattr(source_conn, "connection_init_session_id")
            and source_conn.connection_init_session_id
        ):
            await self._attach_oauth_pending_info(db, source_conn, ctx, auth_info)
        elif hasattr(source_conn, "authentication_url") and source_conn.authentication_url:
            auth_info["auth_url"] = source_conn.authentication_url
            if hasattr(source_conn, "authentication_url_expiry"):
                auth_info["auth_url_expires"] = source_conn.authentication_url_expiry

        return AuthenticationDetails(**auth_info)

    async def _resolve_auth_method(
        self, db: Any, source_conn: Any, ctx: Any
    ) -> AuthenticationMethod:
        """Resolve the auth method from auth provider, credential, or fallback."""
        if (
            hasattr(source_conn, "readable_auth_provider_id")
            and source_conn.readable_auth_provider_id
        ):
            return AuthenticationMethod.AUTH_PROVIDER

        if source_conn.connection_id:
            connection = await crud.connection.get(db, id=source_conn.connection_id, ctx=ctx)
            if connection and connection.integration_credential_id:
                credential = await crud.integration_credential.get(
                    db, id=connection.integration_credential_id, ctx=ctx
                )
                if credential and hasattr(credential, "authentication_method"):
                    method_map = {
                        "oauth_token": AuthenticationMethod.OAUTH_TOKEN,
                        "oauth_browser": AuthenticationMethod.OAUTH_BROWSER,
                        "oauth_byoc": AuthenticationMethod.OAUTH_BYOC,
                        "direct": AuthenticationMethod.DIRECT,
                        "auth_provider": AuthenticationMethod.AUTH_PROVIDER,
                    }
                    resolved = method_map.get(credential.authentication_method)
                    if resolved:
                        return resolved

        return determine_auth_method(source_conn)

    async def _attach_oauth_pending_info(
        self, db: Any, source_conn: Any, ctx: Any, auth_info: dict
    ) -> None:
        """Attach OAuth pending auth_url and redirect_url from init session."""
        from sqlalchemy import select
        from sqlalchemy.orm import selectinload

        from airweave.models import ConnectionInitSession

        stmt = (
            select(ConnectionInitSession)
            .where(ConnectionInitSession.id == source_conn.connection_init_session_id)
            .where(ConnectionInitSession.organization_id == ctx.organization.id)
            .options(selectinload(ConnectionInitSession.redirect_session))
        )
        result = await db.execute(stmt)
        init_session = result.scalar_one_or_none()
        if init_session:
            if init_session.overrides:
                redirect_url = init_session.overrides.get("redirect_url")
                if redirect_url:
                    auth_info["redirect_url"] = redirect_url
            if init_session.redirect_session and not source_conn.is_authenticated:
                auth_info["auth_url"] = (
                    f"{core_settings.api_url}/source-connections/authorize/"
                    f"{init_session.redirect_session.code}"
                )
                auth_info["auth_url_expires"] = init_session.redirect_session.expires_at

    async def _build_schedule_details(
        self, db: Any, source_conn: Any, ctx: Any
    ) -> Optional[schemas.ScheduleDetails]:
        """Build schedule section."""
        if not getattr(source_conn, "sync_id", None):
            return None
        try:
            schedule_info = await crud.source_connection.get_schedule_info(db, source_conn)
            if schedule_info:
                return schemas.ScheduleDetails(
                    cron=schedule_info.get("cron_expression"),
                    next_run=schedule_info.get("next_run_at"),
                    continuous=schedule_info.get("is_continuous", False),
                    cursor_field=schedule_info.get("cursor_field"),
                    cursor_value=schedule_info.get("cursor_value"),
                )
        except Exception as e:
            ctx.logger.warning(f"Failed to get schedule info: {e}")
        return None

    async def _build_sync_details(
        self, db: Any, source_conn: Any, ctx: Any
    ) -> Optional[schemas.SyncDetails]:
        """Build sync/job details section."""
        if not getattr(source_conn, "sync_id", None):
            return None
        try:
            from airweave.core.sync_service import sync_service

            job = await sync_service.get_last_sync_job(db, ctx=ctx, sync_id=source_conn.sync_id)
            if job:
                duration_seconds = None
                if job.completed_at and job.started_at:
                    duration_seconds = (job.completed_at - job.started_at).total_seconds()

                last_job = schemas.SyncJobDetails(
                    id=job.id,
                    status=job.status,
                    started_at=getattr(job, "started_at", None),
                    completed_at=getattr(job, "completed_at", None),
                    duration_seconds=duration_seconds,
                    entities_inserted=getattr(job, "entities_inserted", 0) or 0,
                    entities_updated=getattr(job, "entities_updated", 0) or 0,
                    entities_deleted=getattr(job, "entities_deleted", 0) or 0,
                    entities_failed=getattr(job, "entities_skipped", 0) or 0,
                    error=getattr(job, "error", None),
                )
                return schemas.SyncDetails(
                    total_runs=1,
                    successful_runs=1 if job.status == SyncJobStatus.COMPLETED else 0,
                    failed_runs=1 if job.status == SyncJobStatus.FAILED else 0,
                    last_job=last_job,
                )
        except Exception as e:
            ctx.logger.warning(f"Failed to get sync details: {e}")
        return None

    async def _build_entity_summary(
        self, db: Any, source_conn: Any, ctx: Any
    ) -> Optional[schemas.EntitySummary]:
        """Build entity summary section."""
        if not getattr(source_conn, "sync_id", None):
            return None
        try:
            entity_counts = await crud.entity_count.get_counts_per_sync_and_type(
                db, source_conn.sync_id
            )
            if entity_counts:
                total_entities = sum(c.count for c in entity_counts)
                by_type = {
                    c.entity_definition_name: schemas.EntityTypeStats(
                        count=c.count, last_updated=c.modified_at
                    )
                    for c in entity_counts
                }
                return schemas.EntitySummary(total_entities=total_entities, by_type=by_type)
        except Exception as e:
            ctx.logger.warning(f"Failed to get entity summary: {e}")
        return None

    async def _get_federated_search(self, db: Any, source_conn: Any, ctx: Any) -> bool:
        """Get federated_search flag for the source."""
        try:
            source_model = await crud.source.get_by_short_name(db, source_conn.short_name)
            if source_model:
                return getattr(source_model, "federated_search", False)
        except Exception as e:
            ctx.logger.warning(f"Failed to get federated_search for {source_conn.short_name}: {e}")
        return False
