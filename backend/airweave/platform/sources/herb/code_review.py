"""HERB Code Review source — syncs pull requests from the HERB benchmark dataset."""

from __future__ import annotations

import json
import os
from datetime import datetime
from typing import TYPE_CHECKING, AsyncGenerator, Optional

from airweave.core.logging import ContextualLogger
from airweave.domains.browse_tree.types import NodeSelectionData
from airweave.domains.sources.token_providers.protocol import SourceAuthProvider
from airweave.domains.storage.file_service import FileService
from airweave.domains.syncs.cursors.cursor import SyncCursor
from airweave.platform.configs.auth import HerbAuthConfig
from airweave.platform.configs.config import HerbConfig
from airweave.platform.decorators import source
from airweave.platform.entities._base import BaseEntity, Breadcrumb
from airweave.platform.entities.herb_code_review import HerbPullRequestEntity
from airweave.platform.http_client.airweave_client import AirweaveHttpClient
from airweave.platform.sources._base import BaseSource
from airweave.schemas.source_connection import AuthenticationMethod

if TYPE_CHECKING:
    from airweave.domains.sync_pipeline.source_hash_lookup import SourceHashLookup


@source(
    name="HERB Code Review",
    short_name="herb_code_review",
    auth_methods=[AuthenticationMethod.DIRECT],
    auth_config_class=HerbAuthConfig,
    config_class=HerbConfig,
    labels=["Benchmark", "HERB"],
    internal=True,
)
class HerbCodeReviewSource(BaseSource):
    """Source that syncs pull requests from the HERB benchmark dataset."""

    def __init__(
        self,
        *,
        auth: SourceAuthProvider,
        logger: ContextualLogger,
        http_client: AirweaveHttpClient,
    ) -> None:
        """Initialize the HERB code review source."""
        super().__init__(auth=auth, logger=logger, http_client=http_client)
        self.data_dir: str = ""

    @classmethod
    async def create(
        cls,
        *,
        auth: SourceAuthProvider,
        logger: ContextualLogger,
        http_client: AirweaveHttpClient,
        config: HerbConfig,
    ) -> HerbCodeReviewSource:
        """Create a new HERB code review source instance."""
        instance = cls(auth=auth, logger=logger, http_client=http_client)
        if config:
            instance.data_dir = config.data_dir if hasattr(config, "data_dir") else ""
        return instance

    @staticmethod
    def _build_reviews_text(reviews: list) -> Optional[str]:
        """Concatenate review comments into a single text block."""
        if not reviews:
            return None
        parts = []
        for r in reviews:
            reviewer = r.get("user", {}).get("login", "unknown")
            state = r.get("state", "")
            comment = r.get("comment", "")
            submitted = r.get("submitted_at", "")
            parts.append(f"[{state}] {reviewer} ({submitted}): {comment}")
        return "\n".join(parts)

    async def generate_entities(
        self,
        *,
        cursor: SyncCursor | None = None,
        files: FileService | None = None,
        node_selections: list[NodeSelectionData] | None = None,
        source_hash_lookup: SourceHashLookup | None = None,
    ) -> AsyncGenerator[BaseEntity, None]:
        """Generate HerbPullRequestEntity instances from HERB product files."""
        products_dir = os.path.join(self.data_dir, "products")

        for fname in sorted(os.listdir(products_dir)):
            if not fname.endswith(".json"):
                continue

            product_name = fname.replace(".json", "")
            with open(os.path.join(products_dir, fname)) as f:
                data = json.load(f)

            for pr in data.get("prs", []):
                # Parse creation timestamp
                created_str = pr.get("created_at", "")
                try:
                    pr_created_at = datetime.fromisoformat(created_str)
                except (ValueError, TypeError):
                    pr_created_at = None

                yield HerbPullRequestEntity(
                    pr_id=pr["id"],
                    title=pr.get("title", ""),
                    summary=pr.get("summary", ""),
                    pr_link=pr.get("link", ""),
                    state=pr.get("state", ""),
                    merged=str(pr.get("merged", "")),
                    number=str(pr.get("number", "")),
                    author_login=pr.get("user", {}).get("login", "unknown"),
                    reviews_text=self._build_reviews_text(pr.get("reviews", [])),
                    pr_created_at=pr_created_at,
                    product_name=product_name,
                    breadcrumbs=[
                        Breadcrumb(
                            entity_id=product_name,
                            name=product_name,
                            entity_type="HerbProduct",
                        ),
                    ],
                )

    async def validate(self) -> None:
        """Validate that the HERB data directory exists and contains product files."""
        products_dir = os.path.join(self.data_dir, "products")
        if not (
            os.path.isdir(products_dir)
            and any(f.endswith(".json") for f in os.listdir(products_dir))
        ):
            raise ValueError(f"HERB data dir '{products_dir}' missing or has no product JSON files")
