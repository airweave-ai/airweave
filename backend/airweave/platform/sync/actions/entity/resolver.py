"""Action resolver for entity processing.

Resolves entities to their appropriate action (INSERT/UPDATE/DELETE/KEEP)
by comparing content hashes against stored values in the database.
"""

import time
from typing import TYPE_CHECKING, Dict, List, Optional, Tuple
from uuid import UUID

from airweave import crud, models
from airweave.db.session import get_db_context
from airweave.platform.entities._base import BaseEntity, DeletionEntity
from airweave.platform.sync.actions.entity.types import (
    EntityActionBatch,
    EntityDeleteAction,
    EntityInsertAction,
    EntityKeepAction,
    EntityUpdateAction,
)
from airweave.platform.sync.exceptions import SyncFailureError

if TYPE_CHECKING:
    from airweave.platform.contexts import SyncContext


class EntityActionResolver:
    """Resolves entities to action objects (INSERT/UPDATE/DELETE/KEEP).

    Compares entity hashes against stored values in the database to determine
    what operation is needed for each entity.
    """

    def __init__(self, entity_map: Dict[type, UUID]):
        """Initialize the action resolver.

        Args:
            entity_map: Mapping of entity class to entity_definition_id
        """
        self.entity_map = entity_map

    # -------------------------------------------------------------------------
    # Public API
    # -------------------------------------------------------------------------

    async def resolve(
        self,
        entities: List[BaseEntity],
        sync_context: "SyncContext",
    ) -> EntityActionBatch:
        """Resolve entities to their appropriate actions.

        Args:
            entities: Entities to resolve (must have hash set in metadata)
            sync_context: Sync context with logger

        Returns:
            EntityActionBatch containing all resolved actions

        Raises:
            SyncFailureError: If entity type not found in entity_map or missing hash
        """
        # Check if skip_hash_comparison is enabled
        if (
            sync_context.execution_config
            and sync_context.execution_config.behavior
            and sync_context.execution_config.behavior.skip_hash_comparison
        ):
            sync_context.logger.info(
                "skip_hash_comparison enabled: Forcing all entities as INSERT actions"
            )
            return self._force_all_inserts(entities, sync_context)

        # Step 1: Separate deletions from non-deletions
        delete_entities, non_delete_entities = self._separate_deletions(entities)

        # Step 2: Build entity requests for DB lookup
        all_entities = non_delete_entities + delete_entities
        entity_requests = self._build_entity_requests(all_entities, sync_context)

        # Step 3: Fetch existing entities from database
        existing_map = await self._fetch_existing_entities(entity_requests, sync_context)

        # Step 4: Create actions for each entity
        batch = self._create_actions(
            non_delete_entities,
            delete_entities,
            existing_map,
            sync_context,
        )

        # Log summary
        sync_context.logger.debug(f"Action resolution: {batch.summary()}")

        return batch

    def resolve_entity_definition_id(self, entity: BaseEntity) -> Optional[UUID]:
        """Resolve entity definition ID with polymorphic fallback.

        Args:
            entity: Entity to resolve definition ID for

        Returns:
            Entity definition UUID, or None if not found
        """
        entity_class = entity.__class__

        # Handle DeletionEntity - resolve to target class
        if issubclass(entity_class, DeletionEntity):
            target_class = getattr(entity_class, "deletes_entity_class", None)
            if target_class:
                entity_class = target_class

        # Try direct lookup
        return self.entity_map.get(entity_class)

    # -------------------------------------------------------------------------
    # Internal Methods
    # -------------------------------------------------------------------------

    def _separate_deletions(
        self, entities: List[BaseEntity]
    ) -> Tuple[List[BaseEntity], List[BaseEntity]]:
        """Separate deletion entities from non-deletions.

        Args:
            entities: All entities to process

        Returns:
            Tuple of (delete_entities, non_delete_entities)
        """
        delete_entities = []
        non_delete_entities = []

        for entity in entities:
            if isinstance(entity, DeletionEntity) and entity.deletion_status == "removed":
                delete_entities.append(entity)
            else:
                non_delete_entities.append(entity)

        return delete_entities, non_delete_entities

    def _build_entity_requests(
        self,
        entities: List[BaseEntity],
        sync_context: "SyncContext",
    ) -> List[Tuple[str, UUID]]:
        """Build entity requests for database lookup.

        Args:
            entities: Entities to build requests for
            sync_context: Sync context for logging

        Returns:
            List of (entity_id, entity_definition_id) tuples

        Raises:
            SyncFailureError: If entity type not found in entity_map
        """
        entity_requests = []

        for entity in entities:
            entity_definition_id = self.resolve_entity_definition_id(entity)
            if entity_definition_id is None:
                sync_context.logger.error(
                    f"Entity type {entity.__class__.__name__} not found in entity_map"
                )
                raise SyncFailureError(f"Entity type {entity.__class__.__name__} not in entity_map")
            entity_requests.append((entity.entity_id, entity_definition_id))

        return entity_requests

    async def _fetch_existing_entities(
        self,
        entity_requests: List[Tuple[str, UUID]],
        sync_context: "SyncContext",
    ) -> Dict[Tuple[str, UUID], models.Entity]:
        """Bulk fetch existing entity records from database.

        Args:
            entity_requests: List of (entity_id, entity_definition_id) tuples
            sync_context: Sync context with logger

        Returns:
            Dict mapping (entity_id, entity_definition_id) -> Entity model

        Raises:
            SyncFailureError: If database lookup fails
        """
        if not entity_requests:
            return {}

        try:
            lookup_start = time.time()
            num_chunks = (len(entity_requests) + 999) // 1000
            sync_context.logger.debug(
                f"Bulk entity lookup for {len(entity_requests)} entities ({num_chunks} chunks)..."
            )

            async with get_db_context() as db:
                existing_map = await crud.entity.bulk_get_by_entity_sync_and_definition(
                    db,
                    sync_id=sync_context.sync.id,
                    entity_requests=entity_requests,
                )

            lookup_duration = time.time() - lookup_start
            sync_context.logger.debug(
                f"Bulk lookup complete in {lookup_duration:.2f}s - "
                f"found {len(existing_map)}/{len(entity_requests)} existing"
            )

            return existing_map

        except Exception as e:
            sync_context.logger.error(f"Failed to fetch existing entities: {e}")
            raise SyncFailureError(f"Failed to fetch existing entities: {e}") from e

    def _create_actions(
        self,
        non_delete_entities: List[BaseEntity],
        delete_entities: List[BaseEntity],
        existing_map: Dict[Tuple[str, UUID], models.Entity],
        sync_context: "SyncContext",
    ) -> EntityActionBatch:
        """Create action objects for all entities.

        Args:
            non_delete_entities: Entities that are not deletions
            delete_entities: DeletionEntity instances
            existing_map: Map of existing DB records
            sync_context: Sync context for error handling

        Returns:
            EntityActionBatch with all resolved actions

        Raises:
            SyncFailureError: If entity has no hash or type not in entity_map
        """
        inserts: List[EntityInsertAction] = []
        updates: List[EntityUpdateAction] = []
        keeps: List[EntityKeepAction] = []
        deletes: List[EntityDeleteAction] = []

        # Process non-delete entities
        for entity in non_delete_entities:
            action = self._resolve_non_delete_action(entity, existing_map, sync_context)
            if isinstance(action, EntityInsertAction):
                inserts.append(action)
            elif isinstance(action, EntityUpdateAction):
                updates.append(action)
            elif isinstance(action, EntityKeepAction):
                keeps.append(action)

        # Process delete entities
        for entity in delete_entities:
            action = self._create_delete_action(entity, existing_map, sync_context)
            deletes.append(action)

        return EntityActionBatch(
            inserts=inserts,
            updates=updates,
            keeps=keeps,
            deletes=deletes,
            existing_map=existing_map,
        )

    def _resolve_non_delete_action(
        self,
        entity: BaseEntity,
        existing_map: Dict[Tuple[str, UUID], models.Entity],
        sync_context: "SyncContext",
    ) -> EntityInsertAction | EntityUpdateAction | EntityKeepAction:
        """Resolve a non-delete entity to its action type.

        Args:
            entity: Entity to resolve
            existing_map: Map of existing DB records
            sync_context: Sync context

        Returns:
            EntityInsertAction, EntityUpdateAction, or EntityKeepAction

        Raises:
            SyncFailureError: If entity has no hash or type not in entity_map
        """
        # Validate hash is set
        if not entity.airweave_system_metadata or not entity.airweave_system_metadata.hash:
            raise SyncFailureError(
                f"PROGRAMMING ERROR: Entity {entity.__class__.__name__}"
                f"[{entity.entity_id}] has no hash. "
                f"Hash should have been set during hash computation."
            )

        entity_hash = entity.airweave_system_metadata.hash

        # Get entity_definition_id
        entity_definition_id = self.resolve_entity_definition_id(entity)
        if entity_definition_id is None:
            raise SyncFailureError(f"Entity type {entity.__class__.__name__} not in entity_map")

        # Lookup existing DB record
        db_key = (entity.entity_id, entity_definition_id)
        db_row = existing_map.get(db_key)

        # Determine action based on DB state and hash
        if db_row is None:
            # New entity - INSERT
            return EntityInsertAction(
                entity=entity,
                entity_definition_id=entity_definition_id,
            )
        elif db_row.hash != entity_hash:
            # Hash changed - UPDATE
            return EntityUpdateAction(
                entity=entity,
                entity_definition_id=entity_definition_id,
                db_id=db_row.id,
            )
        else:
            # Hash unchanged - KEEP
            return EntityKeepAction(
                entity=entity,
                entity_definition_id=entity_definition_id,
            )

    def _create_delete_action(
        self,
        entity: BaseEntity,
        existing_map: Dict[Tuple[str, UUID], models.Entity],
        sync_context: "SyncContext",
    ) -> EntityDeleteAction:
        """Create a delete action for a DeletionEntity.

        Args:
            entity: DeletionEntity to process
            existing_map: Map of existing DB records
            sync_context: Sync context

        Returns:
            EntityDeleteAction with db_id if entity exists in DB

        Raises:
            SyncFailureError: If entity type not in entity_map
        """
        entity_definition_id = self.resolve_entity_definition_id(entity)
        if entity_definition_id is None:
            raise SyncFailureError(f"Entity type {entity.__class__.__name__} not in entity_map")

        # Check if entity exists in DB
        db_key = (entity.entity_id, entity_definition_id)
        db_row = existing_map.get(db_key)

        return EntityDeleteAction(
            entity=entity,
            entity_definition_id=entity_definition_id,
            db_id=db_row.id if db_row else None,
        )

    def _force_all_inserts(
        self,
        entities: List[BaseEntity],
        sync_context: "SyncContext",
    ) -> EntityActionBatch:
        """Force all entities as INSERT actions (skip hash comparison).

        Used for ARF replay or when execution_config.behavior.skip_hash_comparison is True.

        Args:
            entities: Entities to process
            sync_context: Sync context

        Returns:
            EntityActionBatch with all entities as inserts
        """
        inserts: List[EntityInsertAction] = []
        deletes: List[EntityDeleteAction] = []

        for entity in entities:
            if isinstance(entity, DeletionEntity):
                deletes.append(self._create_delete_action(entity, {}, sync_context))
            else:
                entity_definition_id = self.resolve_entity_definition_id(entity)
                if not entity_definition_id:
                    raise SyncFailureError(
                        f"Entity type {entity.__class__.__name__} not in entity_map"
                    )
                inserts.append(
                    EntityInsertAction(entity=entity, entity_definition_id=entity_definition_id)
                )

        return EntityActionBatch(
            inserts=inserts,
            updates=[],
            keeps=[],
            deletes=deletes,
        )
