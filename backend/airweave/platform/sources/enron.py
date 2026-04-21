"""Enron Email source — syncs the HuggingFace Enron email dataset into Airweave.

Reads pre-processed parquet files from ``corbt/enron-emails`` and yields flat
EnronEmailEntity instances with no breadcrumbs. This follows the HERB benchmark
pattern: static downloaded data, BaseEntity, no file-download pipeline.

Expected data directory layout (HuggingFace snapshot_download output):
    {data_dir}/
    └── data/
        ├── train-00000-of-00003.parquet
        ├── train-00001-of-00003.parquet
        └── train-00002-of-00003.parquet
"""

from __future__ import annotations

import os
import re
from typing import TYPE_CHECKING, AsyncGenerator, List

from airweave.core.logging import ContextualLogger
from airweave.domains.browse_tree.types import NodeSelectionData
from airweave.domains.sources.token_providers.protocol import SourceAuthProvider
from airweave.domains.storage.file_service import FileService
from airweave.domains.syncs.cursors.cursor import SyncCursor
from airweave.platform.configs.auth import EnronAuthConfig
from airweave.platform.configs.config import EnronConfig
from airweave.platform.decorators import source
from airweave.platform.entities._base import BaseEntity
from airweave.platform.entities.enron import EnronEmailEntity
from airweave.platform.http_client.airweave_client import AirweaveHttpClient
from airweave.platform.sources._base import BaseSource
from airweave.schemas.source_connection import AuthenticationMethod

if TYPE_CHECKING:
    from airweave.domains.sync_pipeline.source_hash_lookup import SourceHashLookup

_CTRL_CHAR_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def _sanitize(value: str) -> str:
    """Strip control characters that Vespa rejects."""
    return _CTRL_CHAR_RE.sub("", value)


def _clean_list(raw: List[str]) -> List[str]:
    """Remove empty strings from address lists (parquet stores [''] for empty)."""
    return [addr for addr in raw if addr and addr.strip()]


@source(
    name="Enron Email Dataset",
    short_name="enron",
    auth_methods=[AuthenticationMethod.DIRECT],
    auth_config_class=EnronAuthConfig,
    config_class=EnronConfig,
    labels=["Benchmark", "Email"],
    internal=True,
)
class EnronSource(BaseSource):
    """Source that reads parquet files from the Enron email dataset.

    Each email is yielded as a flat EnronEmailEntity with no breadcrumbs.
    All fields are preserved exactly as-is to ensure eval ground-truth
    message_ids match without transformation.
    """

    def __init__(
        self,
        *,
        auth: SourceAuthProvider,
        logger: ContextualLogger,
        http_client: AirweaveHttpClient,
    ) -> None:
        """Initialize the Enron source."""
        super().__init__(auth=auth, logger=logger, http_client=http_client)
        self.data_dir: str = ""

    @classmethod
    async def create(
        cls,
        *,
        auth: SourceAuthProvider,
        logger: ContextualLogger,
        http_client: AirweaveHttpClient,
        config: EnronConfig,  # type: ignore[override]
    ) -> EnronSource:
        """Create a new Enron source instance."""
        instance = cls(auth=auth, logger=logger, http_client=http_client)
        if config:
            instance.data_dir = config.data_dir if hasattr(config, "data_dir") else ""
        return instance

    async def generate_entities(
        self,
        *,
        cursor: SyncCursor | None = None,
        files: FileService | None = None,
        node_selections: list[NodeSelectionData] | None = None,
        source_hash_lookup: SourceHashLookup | None = None,
    ) -> AsyncGenerator[BaseEntity, None]:
        """Read parquet files and yield EnronEmailEntity instances."""
        # Lazy import: pyarrow is a heavy optional dependency only needed by this
        # benchmark source and is not guaranteed to be in the Docker image.
        import pyarrow.parquet as pq  # type: ignore[import-untyped]

        data_dir = os.path.join(self.data_dir, "data")
        parquet_files = sorted(f for f in os.listdir(data_dir) if f.endswith(".parquet"))

        self.logger.info(f"Reading {len(parquet_files)} parquet files from {data_dir}")

        total = 0
        for fname in parquet_files:
            table = pq.read_table(os.path.join(data_dir, fname))

            for batch in table.to_batches(max_chunksize=1000):
                rows = batch.to_pydict()
                n_rows = len(rows["message_id"])

                for i in range(n_rows):
                    yield EnronEmailEntity(
                        message_id=rows["message_id"][i],
                        subject=_sanitize(rows["subject"][i] or ""),
                        body=_sanitize(rows["body"][i] or ""),
                        sender=rows["from"][i] or "",
                        to=_clean_list(rows["to"][i]),
                        cc=_clean_list(rows["cc"][i]),
                        bcc=_clean_list(rows["bcc"][i]),
                        sent_at=rows["date"][i],
                        breadcrumbs=[],
                    )

                    total += 1
                    if total % 50_000 == 0:
                        self.logger.info(f"Yielded {total:,} emails so far ...")

        self.logger.info(f"Complete: {total:,} emails yielded")

    async def validate(self) -> None:
        """Validate that the data directory contains parquet files."""
        data_dir = os.path.join(self.data_dir, "data")
        if not os.path.isdir(data_dir):
            raise ValueError(f"Enron data directory '{data_dir}' does not exist")
        if not any(f.endswith(".parquet") for f in os.listdir(data_dir)):
            raise ValueError(f"Enron data directory '{data_dir}' contains no parquet files")
