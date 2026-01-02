"""Sync multiplexer endpoints for destination migrations.

Feature-gated: requires SYNC_MULTIPLEXER flag enabled.
"""

from typing import List
from uuid import UUID

from fastapi import Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from airweave import crud, schemas
from airweave.api import deps
from airweave.api.context import ApiContext
from airweave.api.router import TrailingSlashRouter
from airweave.core.shared_models import FeatureFlag
from airweave.db.unit_of_work import UnitOfWork
from airweave.models.sync_connection import DestinationRole

router = TrailingSlashRouter()


def _require_feature(ctx: ApiContext) -> None:
    """Check if multiplexer feature is enabled."""
    if not ctx.has_feature(FeatureFlag.SYNC_MULTIPLEXER):
        raise HTTPException(status_code=403, detail="SYNC_MULTIPLEXER feature not enabled")


@router.get("/{sync_id}/destinations", response_model=List[schemas.DestinationSlotInfo])
async def list_destinations(
    sync_id: UUID,
    db: AsyncSession = Depends(deps.get_db),
    ctx: ApiContext = Depends(deps.get_context),
) -> List[schemas.DestinationSlotInfo]:
    """List all destination slots for a sync with their roles."""
    _require_feature(ctx)

    # Validate sync access
    sync = await crud.sync.get(db, id=sync_id, ctx=ctx, with_connections=False)
    if not sync:
        raise HTTPException(status_code=404, detail="Sync not found")

    # Get all slots (includes sources with role=NULL and destinations with role set)
    slots = await crud.sync_connection.get_by_sync_id(db, sync_id=sync_id)

    result = []
    for slot in slots:
        # Skip sources (role=NULL) - only show destinations
        if slot.role is None:
            continue

        conn = await crud.connection.get(db, id=slot.connection_id, ctx=ctx)
        if conn:
            result.append(
                schemas.DestinationSlotInfo(
                    slot_id=slot.id,
                    connection_id=slot.connection_id,
                    connection_name=conn.name,
                    role=DestinationRole(slot.role),
                    created_at=slot.created_at,
                )
            )

    # Sort: active first, then shadow, then deprecated
    role_order = {
        DestinationRole.ACTIVE: 0,
        DestinationRole.SHADOW: 1,
        DestinationRole.DEPRECATED: 2,
    }
    result.sort(key=lambda x: role_order.get(x.role, 99))
    return result


@router.post("/{sync_id}/destinations/fork", response_model=schemas.ForkDestinationResponse)
async def fork_destination(
    sync_id: UUID,
    request: schemas.ForkDestinationRequest,
    db: AsyncSession = Depends(deps.get_db),
    ctx: ApiContext = Depends(deps.get_context),
) -> schemas.ForkDestinationResponse:
    """Fork: add a shadow destination for migration testing."""
    _require_feature(ctx)

    # Validate sync
    sync = await crud.sync.get(db, id=sync_id, ctx=ctx, with_connections=True)
    if not sync:
        raise HTTPException(status_code=404, detail="Sync not found")

    # Validate destination connection
    dest_conn = await crud.connection.get(db, id=request.destination_connection_id, ctx=ctx)
    if not dest_conn:
        raise HTTPException(status_code=404, detail="Destination connection not found")

    # Check if already exists
    existing = await crud.sync_connection.get_by_sync_id(db, sync_id=sync_id)
    if any(s.connection_id == request.destination_connection_id for s in existing):
        raise HTTPException(status_code=400, detail="Destination already exists for this sync")

    # Create shadow slot
    async with UnitOfWork(db) as uow:
        slot = await crud.sync_connection.create(
            db,
            sync_id=sync_id,
            connection_id=request.destination_connection_id,
            role=DestinationRole.SHADOW,
            uow=uow,
        )

        # Update sync.destination_connection_ids to include new destination
        current_ids = list(sync.destination_connection_ids or [])
        if request.destination_connection_id not in current_ids:
            current_ids.append(request.destination_connection_id)
            await crud.sync.update(
                db,
                db_obj=sync,
                obj_in=schemas.SyncUpdate(destination_connection_ids=current_ids),
                ctx=ctx,
                uow=uow,
            )

        await uow.commit()

    ctx.logger.info(f"Created shadow destination slot {slot.id} for sync {sync_id}")

    # TODO: Kick off replay if requested
    replay_job_id = None
    if request.replay_from_arf:
        # Will be implemented when we integrate with temporal_service
        ctx.logger.info("Replay requested but not yet implemented in this endpoint")

    return schemas.ForkDestinationResponse(slot_id=slot.id, replay_job_id=replay_job_id)


