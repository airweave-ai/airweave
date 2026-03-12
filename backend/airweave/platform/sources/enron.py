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

import os
import re
from typing import Any, AsyncGenerator, Dict, List, Optional, Union

import pyarrow.parquet as pq

from airweave.platform.configs.auth import EnronAuthConfig
from airweave.platform.configs.config import EnronConfig
from airweave.platform.decorators import source
from airweave.platform.entities._base import BaseEntity
from airweave.platform.entities.enron import EnronEmailEntity
from airweave.platform.sources._base import BaseSource
from airweave.schemas.source_connection import AuthenticationMethod


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

    def __init__(self):
        """Initialize the Enron source."""
        super().__init__()
        self.data_dir: str = ""

    @classmethod
    async def create(
        cls,
        credentials: Optional[Union[Dict[str, Any], EnronAuthConfig]] = None,
        config: Optional[Union[Dict[str, Any], EnronConfig]] = None,
    ) -> "EnronSource":
        """Create a new Enron source instance."""
        instance = cls()
        if config:
            instance.data_dir = (
                config.get("data_dir", "") if isinstance(config, dict) else config.data_dir
            )
        return instance

    async def generate_entities(self) -> AsyncGenerator[BaseEntity, None]:
        """Read parquet files and yield EnronEmailEntity instances."""
        data_dir = os.path.join(self.data_dir, "data")
        parquet_files = sorted(
            f for f in os.listdir(data_dir) if f.endswith(".parquet")
        )

        self.logger.info(
            f"Reading {len(parquet_files)} parquet files from {data_dir}"
        )

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

    async def validate(self) -> bool:
        """Validate that the data directory contains parquet files."""
        data_dir = os.path.join(self.data_dir, "data")
        if not os.path.isdir(data_dir):
            return False
        return any(f.endswith(".parquet") for f in os.listdir(data_dir))
