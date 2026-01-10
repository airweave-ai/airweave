"""Layer resolution for sync configuration.

Resolution order (lowest → highest priority):
1. Schema defaults (SyncConfig field defaults)
2. Environment (SYNC_CONFIG__* env vars, handled by Pydantic Settings)
3. Collection (collection.sync_config_json)
4. Sync (sync.sync_config_json)
5. SyncJob (sync_job.execution_config_json)
"""

from typing import Optional

from airweave.platform.sync.config.base import SyncConfig


class SyncConfigBuilder:
    """Builds layered configuration into a final SyncConfig."""

    @classmethod
    def build(
        cls,
        collection_overrides: Optional[SyncConfig] = None,
        sync_overrides: Optional[SyncConfig] = None,
        job_overrides: Optional[SyncConfig] = None,
    ) -> SyncConfig:
        """Build final config from all layers.

        Args:
            collection_overrides: Overrides from collection (validate with SyncConfig(**json))
            sync_overrides: Overrides from sync (validate with SyncConfig(**json))
            job_overrides: Overrides from sync_job (validate with SyncConfig(**json))

        Returns:
            Fully resolved SyncConfig with all layers applied.
        """
        # Layer 1 + 2: Schema defaults + env vars (Pydantic Settings handles this)
        config = SyncConfig()

        # Layer 3-5: Apply overrides in order
        for overrides in [collection_overrides, sync_overrides, job_overrides]:
            if overrides:
                config = config.merge_with(overrides.model_dump(exclude_unset=True))

        return config
