"""Module for data synchronization."""

from sqlalchemy.ext.asyncio import AsyncSession

from app import crud, schemas
from app.core import credentials
from app.core.exceptions import NotFoundException
from app.db.session import get_db_context
from app.platform.auth.schemas import AuthType
from app.platform.auth.services import oauth2_service
from app.platform.chunks._base import BaseChunk
from app.platform.destinations.weaviate import WeaviateDestination
from app.platform.embedding_models.local_text2vec import LocalText2Vec
from app.platform.locator import resource_locator
from app.platform.sync.context import SyncContext


class SyncService:
    """Main service for data synchronization."""

    async def create(
        self, db: AsyncSession, sync: schemas.SyncCreate, current_user: schemas.User
    ) -> schemas.Sync:
        """Create a new sync."""
        return await crud.sync.create(db=db, obj_in=sync, current_user=current_user)

    async def run(
        self,
        sync: schemas.Sync,
        sync_job: schemas.SyncJob,
        current_user: schemas.User,
    ) -> schemas.Sync:
        """Run a sync.

        This method:
        1. Creates a sync context
        2. Processes chunks from the source
        3. Handles updates, inserts, and deletions in both DB and destination
        4. Uses batch processing for efficiency
        """
        async with get_db_context() as db:
            sync_context = await self.create_sync_context(db, sync, sync_job, current_user)

            # TODO: Implement microbatch processing

            # Process chunks from source
            async for chunk in sync_context.source.generate_chunks():

                # Enrich chunk with sync context information
                chunk = await self._enrich_chunk(chunk, sync_context)

                # Calculate hash for deduplication
                chunk_hash = chunk.hash()

                # Check if chunk exists in DB
                db_chunk = await crud.chunk.get_by_entity_id(
                    db, entity_id=chunk.entity_id, sync_id=sync.id
                )

                if db_chunk:
                    if db_chunk.hash == chunk_hash:
                        # No changes, update sync_job_id
                        await crud.chunk.update_job_id(db, db_obj=db_chunk, sync_job_id=sync_job.id)
                    else:
                        # Content changed, update both DB and destination
                        await crud.chunk.update(
                            db, db_obj=db_chunk, obj_in=chunk, organization_id=sync.organization_id
                        )
                        await sync_context.destination.delete(db_chunk.id)
                        await sync_context.destination.insert(chunk)
                else:
                    # New chunk, insert into DB and buffer for destination
                    chunk_schema = schemas.ChunkCreate(
                        sync_id=sync.id,
                        sync_job_id=sync_job.id,
                        entity_id=chunk.entity_id,
                        hash=chunk_hash,
                    )
                    db_chunk = await crud.chunk.create(
                        db,
                        obj_in=chunk_schema,
                        organization_id=sync.organization_id,
                    )
                    chunk.db_chunk_id = db_chunk.id
                    await sync_context.destination.insert(chunk)

            # Handle deletions - remove outdated chunks
            outdated_chunks = await crud.chunk.get_all_outdated(db, sync=sync)
            if outdated_chunks:
                db_chunk_ids = [chunk.entity_id for chunk in outdated_chunks]
                # Remove from destination
                for db_chunk_id in db_chunk_ids:
                    await sync_context.destination.delete(db_chunk_id)
                    # Remove from database
                    await crud.chunk.remove(
                        db, id=db_chunk_id, organization_id=current_user.organization_id
                    )

            return sync

    async def _enrich_chunk(
        self,
        chunk: BaseChunk,
        sync_context: SyncContext,
    ) -> BaseChunk:
        """Enrich a chunk with information from the sync context."""
        chunk.source_name = sync_context.source._name
        chunk.sync_id = sync_context.sync.id
        chunk.sync_job_id = sync_context.sync_job.id
        chunk.sync_metadata = sync_context.sync.sync_metadata
        if sync_context.sync.white_label_id:
            chunk.white_label_user_identifier = sync_context.sync.white_label_user_identifier
            chunk.white_label_id = sync_context.sync.white_label_id
            chunk.white_label_name = sync_context.white_label.name

        return chunk

    async def create_sync_context(
        self,
        db: AsyncSession,
        sync: schemas.Sync,
        sync_job: schemas.SyncJob,
        current_user: schemas.User,
    ) -> SyncContext:
        """Create a sync context."""
        source_connection = await crud.connection.get(db, sync.source_connection_id, current_user)
        if not source_connection:
            raise NotFoundException("Source connection not found")
        source_model = await crud.source.get(db, source_connection.source_id)

        if not source_model:
            raise NotFoundException("Source not found")

        source_integration_credential = await crud.integration_credential.get(
            db, source_connection.integration_credential_id, current_user
        )

        if not source_integration_credential:
            raise NotFoundException("Source integration credential not found")

        source_class = resource_locator.get_source(source_model)
        decrypted_credential = credentials.decrypt(
            source_integration_credential.encrypted_credentials
        )

        if (
            source_model.auth_type == AuthType.oauth2_with_refresh
            or source_model.auth_type == AuthType.oauth2_with_refresh_rotating
        ):
            oauth2_response = await oauth2_service.refresh_access_token(
                db, source_model.short_name, current_user, source_connection.id
            )
            access_token = oauth2_response.access_token
            source_instance = await source_class.create(access_token)
        else:
            # in case of API key auth / basic auth / etc.
            auth_config = resource_locator.get_auth_config(source_model.auth_config_class)
            source_credentials = auth_config.model_validate(decrypted_credential)
            source_instance = await source_class.create(source_credentials)

        if not sync.embedding_model_connection_id:
            embedding_model = LocalText2Vec()

        if not sync.destination_connection_id:
            destination = await WeaviateDestination.create(sync.id, embedding_model)

        sync_context = SyncContext(source_instance, destination, embedding_model, sync, sync_job)

        if sync.white_label_id:
            white_label = await crud.white_label.get(db, sync.white_label_id, current_user)
            sync_context.white_label = white_label
        return sync_context


sync_service = SyncService()
