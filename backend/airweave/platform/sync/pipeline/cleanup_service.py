"""Cleanup service for temporary files during sync."""

import os
from typing import TYPE_CHECKING, Any, Dict, List

from airweave.platform.entities._base import FileEntity
from airweave.platform.sync.exceptions import SyncFailureError

if TYPE_CHECKING:
    from airweave.platform.contexts import SyncContext
    from airweave.platform.contexts.runtime import SyncRuntime


class CleanupService:
    """Service for cleaning up temporary files during sync.

    Handles:
    - Progressive temp file cleanup (after each batch)
    - Final temp directory cleanup (safety net in finally block)

    Note: Orphaned entity cleanup is handled by handlers via dispatcher.
    """

    async def cleanup_processed_files(
        self,
        partitions: Dict[str, Any],
        sync_context: "SyncContext",
    ) -> None:
        """Delete temporary files after batch processing (progressive cleanup).

        Called after entities are persisted to destinations and database.
        Raises SyncFailureError if deletion fails to prevent disk space issues.

        Args:
            partitions: Entity partitions from action determination
            sync_context: Sync context with logger
        """
        entities_to_clean = partitions["inserts"] + partitions["updates"] + partitions["keeps"]
        cleaned_count = 0
        failed_deletions: List[str] = []

        for entity in entities_to_clean:
            # Only clean up file entities
            if not isinstance(entity, FileEntity):
                continue

            # FileEntity without local_path is a programming error
            if not hasattr(entity, "local_path") or not entity.local_path:
                raise SyncFailureError(
                    f"FileEntity {entity.__class__.__name__}[{entity.entity_id}] "
                    f"has no local_path after processing. This indicates download/save failed "
                    f"but entity was not filtered out."
                )

            local_path = entity.local_path

            try:
                if os.path.exists(local_path):
                    os.remove(local_path)

                    if os.path.exists(local_path):
                        failed_deletions.append(local_path)
                        sync_context.logger.error(f"Failed to delete temp file: {local_path}")
                    else:
                        cleaned_count += 1
                        sync_context.logger.debug(f"Deleted temp file: {local_path}")

            except Exception as e:
                failed_deletions.append(local_path)
                sync_context.logger.error(f"Error deleting temp file {local_path}: {e}")

        if cleaned_count > 0:
            sync_context.logger.debug(f"Progressive cleanup: deleted {cleaned_count} temp files")

        if failed_deletions:
            raise SyncFailureError(
                f"Failed to delete {len(failed_deletions)} temp files. "
                f"This can cause pod eviction. Files: {failed_deletions[:5]}"
            )

    async def cleanup_temp_files(
        self,
        sync_context: "SyncContext",
        runtime: "SyncRuntime",
    ) -> None:
        """Remove entire sync_job_id directory (final cleanup safety net).

        Called in orchestrator's finally block to ensure cleanup happens even if
        pipeline fails. Removes entire /tmp/airweave/processing/{sync_job_id}/ directory.

        Args:
            sync_context: Sync context with source and logger
            runtime: Sync runtime with live services

        Note:
            Some sources don't download files (e.g., Airtable, Jira without attachments).
            For these sources, file_downloader won't be set, which is expected.
        """
        try:
            if not hasattr(runtime.source, "file_downloader"):
                sync_context.logger.debug(
                    "Source has no file downloader (API-only source), skipping temp cleanup"
                )
                return

            downloader = runtime.source.file_downloader
            if downloader is None:
                sync_context.logger.debug("File downloader not initialized, skipping temp cleanup")
                return

            await downloader.cleanup_sync_directory(sync_context.logger)

        except Exception as e:
            sync_context.logger.warning(
                f"Final temp file cleanup failed (non-fatal): {e}", exc_info=True
            )


# Singleton instance
cleanup_service = CleanupService()
