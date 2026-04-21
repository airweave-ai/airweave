"""HERB Documents source — syncs documents from the HERB benchmark dataset."""

from __future__ import annotations

import json
import os
from datetime import datetime
from typing import TYPE_CHECKING, AsyncGenerator, Dict

from airweave.core.logging import ContextualLogger
from airweave.domains.browse_tree.types import NodeSelectionData
from airweave.domains.sources.token_providers.protocol import SourceAuthProvider
from airweave.domains.storage.file_service import FileService
from airweave.domains.syncs.cursors.cursor import SyncCursor
from airweave.platform.configs.auth import HerbAuthConfig
from airweave.platform.configs.config import HerbConfig
from airweave.platform.decorators import source
from airweave.platform.entities._base import BaseEntity, Breadcrumb
from airweave.platform.entities.herb_documents import HerbDocumentEntity
from airweave.platform.http_client.airweave_client import AirweaveHttpClient
from airweave.platform.sources._base import BaseSource
from airweave.schemas.source_connection import AuthenticationMethod

if TYPE_CHECKING:
    from airweave.domains.sync_pipeline.source_hash_lookup import SourceHashLookup


@source(
    name="HERB Documents",
    short_name="herb_documents",
    auth_methods=[AuthenticationMethod.DIRECT],
    auth_config_class=HerbAuthConfig,
    config_class=HerbConfig,
    labels=["Benchmark", "HERB"],
    internal=True,
)
class HerbDocumentsSource(BaseSource):
    """Source that syncs documents (PRDs, vision docs, etc.) from the HERB benchmark dataset."""

    def __init__(
        self,
        *,
        auth: SourceAuthProvider,
        logger: ContextualLogger,
        http_client: AirweaveHttpClient,
    ) -> None:
        """Initialize the HERB documents source."""
        super().__init__(auth=auth, logger=logger, http_client=http_client)
        self.data_dir: str = ""
        self._employees: Dict[str, Dict] = {}

    @classmethod
    async def create(
        cls,
        *,
        auth: SourceAuthProvider,
        logger: ContextualLogger,
        http_client: AirweaveHttpClient,
        config: HerbConfig,
    ) -> HerbDocumentsSource:
        """Create a new HERB documents source instance."""
        instance = cls(auth=auth, logger=logger, http_client=http_client)
        if config:
            instance.data_dir = config.data_dir if hasattr(config, "data_dir") else ""
        return instance

    def _load_employees(self) -> None:
        """Load employee directory for name resolution."""
        emp_path = os.path.join(self.data_dir, "metadata", "employee.json")
        if os.path.exists(emp_path):
            with open(emp_path) as f:
                self._employees = json.load(f)

    @staticmethod
    def _humanize_id(doc_id: str) -> str:
        """Convert a document ID into a human-readable title."""
        # Remove common prefixes and replace underscores with spaces
        title = doc_id.replace("_", " ").strip()
        # Capitalize first letter of each word
        return title.title()

    async def generate_entities(
        self,
        *,
        cursor: SyncCursor | None = None,
        files: FileService | None = None,
        node_selections: list[NodeSelectionData] | None = None,
        source_hash_lookup: SourceHashLookup | None = None,
    ) -> AsyncGenerator[BaseEntity, None]:
        """Generate HerbDocumentEntity instances from HERB product files."""
        self._load_employees()
        products_dir = os.path.join(self.data_dir, "products")

        for fname in sorted(os.listdir(products_dir)):
            if not fname.endswith(".json"):
                continue

            product_name = fname.replace(".json", "")
            with open(os.path.join(products_dir, fname)) as f:
                data = json.load(f)

            for doc in data.get("documents", []):
                author_id = doc.get("author", "unknown")
                emp = self._employees.get(author_id, {})
                author_name = emp.get("name") if emp else None

                # Parse creation date
                date_str = doc.get("date", "")
                try:
                    doc_created_at = datetime.fromisoformat(date_str)
                except (ValueError, TypeError):
                    doc_created_at = None

                doc_type = doc.get("type", "Document")
                doc_type_slug = doc_type.lower().replace(" ", "_")

                yield HerbDocumentEntity(
                    doc_id=doc["id"],
                    title=self._humanize_id(doc["id"]),
                    content=doc.get("content", ""),
                    doc_type=doc_type,
                    author_id=author_id,
                    author_name=author_name,
                    feedback=doc.get("feedback"),
                    document_link=doc.get("document_link"),
                    doc_created_at=doc_created_at,
                    product_name=product_name,
                    breadcrumbs=[
                        Breadcrumb(
                            entity_id=product_name,
                            name=product_name,
                            entity_type="HerbProduct",
                        ),
                        Breadcrumb(
                            entity_id=doc_type_slug,
                            name=doc_type,
                            entity_type="HerbDocType",
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
