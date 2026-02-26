"""HERB Messaging source — syncs Slack messages from the HERB benchmark dataset."""

import json
import os
from datetime import datetime
from typing import Any, AsyncGenerator, Dict, Optional, Union

from airweave.platform.configs.auth import HerbAuthConfig
from airweave.platform.configs.config import HerbConfig
from airweave.platform.decorators import source
from airweave.platform.entities._base import BaseEntity, Breadcrumb
from airweave.platform.entities.herb_messaging import HerbMessageEntity
from airweave.platform.sources._base import BaseSource
from airweave.schemas.source_connection import AuthenticationMethod


@source(
    name="HERB Messaging",
    short_name="herb_messaging",
    auth_methods=[AuthenticationMethod.DIRECT],
    auth_config_class=HerbAuthConfig,
    config_class=HerbConfig,
    labels=["Benchmark", "HERB"],
    internal=True,
)
class HerbMessagingSource(BaseSource):
    """Source that syncs Slack messages from the HERB benchmark dataset."""

    def __init__(self):
        """Initialize the HERB messaging source."""
        super().__init__()
        self.data_dir: str = ""
        self._employees: Dict[str, Dict] = {}

    @classmethod
    async def create(
        cls,
        credentials: Optional[Union[Dict[str, Any], HerbAuthConfig]] = None,
        config: Optional[Dict[str, Any]] = None,
    ) -> "HerbMessagingSource":
        """Create a new HERB messaging source instance."""
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

    async def generate_entities(self) -> AsyncGenerator[BaseEntity, None]:
        """Generate HerbMessageEntity instances from HERB product files."""
        self._load_employees()
        products_dir = os.path.join(self.data_dir, "products")

        for fname in sorted(os.listdir(products_dir)):
            if not fname.endswith(".json"):
                continue

            product_name = fname.replace(".json", "")
            with open(os.path.join(products_dir, fname)) as f:
                data = json.load(f)

            for msg in data.get("slack", []):
                channel = msg.get("Channel", {})
                user_data = msg.get("Message", {}).get("User", {})
                sender_id = user_data.get("userId", "unknown")

                # Resolve sender name from employee directory
                emp = self._employees.get(sender_id, {})
                sender_name = emp.get("name") if emp else None

                # Parse timestamp
                ts_str = user_data.get("timestamp", "")
                try:
                    message_time = datetime.fromisoformat(ts_str)
                except (ValueError, TypeError):
                    message_time = datetime(2026, 1, 1)

                channel_id = channel.get("channelID", "")
                channel_name = channel.get("name", "")

                yield HerbMessageEntity(
                    message_id=msg["id"],
                    text=user_data.get("text", ""),
                    sender_id=sender_id,
                    sender_name=sender_name,
                    channel_name=channel_name,
                    channel_id=channel_id,
                    message_time=message_time,
                    product_name=product_name,
                    breadcrumbs=[
                        Breadcrumb(
                            entity_id=product_name,
                            name=product_name,
                            entity_type="HerbProduct",
                        ),
                        Breadcrumb(
                            entity_id=channel_id,
                            name=f"#{channel_name}",
                            entity_type="HerbChannel",
                        ),
                    ],
                )

    async def validate(self) -> bool:
        """Validate that the HERB data directory exists and contains product files."""
        products_dir = os.path.join(self.data_dir, "products")
        return os.path.isdir(products_dir) and any(
            f.endswith(".json") for f in os.listdir(products_dir)
        )
