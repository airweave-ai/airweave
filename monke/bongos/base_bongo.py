"""Base bongo class for all connector integrations."""

from abc import ABC, abstractmethod
from typing import Any, Dict, List


class BaseBongo(ABC):
    """Base class for all connector bongos.

    The bongo plays the real API to create, update, and delete test data.
    """

    def __init__(self, credentials: Dict[str, Any]):
        """Initialize the bongo.

        Args:
            credentials: Credentials for the connector API
        """
        self.credentials = credentials
        self.created_entities = []  # Track what we create for cleanup

    @abstractmethod
    async def create_entities(self) -> List[Dict[str, Any]]:
        """Create test entities via real API.

        Returns:
            List of created entity data for verification
        """
        pass

    @abstractmethod
    async def update_entities(self) -> List[Dict[str, Any]]:
        """Update test entities via real API.

        Returns:
            List of updated entity data for verification
        """
        pass

    @abstractmethod
    async def delete_entities(self) -> List[str]:
        """Delete all test entities via real API.

        Returns:
            List of deleted entity IDs for verification
        """
        pass

    @abstractmethod
    async def delete_specific_entities(self, entities: List[Dict[str, Any]]) -> List[str]:
        """Delete specific entities via real API.

        Args:
            entities: List of entities to delete

        Returns:
            List of deleted entity IDs for verification
        """
        pass

    @abstractmethod
    async def cleanup(self):
        """Clean up any remaining test data via real API."""
        pass