@router.post("/{sync_id}/destinations/{slot_id}/switch")
async def switch_destination(
    sync_id: UUID,
    slot_id: UUID,
    db: AsyncSession = Depends(deps.get_db),
    ctx: ApiContext = Depends(deps.get_context),
) -> dict:
    """Switch: promote a shadow destination to active."""
    _require_feature(ctx)

    # Validate sync
    sync = await crud.sync.get(db, id=sync_id, ctx=ctx, with_connections=False)
    if not sync:
        raise HTTPException(status_code=404, detail="Sync not found")

    # Get all slots
    slots = await crud.sync_connection.get_by_sync_id(db, sync_id=sync_id)
    target = next((s for s in slots if s.id == slot_id), None)
    if not target:
        raise HTTPException(status_code=404, detail="Slot not found")
    if target.role != DestinationRole.SHADOW.value:
        raise HTTPException(status_code=400, detail="Can only switch shadow destinations to active")

    current_active = next((s for s in slots if s.role == DestinationRole.ACTIVE.value), None)

    async with UnitOfWork(db) as uow:
        # Demote current active
        if current_active:
            await crud.sync_connection.update_role(
                db, id=current_active.id, role=DestinationRole.DEPRECATED, uow=uow
            )

        # Promote target
        await crud.sync_connection.update_role(db, id=slot_id, role=DestinationRole.ACTIVE, uow=uow)
        await uow.commit()

    ctx.logger.info(f"Switched active destination for sync {sync_id}: {slot_id}")
    return {"status": "switched", "new_active_slot_id": str(slot_id)}


@router.post("/{sync_id}/destinations/{slot_id}/set-role")
async def set_destination_role(
    sync_id: UUID,
    slot_id: UUID,
    role: str,
    db: AsyncSession = Depends(deps.get_db),
    ctx: ApiContext = Depends(deps.get_context),
) -> dict:
    """Set the role of a destination slot (active/shadow/deprecated).

    Rules:
    - Only one destination can be active at a time
    - Promoting to active demotes current active to shadow
    - Cannot have zero active destinations (last active cannot be demoted)
    """
    _require_feature(ctx)

    # Validate role
    try:
        new_role = DestinationRole(role)
    except ValueError:
        raise HTTPException(
            status_code=400, detail=f"Invalid role: {role}. Must be active/shadow/deprecated"
        )

    # Validate sync
    sync = await crud.sync.get(db, id=sync_id, ctx=ctx, with_connections=False)
    if not sync:
        raise HTTPException(status_code=404, detail="Sync not found")

    # Get all destination slots (exclude sources which have role=NULL)
    slots = await crud.sync_connection.get_by_sync_id(db, sync_id=sync_id)
    dest_slots = [s for s in slots if s.role is not None]
    target = next((s for s in dest_slots if s.id == slot_id), None)
    if not target:
        raise HTTPException(status_code=404, detail="Destination slot not found")

    current_active = next((s for s in dest_slots if s.role == DestinationRole.ACTIVE.value), None)

    async with UnitOfWork(db) as uow:
        if new_role == DestinationRole.ACTIVE:
            # Promoting to active - demote current active to shadow
            if current_active and current_active.id != slot_id:
                await crud.sync_connection.update_role(
                    db, id=current_active.id, role=DestinationRole.SHADOW, uow=uow
                )
                ctx.logger.info(f"Demoted {current_active.id} to shadow")

        elif target.role == DestinationRole.ACTIVE.value:
            # Demoting from active - ensure there's another active destination or reject
            # Cannot leave sync without an active destination
            other_destinations = [s for s in dest_slots if s.id != slot_id]
            if not other_destinations:
                raise HTTPException(
                    status_code=400,
                    detail="Cannot demote the last active destination. Promote another destination first.",
                )

        await crud.sync_connection.update_role(db, id=slot_id, role=new_role, uow=uow)
        await uow.commit()

    ctx.logger.info(f"Set role of slot {slot_id} to {role} for sync {sync_id}")
    return {"status": "updated", "slot_id": str(slot_id), "role": role}


@router.delete("/{sync_id}/destinations/{slot_id}")
async def remove_destination(
    sync_id: UUID,
    slot_id: UUID,
    db: AsyncSession = Depends(deps.get_db),
    ctx: ApiContext = Depends(deps.get_context),
) -> dict:
    """Remove a destination slot entirely. Cannot remove active destination."""
    _require_feature(ctx)

    sync = await crud.sync.get(db, id=sync_id, ctx=ctx, with_connections=False)
    if not sync:
        raise HTTPException(status_code=404, detail="Sync not found")

    slots = await crud.sync_connection.get_by_sync_id(db, sync_id=sync_id)
    target = next((s for s in slots if s.id == slot_id), None)
    if not target:
        raise HTTPException(status_code=404, detail="Slot not found")
    # Cannot remove sources (role=NULL) or active destinations
    if target.role is None:
        raise HTTPException(status_code=400, detail="Cannot remove source connection")
    if target.role == DestinationRole.ACTIVE.value:
        raise HTTPException(
            status_code=400, detail="Cannot remove active destination - demote first"
        )

    await db.delete(target)
    await db.commit()

    ctx.logger.info(f"Removed destination slot {slot_id} from sync {sync_id}")
    return {"status": "removed", "slot_id": str(slot_id)}
