"""HERB Resources source — syncs shared URLs/bookmarks from the HERB benchmark dataset."""

from __future__ import annotations

import json
import os
from typing import TYPE_CHECKING, AsyncGenerator

from airweave.core.logging import ContextualLogger
from airweave.domains.browse_tree.types import NodeSelectionData
from airweave.domains.sources.token_providers.protocol import SourceAuthProvider
from airweave.domains.storage.file_service import FileService
from airweave.domains.syncs.cursors.cursor import SyncCursor
from airweave.platform.configs.auth import HerbAuthConfig
from airweave.platform.configs.config import HerbConfig
from airweave.platform.decorators import source
from airweave.platform.entities._base import BaseEntity, Breadcrumb
from airweave.platform.entities.herb_resources import HerbResourceEntity
from airweave.platform.http_client.airweave_client import AirweaveHttpClient
from airweave.platform.sources._base import BaseSource
from airweave.schemas.source_connection import AuthenticationMethod

if TYPE_CHECKING:
    from airweave.domains.sync_pipeline.source_hash_lookup import SourceHashLookup


@source(
    name="HERB Resources",
    short_name="herb_resources",
    auth_methods=[AuthenticationMethod.DIRECT],
    auth_config_class=HerbAuthConfig,
    config_class=HerbConfig,
    labels=["Benchmark", "HERB"],
    internal=True,
)
class HerbResourcesSource(BaseSource):
    """Source that syncs shared URLs/bookmarks from the HERB benchmark dataset."""

    def __init__(
        self,
        *,
        auth: SourceAuthProvider,
        logger: ContextualLogger,
        http_client: AirweaveHttpClient,
    ) -> None:
        """Initialize the HERB resources source."""
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
    ) -> HerbResourcesSource:
        """Create a new HERB resources source instance."""
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
        """Generate HerbResourceEntity instances from HERB product files."""
        products_dir = os.path.join(self.data_dir, "products")

        for fname in sorted(os.listdir(products_dir)):
            if not fname.endswith(".json"):
                continue

            product_name = fname.replace(".json", "")
            with open(os.path.join(products_dir, fname)) as f:
                data = json.load(f)

            for url_item in data.get("urls", []):
                yield HerbResourceEntity(
                    resource_id=url_item["id"],
                    description=url_item.get("description", ""),
                    link=url_item.get("link", ""),
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
