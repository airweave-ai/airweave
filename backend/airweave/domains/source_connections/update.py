"""Source connection update service."""

import re
from typing import Any, Dict, Optional
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from airweave import crud, schemas
from airweave.api.context import ApiContext
from airweave.core import credentials
from airweave.core.exceptions import NotFoundException
from airweave.core.source_connection_service_helpers import source_connection_helpers
from airweave.db.unit_of_work import UnitOfWork
from airweave.domains.collections.protocols import CollectionRepositoryProtocol
from airweave.domains.connections.protocols import ConnectionRepositoryProtocol
from airweave.domains.credentials.protocols import IntegrationCredentialRepositoryProtocol
from airweave.domains.source_connections.protocols import (
    ResponseBuilderProtocol,
    SourceConnectionRepositoryProtocol,
)
from airweave.domains.syncs.protocols import SyncRepositoryProtocol
from airweave.domains.temporal.protocols import TemporalScheduleServiceProtocol
from airweave.schemas.source_connection import (
    SourceConnection as SourceConnectionSchema,
)
from airweave.schemas.source_connection import (
    AuthenticationMethod,
    SourceConnectionUpdate,
)


class SourceConnectionUpdateService:
    """Updates a source connection.

    Handles:
    - Config field updates with validation
    - Schedule updates (create, update, or remove)
    - Credential updates for direct auth only
    """

    def __init__(
        self,
        sc_repo: SourceConnectionRepositoryProtocol,
        collection_repo: CollectionRepositoryProtocol,
        connection_repo: ConnectionRepositoryProtocol,
        cred_repo: IntegrationCredentialRepositoryProtocol,
        sync_repo: SyncRepositoryProtocol,
        response_builder: ResponseBuilderProtocol,
        temporal_schedule_service: TemporalScheduleServiceProtocol,
    ) -> None:
        self._sc_repo = sc_repo
        self._collection_repo = collection_repo
        self._connection_repo = connection_repo
        self._cred_repo = cred_repo
        self._sync_repo = sync_repo
        self._response_builder = response_builder
        self._temporal_schedule_service = temporal_schedule_service

    async def update(
        self,
        db: AsyncSession,
        *,
        id: UUID,
        obj_in: SourceConnectionUpdate,
        ctx: ApiContext,
    ) -> SourceConnectionSchema:
        """Update a source connection."""
        async with UnitOfWork(db) as uow:
            # Re-fetch the source_conn within the UoW session to avoid session mismatch
            source_conn = await self._sc_repo.get(uow.session, id=id, ctx=ctx)
            if not source_conn:
                raise NotFoundException("Source connection not found")

            # Update fields
            update_data = obj_in.model_dump(exclude_unset=True)

            # Normalize nested authentication payloads (Direct auth updates)
            if "authentication" in update_data:
                auth_payload = update_data.get("authentication") or {}
                creds = auth_payload.get("credentials")
                if creds:
                    update_data["credentials"] = creds
                # Remove authentication object so we don't try to persist it on the model
                del update_data["authentication"]

            # Handle config update
            if "config" in update_data:
                validated_config = await source_connection_helpers.validate_config_fields(
                    uow.session, source_conn.short_name, update_data["config"], ctx
                )
                update_data["config_fields"] = validated_config
                del update_data["config"]

            # Handle schedule update
            await self._handle_schedule_update(uow, source_conn, update_data, ctx)

            # Handle credential update (direct auth only)
            if "credentials" in update_data:
                from airweave.schemas.source_connection import determine_auth_method

                auth_method = determine_auth_method(source_conn)
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
                source_conn = await self._sc_repo.update(
                    uow.session,
                    db_obj=source_conn,
                    obj_in=update_data,
                    ctx=ctx,
                    uow=uow,
                )

            await uow.commit()
            await uow.session.refresh(source_conn)

        return await self._response_builder.build_response(db, source_conn, ctx)

    async def _handle_schedule_update(
        self,
        uow: UnitOfWork,
        source_conn: Any,
        update_data: dict,
        ctx: ApiContext,
    ) -> None:
        """Handle schedule updates for a source connection.

        This method handles three cases:
        1. Updating an existing sync's schedule
        2. Creating a new sync when adding a schedule to a connection without one
        3. Removing a schedule (setting cron to None)

        Args:
            uow: Unit of work
            source_conn: Source connection being updated
            update_data: Update data dictionary (modified in place)
            ctx: API context
        """
        if "schedule" not in update_data:
            return

        # If schedule is None, treat it as removing the schedule
        if update_data["schedule"] is None:
            new_cron = None
        else:
            new_cron = update_data["schedule"].get("cron")

        if source_conn.sync_id:
            # Update existing sync's schedule
            if new_cron:
                # Get the source to validate schedule
                source = await self._get_and_validate_source(uow.session, source_conn.short_name)
                self._validate_cron_schedule_for_source(new_cron, source, ctx)
            await self._update_sync_schedule(
                uow.session,
                source_conn.sync_id,
                new_cron,
                ctx,
                uow,
            )
        elif new_cron:
            # No sync exists but we're adding a schedule - create a new sync
            # Get the source to validate schedule
            source = await self._get_and_validate_source(uow.session, source_conn.short_name)
            self._validate_cron_schedule_for_source(new_cron, source, ctx)

            # Check if connection_id exists (might be None for OAuth flows)
            if not source_conn.connection_id:
                ctx.logger.warning(
                    f"Cannot create schedule for SC {source_conn.id} without connection_id"
                )
                # Skip schedule creation for connections without connection_id
                del update_data["schedule"]
                return

            # Get the collection
            collection = await self._collection_repo.get_by_readable_id(
                uow.session, readable_id=source_conn.readable_collection_id, ctx=ctx
            )
            if not collection:
                raise NotFoundException("Collection not found")

            # Create a new sync with the schedule
            sync, _ = await source_connection_helpers.create_sync_without_schedule(
                uow.session,
                source_conn.name,
                source_conn.connection_id,
                collection.id,
                collection.readable_id,
                new_cron,
                False,  # Don't run immediately on update
                ctx,
                uow,
            )

            # Apply the sync_id update to the source connection now
            # so that temporal_schedule_service can find it
            source_conn = await self._sc_repo.update(
                uow.session,
                db_obj=source_conn,
                obj_in={"sync_id": sync.id},
                ctx=ctx,
                uow=uow,
            )
            await uow.session.flush()

            # Create the Temporal schedule
            await self._temporal_schedule_service.create_or_update_schedule(
                sync_id=sync.id,
                cron_schedule=new_cron,
                db=uow.session,
                ctx=ctx,
                uow=uow,
            )

        if "schedule" in update_data:
            del update_data["schedule"]

    async def _get_and_validate_source(self, db: AsyncSession, short_name: str) -> schemas.Source:
        """Get and validate source exists."""
        source = await crud.source.get_by_short_name(db, short_name=short_name)
        if not source:
            raise HTTPException(status_code=404, detail=f"Source '{short_name}' not found")
        return source

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
        if not cron_schedule:
            return

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

    async def _update_sync_schedule(
        self,
        db: AsyncSession,
        sync_id: UUID,
        cron_schedule: Optional[str],
        ctx: ApiContext,
        uow: UnitOfWork,
    ) -> None:
        """Update sync schedule in database and Temporal."""
        sync = await self._sync_repo.get_without_connections(db, id=sync_id, ctx=ctx)
        if sync:
            # Update in database
            sync_update = schemas.SyncUpdate(cron_schedule=cron_schedule)
            await self._sync_repo.update(db, db_obj=sync, obj_in=sync_update, ctx=ctx, uow=uow)

            # Update in Temporal
            if cron_schedule is None:
                # If cron_schedule is None, delete the Temporal schedule
                await self._temporal_schedule_service.delete_all_schedules_for_sync(
                    sync_id=sync_id, db=db, ctx=ctx
                )
            else:
                # Otherwise create or update the schedule
                await self._temporal_schedule_service.create_or_update_schedule(
                    sync_id=sync_id,
                    cron_schedule=cron_schedule,
                    db=db,
                    ctx=ctx,
                    uow=uow,
                )

    async def _update_auth_fields(
        self,
        db: AsyncSession,
        source_conn: Any,
        auth_fields: Any,
        ctx: ApiContext,
        uow: UnitOfWork,
    ) -> None:
        """Update authentication fields."""
        validated_auth = await source_connection_helpers.validate_auth_fields(
            db, source_conn.short_name, auth_fields, ctx
        )
        if hasattr(validated_auth, "model_dump"):
            serializable_auth = validated_auth.model_dump()
        elif hasattr(validated_auth, "dict"):
            serializable_auth = validated_auth.dict()
        else:
            serializable_auth = validated_auth

        connection = await self._connection_repo.get(db, id=source_conn.connection_id, ctx=ctx)
        if connection and connection.integration_credential_id:
            credential = await self._cred_repo.get(
                db, id=connection.integration_credential_id, ctx=ctx
            )
            if credential:
                credential_update = schemas.IntegrationCredentialUpdate(
                    encrypted_credentials=credentials.encrypt(serializable_auth)
                )
                await self._cred_repo.update(
                    db, db_obj=credential, obj_in=credential_update, ctx=ctx, uow=uow
                )
