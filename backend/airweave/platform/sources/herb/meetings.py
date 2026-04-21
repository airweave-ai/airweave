"""HERB Meetings source — syncs meeting transcripts and chats from the HERB benchmark dataset."""

from __future__ import annotations

import json
import os
from datetime import datetime
from typing import TYPE_CHECKING, AsyncGenerator, Dict, Optional

from airweave.core.logging import ContextualLogger
from airweave.domains.browse_tree.types import NodeSelectionData
from airweave.domains.sources.token_providers.protocol import SourceAuthProvider
from airweave.domains.storage.file_service import FileService
from airweave.domains.syncs.cursors.cursor import SyncCursor
from airweave.platform.configs.auth import HerbAuthConfig
from airweave.platform.configs.config import HerbConfig
from airweave.platform.decorators import source
from airweave.platform.entities._base import BaseEntity, Breadcrumb
from airweave.platform.entities.herb_meetings import (
    HerbMeetingChatEntity,
    HerbMeetingTranscriptEntity,
)
from airweave.platform.http_client.airweave_client import AirweaveHttpClient
from airweave.platform.sources._base import BaseSource
from airweave.schemas.source_connection import AuthenticationMethod

if TYPE_CHECKING:
    from airweave.domains.sync_pipeline.source_hash_lookup import SourceHashLookup


@source(
    name="HERB Meetings",
    short_name="herb_meetings",
    auth_methods=[AuthenticationMethod.DIRECT],
    auth_config_class=HerbAuthConfig,
    config_class=HerbConfig,
    labels=["Benchmark", "HERB"],
    internal=True,
)
class HerbMeetingsSource(BaseSource):
    """Source that syncs meeting transcripts and chats from the HERB benchmark dataset."""

    def __init__(
        self,
        *,
        auth: SourceAuthProvider,
        logger: ContextualLogger,
        http_client: AirweaveHttpClient,
    ) -> None:
        """Initialize the HERB meetings source."""
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
    ) -> HerbMeetingsSource:
        """Create a new HERB meetings source instance."""
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

    def _resolve_names(self, participant_ids: list) -> Optional[str]:
        """Resolve a list of employee IDs to names."""
        names = []
        for pid in participant_ids:
            emp = self._employees.get(pid, {})
            if emp:
                names.append(emp.get("name", pid))
            else:
                names.append(pid)
        return ", ".join(names) if names else None

    async def generate_entities(
        self,
        *,
        cursor: SyncCursor | None = None,
        files: FileService | None = None,
        node_selections: list[NodeSelectionData] | None = None,
        source_hash_lookup: SourceHashLookup | None = None,
    ) -> AsyncGenerator[BaseEntity, None]:
        """Generate meeting entities from HERB product files."""
        self._load_employees()
        products_dir = os.path.join(self.data_dir, "products")

        for fname in sorted(os.listdir(products_dir)):
            if not fname.endswith(".json"):
                continue

            product_name = fname.replace(".json", "")
            with open(os.path.join(products_dir, fname)) as f:
                data = json.load(f)

            # Meeting transcripts
            for mt in data.get("meeting_transcripts", []):
                participants = mt.get("participants", [])
                participant_ids_str = ", ".join(participants)
                participant_names = self._resolve_names(participants)

                # Parse meeting date
                date_str = mt.get("date", "")
                try:
                    meeting_date = datetime.fromisoformat(date_str)
                except (ValueError, TypeError):
                    meeting_date = None

                date_label = date_str[:10] if date_str else "unknown"
                title = f"{product_name} meeting — {date_label}"

                yield HerbMeetingTranscriptEntity(
                    meeting_id=mt["id"],
                    title=title,
                    transcript=mt.get("transcript", ""),
                    document_type=mt.get("document_type", "meeting_transcript"),
                    participant_ids=participant_ids_str,
                    participant_names=participant_names,
                    meeting_date=meeting_date,
                    product_name=product_name,
                    breadcrumbs=[
                        Breadcrumb(
                            entity_id=product_name,
                            name=product_name,
                            entity_type="HerbProduct",
                        ),
                    ],
                )

            # Meeting chats
            for mc in data.get("meeting_chats", []):
                yield HerbMeetingChatEntity(
                    chat_id=mc["id"],
                    text=mc.get("text", ""),
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
