"""HERB Code Review source — syncs pull requests from the HERB benchmark dataset."""

import json
import os
from datetime import datetime
from typing import Any, AsyncGenerator, Dict, Optional, Union

from airweave.platform.configs.auth import HerbAuthConfig
from airweave.platform.configs.config import HerbConfig
from airweave.platform.decorators import source
from airweave.platform.entities._base import BaseEntity, Breadcrumb
from airweave.platform.entities.herb_code_review import HerbPullRequestEntity
from airweave.platform.sources._base import BaseSource
from airweave.schemas.source_connection import AuthenticationMethod


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

    def __init__(self):
        """Initialize the HERB code review source."""
        super().__init__()
        self.data_dir: str = ""

    @classmethod
    async def create(
        cls,
        credentials: Optional[Union[Dict[str, Any], HerbAuthConfig]] = None,
        config: Optional[Dict[str, Any]] = None,
    ) -> "HerbCodeReviewSource":
        """Create a new HERB code review source instance."""
        instance = cls()
        if config:
            instance.data_dir = (
                config.get("data_dir", "") if isinstance(config, dict) else config.data_dir
            )
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

    async def generate_entities(self) -> AsyncGenerator[BaseEntity, None]:
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

    async def validate(self) -> bool:
        """Validate that the HERB data directory exists and contains product files."""
        products_dir = os.path.join(self.data_dir, "products")
        return os.path.isdir(products_dir) and any(
            f.endswith(".json") for f in os.listdir(products_dir)
        )
