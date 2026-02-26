"""HERB Meetings source — syncs meeting transcripts and chats from the HERB benchmark dataset."""

import json
import os
from datetime import datetime
from typing import Any, AsyncGenerator, Dict, Optional, Union

from airweave.platform.configs.auth import HerbAuthConfig
from airweave.platform.configs.config import HerbConfig
from airweave.platform.decorators import source
from airweave.platform.entities._base import BaseEntity, Breadcrumb
from airweave.platform.entities.herb_meetings import (
    HerbMeetingChatEntity,
    HerbMeetingTranscriptEntity,
)
from airweave.platform.sources._base import BaseSource
from airweave.schemas.source_connection import AuthenticationMethod


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

    def __init__(self):
        """Initialize the HERB meetings source."""
        super().__init__()
        self.data_dir: str = ""
        self._employees: Dict[str, Dict] = {}

    @classmethod
    async def create(
        cls,
        credentials: Optional[Union[Dict[str, Any], HerbAuthConfig]] = None,
        config: Optional[Dict[str, Any]] = None,
    ) -> "HerbMeetingsSource":
        """Create a new HERB meetings source instance."""
        instance = cls()
        if config:
            instance.data_dir = (
                config.get("data_dir", "") if isinstance(config, dict) else config.data_dir
            )
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

    async def generate_entities(self) -> AsyncGenerator[BaseEntity, None]:
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

    async def validate(self) -> bool:
        """Validate that the HERB data directory exists and contains product files."""
        products_dir = os.path.join(self.data_dir, "products")
        return os.path.isdir(products_dir) and any(
            f.endswith(".json") for f in os.listdir(products_dir)
        )
