"""HERB Resources source — syncs shared URLs/bookmarks from the HERB benchmark dataset."""

import json
import os
from typing import Any, AsyncGenerator, Dict, Optional, Union

from airweave.platform.configs.auth import HerbAuthConfig
from airweave.platform.configs.config import HerbConfig
from airweave.platform.decorators import source
from airweave.platform.entities._base import BaseEntity, Breadcrumb
from airweave.platform.entities.herb import HerbResourceEntity
from airweave.platform.sources._base import BaseSource
from airweave.schemas.source_connection import AuthenticationMethod


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

    def __init__(self):
        """Initialize the HERB resources source."""
        super().__init__()
        self.data_dir: str = ""

    @classmethod
    async def create(
        cls,
        credentials: Optional[Union[Dict[str, Any], HerbAuthConfig]] = None,
        config: Optional[Dict[str, Any]] = None,
    ) -> "HerbResourcesSource":
        """Create a new HERB resources source instance."""
        instance = cls()
        if config:
            instance.data_dir = (
                config.get("data_dir", "") if isinstance(config, dict) else config.data_dir
            )
        return instance

    async def generate_entities(self) -> AsyncGenerator[BaseEntity, None]:
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

    async def validate(self) -> bool:
        """Validate that the HERB data directory exists and contains product files."""
        products_dir = os.path.join(self.data_dir, "products")
        return os.path.isdir(products_dir) and any(
            f.endswith(".json") for f in os.listdir(products_dir)
        )
