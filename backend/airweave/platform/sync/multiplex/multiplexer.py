"""Sync multiplexer for managing multiple destinations per sync.

Enables blue-green deployments and migrations between vector DB configs:
- Fork: Create shadow destination, replay from ARF
- Switch: Promote shadow to active
- Resync: Force full sync from source to refresh ARF
- List: Show all destinations and their roles
"""

from typing import List, Optional
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from airweave import crud, schemas
from airweave.api.context import ApiContext
from airweave.core.logging import ContextualLogger
from airweave.core.shared_models import IntegrationType
from airweave.db.unit_of_work import UnitOfWork
from airweave.models.sync_connection import DestinationRole, SyncConnection
from airweave.platform.sync.raw_data import raw_data_service


class SyncMultiplexer:
    """Manages destination slots for a sync.

    Use cases:
    - Migration: Qdrant → Vespa, Vespa v0 → Vespa v1
    - A/B testing: Compare search quality across configs
    - Rollback: Keep previous destination available

    Typical workflow:
    1. resync_from_source() - Ensure ARF is up-to-date
    2. fork() - Create shadow destination, optionally replay from ARF
    3. Validate shadow destination (search quality, etc.)
    4. switch() - Promote shadow to active
    5. (Optional) cleanup deprecated destinations
    """

    def __init__(self, db: AsyncSession, ctx: ApiContext, logger: ContextualLogger):
        """Initialize the multiplexer.

        Args:
            db: Database session
            ctx: API context (used for access control)
            logger: Contextual logger
        """
        self.db = db
        self.ctx = ctx
        self.logger = logger

    # =========================================================================
    # Fork: Create shadow destination
    # =========================================================================

    async def fork(
        self,
        sync_id: UUID,
        destination_connection_id: UUID,
        replay_from_arf: bool = False,
    ) -> tuple[SyncConnection, Optional[schemas.SyncJob]]:
        """Create a shadow destination and optionally populate from ARF.

        Args:
            sync_id: Sync to fork destination for
            destination_connection_id: New destination connection to add
            replay_from_arf: If True, kicks off replay job from ARF

        Returns:
            Tuple of (SyncConnection, Optional[SyncJob])
            - SyncJob is returned if replay_from_arf=True

        Raises:
            HTTPException: If sync not found, destination invalid, or already exists
        """
        # 1. Validate sync exists and user has access
        sync = await crud.sync.get(self.db, id=sync_id, ctx=self.ctx, with_connections=False)
        if not sync:
            raise HTTPException(status_code=404, detail=f"Sync {sync_id} not found")

        # 2. Check destination connection exists and is a valid destination
        dest_conn = await crud.connection.get(self.db, id=destination_connection_id, ctx=self.ctx)
        if not dest_conn:
            raise HTTPException(
                status_code=404, detail=f"Connection {destination_connection_id} not found"
            )
        if dest_conn.integration_type != IntegrationType.DESTINATION.value:
            raise HTTPException(
                status_code=400,
                detail=f"Connection {destination_connection_id} is not a destination",
            )

        # 3. Check if slot already exists
        existing = await crud.sync_connection.get_by_sync_and_connection(
            self.db, sync_id=sync_id, connection_id=destination_connection_id
        )
        if existing:
            raise HTTPException(
                status_code=400,
                detail=f"Destination {destination_connection_id} already exists for sync {sync_id}",
            )

        # 4. Create shadow slot
        async with UnitOfWork(self.db) as uow:
            slot = await crud.sync_connection.create(
                self.db,
                sync_id=sync_id,
                connection_id=destination_connection_id,
                role=DestinationRole.SHADOW,
                uow=uow,
            )

            # Also update sync.destination_connection_ids to include the new destination
            # This ensures backward compatibility with existing sync flow
            current_dest_ids = list(sync.destination_connection_ids or [])
            if destination_connection_id not in current_dest_ids:
                current_dest_ids.append(destination_connection_id)
                await crud.sync.update(
                    self.db,
                    db_obj=sync,
                    obj_in=schemas.SyncUpdate(destination_connection_ids=current_dest_ids),
                    ctx=self.ctx,
                    uow=uow,
                )

            await uow.commit()

        self.logger.info(
            f"Created shadow slot for sync {sync_id} → {dest_conn.name}",
            extra={"slot_id": str(slot.id), "destination_id": str(destination_connection_id)},
        )

        # 5. Kick off replay if requested
        replay_job = None
        if replay_from_arf:
            replay_job = await self._start_replay_job(sync_id, slot.id, destination_connection_id)

        return slot, replay_job

    # =========================================================================
    # Switch: Promote shadow to active
    # =========================================================================

    async def switch(
        self,
        sync_id: UUID,
        new_active_slot_id: UUID,
    ) -> schemas.SwitchDestinationResponse:
        """Promote a shadow destination to active.

        Args:
            sync_id: Sync to switch
            new_active_slot_id: Slot ID to promote

        Returns:
            SwitchDestinationResponse with status and slot IDs

        Raises:
            HTTPException: If slot not found or not a shadow
        """
        # 1. Validate sync exists and user has access
        sync = await crud.sync.get(self.db, id=sync_id, ctx=self.ctx, with_connections=False)
        if not sync:
            raise HTTPException(status_code=404, detail=f"Sync {sync_id} not found")

        # 2. Get all slots for this sync
        slots = await crud.sync_connection.get_by_sync_id(self.db, sync_id=sync_id)

        current_active = next((s for s in slots if s.role == DestinationRole.ACTIVE.value), None)
        target_slot = next((s for s in slots if s.id == new_active_slot_id), None)

        if not target_slot:
            raise HTTPException(
                status_code=404, detail=f"Slot {new_active_slot_id} not found for sync {sync_id}"
            )
        if target_slot.role != DestinationRole.SHADOW.value:
            raise HTTPException(
                status_code=400,
                detail=f"Slot {new_active_slot_id} is not a shadow (current: {target_slot.role})",
            )

        # 3. Perform the switch atomically
        async with UnitOfWork(self.db) as uow:
            previous_active_id = None

            # Demote current active (if exists)
            if current_active:
                await crud.sync_connection.update_role(
                    self.db, id=current_active.id, role=DestinationRole.DEPRECATED, uow=uow
                )
                previous_active_id = current_active.id
                self.logger.info(
                    f"Demoted slot {current_active.id} to DEPRECATED",
                    extra={"destination_id": str(current_active.connection_id)},
                )

            # Promote target to active
            await crud.sync_connection.update_role(
                self.db, id=target_slot.id, role=DestinationRole.ACTIVE, uow=uow
            )
            self.logger.info(
                f"Promoted slot {target_slot.id} to ACTIVE",
                extra={"destination_id": str(target_slot.connection_id)},
            )

            await uow.commit()

        return schemas.SwitchDestinationResponse(
            status="switched",
            new_active_slot_id=new_active_slot_id,
            previous_active_slot_id=previous_active_id,
        )

    # =========================================================================
    # List: Show all destinations and their roles
    # =========================================================================

    async def list_destinations(
        self,
        sync_id: UUID,
    ) -> List[schemas.DestinationSlotInfo]:
        """List all destinations for a sync with their roles.

        Args:
            sync_id: Sync ID

        Returns:
            List of DestinationSlotInfo sorted by role (active first)
        """
        # 1. Validate sync exists and user has access
        sync = await crud.sync.get(self.db, id=sync_id, ctx=self.ctx, with_connections=False)
        if not sync:
            raise HTTPException(status_code=404, detail=f"Sync {sync_id} not found")

        # 2. Get all slots
        slots = await crud.sync_connection.get_by_sync_id(self.db, sync_id=sync_id)

        # 3. Get ARF stats for entity count
        arf_stats = await raw_data_service.get_replay_stats(str(sync_id))
        entity_count = arf_stats.get("entity_count", 0) if arf_stats.get("exists") else 0

        # 4. Build response
        result = []
        for slot in slots:
            # Get connection details
            conn = await crud.connection.get(self.db, id=slot.connection_id, ctx=self.ctx)
            if not conn:
                continue  # Skip if connection was deleted

            result.append(
                schemas.DestinationSlotInfo(
                    slot_id=slot.id,
                    destination_connection_id=slot.connection_id,
                    destination_name=conn.name,
                    destination_short_name=conn.short_name,
                    role=DestinationRole(slot.role),
                    created_at=slot.created_at,
                    entity_count=entity_count,
                )
            )

        # Sort: ACTIVE → SHADOW → DEPRECATED
        role_order = {
            DestinationRole.ACTIVE: 0,
            DestinationRole.SHADOW: 1,
            DestinationRole.DEPRECATED: 2,
        }
        result.sort(key=lambda x: role_order.get(x.role, 99))

        return result

    async def get_active_destination(
        self,
        sync_id: UUID,
    ) -> Optional[schemas.DestinationSlotInfo]:
        """Get the active destination for queries.

        Args:
            sync_id: Sync ID

        Returns:
            Active destination info, or None if no active destination
        """
        slots = await self.list_destinations(sync_id)
        return next((s for s in slots if s.role == DestinationRole.ACTIVE), None)

    # =========================================================================
    # Resync: Force full sync from source to refresh ARF
    # =========================================================================

    async def resync_from_source(
        self,
        sync_id: UUID,
    ) -> schemas.SyncJob:
        """Trigger full sync from source to refresh ARF.

        Ensures ARF is up-to-date before forking to a new destination.
        Uses force_full_sync=True to bypass cursor and get all entities.

        Args:
            sync_id: Sync ID

        Returns:
            SyncJob for tracking progress
        """
        from airweave.core import source_connection_service

        # 1. Validate sync exists
        sync = await crud.sync.get(self.db, id=sync_id, ctx=self.ctx, with_connections=False)
        if not sync:
            raise HTTPException(status_code=404, detail=f"Sync {sync_id} not found")

        # 2. Get source connection for this sync
        source_conn = await crud.source_connection.get_by_sync_id(
            self.db, sync_id=sync_id, ctx=self.ctx
        )
        if not source_conn:
            raise HTTPException(
                status_code=404, detail=f"No source connection found for sync {sync_id}"
            )

        self.logger.info(
            "Triggering full resync from source for ARF refresh",
            extra={"sync_id": str(sync_id), "source_connection_id": str(source_conn.id)},
        )

        # 3. Trigger via existing service (force_full_sync=True)
        job = await source_connection_service.run(
            self.db,
            id=source_conn.id,
            ctx=self.ctx,
            force_full_sync=True,
        )

        # Convert SourceConnectionJob to SyncJob
        return schemas.SyncJob(
            id=job.id,
            sync_id=sync_id,
            organization_id=self.ctx.organization.id,
            status=job.status,
            started_at=job.started_at,
            completed_at=job.completed_at,
            entities_inserted=job.entities_inserted,
            entities_updated=job.entities_updated,
            entities_deleted=job.entities_deleted,
            entities_kept=job.entities_kept,
            entities_skipped=job.entities_skipped,
        )

    # =========================================================================
    # Private: Replay job management
    # =========================================================================

    async def _start_replay_job(
        self,
        sync_id: UUID,
        target_slot_id: UUID,
        target_destination_id: UUID,
    ) -> schemas.SyncJob:
        """Start ARF replay job to populate a shadow destination.

        Uses the SyncOrchestrator with ARFReplaySource for efficient replay
        that reuses all existing pipeline logic.

        Args:
            sync_id: Sync ID
            target_slot_id: Slot ID to replay to
            target_destination_id: Destination connection ID

        Returns:
            SyncJob tracking the replay progress
        """
        from airweave.platform.sync.multiplex.replay import replay_to_destination

        self.logger.info(
            f"Starting ARF replay for slot {target_slot_id}",
            extra={
                "sync_id": str(sync_id),
                "target_slot_id": str(target_slot_id),
                "target_destination_id": str(target_destination_id),
            },
        )

        return await replay_to_destination(
            db=self.db,
            ctx=self.ctx,
            sync_id=sync_id,
            target_connection_id=target_destination_id,
        )


async def get_multiplexer(db: AsyncSession, ctx: ApiContext) -> SyncMultiplexer:
    """Get a SyncMultiplexer instance.

    Args:
        db: Database session
        ctx: API context

    Returns:
        SyncMultiplexer instance
    """
    return SyncMultiplexer(db, ctx, ctx.logger)
