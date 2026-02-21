"""Domain exceptions for collections."""


class CollectionNotFoundError(Exception):
    """Raised when a collection is not found."""

    def __init__(self, readable_id: str):
        """Initialize with the missing readable_id."""
        self.readable_id = readable_id
        super().__init__(f"Collection '{readable_id}' not found")


class CollectionAlreadyExistsError(Exception):
    """Raised when a collection with the same readable_id already exists."""

    def __init__(self, readable_id: str):
        """Initialize with the duplicate readable_id."""
        self.readable_id = readable_id
        super().__init__(f"Collection with readable_id '{readable_id}' already exists")
