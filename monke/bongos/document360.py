"""Document360-specific bongo implementation.

Document360 Customer API is read-only (GET only). This bongo does not create,
update, or delete data. Monke tests for Document360 only run sync + verify
against an existing knowledge base that the user has configured.
"""

from typing import Any, Dict, List

from monke.bongos.base_bongo import BaseBongo
from monke.utils.logging import get_logger


class Document360Bongo(BaseBongo):
    """Bongo for Document360.

    Document360 Customer API does not support creating/updating/deleting
    articles or categories. Tests use an existing KB: configure api_token
    and optional base_url/lang_code, then run sync + verify.
    """

    connector_type = "document360"

    def __init__(self, credentials: Dict[str, Any], **kwargs):
        """Initialize the Document360 bongo.

        Args:
            credentials: Dict with "api_token" (Document360 API token).
            **kwargs: Optional config (base_url, lang_code).
        """
        super().__init__(credentials)
        self.api_token: str = (
            credentials.get("api_token")
            or credentials.get("access_token")
        )
        if not self.api_token:
            raise ValueError(
                "Missing Document360 api_token. "
                "Generate from Settings > Knowledge base portal > API tokens."
            )
        self.logger = get_logger("document360_bongo")

    async def create_entities(self) -> List[Dict[str, Any]]:
        """No-op: Document360 Customer API is read-only."""
        self.logger.info(
            "Document360 API is read-only; skipping create. "
            "Sync will use existing KB content."
        )
        return []

    async def update_entities(self) -> List[Dict[str, Any]]:
        """No-op: Document360 Customer API is read-only."""
        return []

    async def delete_entities(self) -> List[str]:
        """No-op: Document360 Customer API is read-only."""
        return []

    async def delete_specific_entities(self, entities: List[Dict[str, Any]]) -> List[str]:
        """No-op: Document360 Customer API is read-only."""
        return []

    async def cleanup(self) -> None:
        """No-op: nothing to clean up."""
        pass
