"""Sync cursor module for tracking sync progress."""

from typing import Optional, Type
from uuid import UUID

from pydantic import BaseModel


class SyncCursor:
    """Runtime cursor wrapper with typed validation.

    Wraps a Pydantic cursor model and provides simple update/get API.
    Uses Pydantic's native serialization (no custom methods needed).

    For sources with typed cursors, this provides validation and type safety.
    For sources without cursors, falls back to raw dict storage.
    """

    def __init__(
        self,
        sync_id: UUID,
        cursor_schema: Optional[Type[BaseModel]] = None,
        cursor_data: dict | None = None,
    ):
        """Initialize cursor with optional typed schema.

        Args:
            sync_id: Associated sync ID
            cursor_schema: Pydantic model class for validation (e.g., GmailCursor)
            cursor_data: Existing cursor data from database
        """
        self.sync_id = sync_id
        self.cursor_schema = cursor_schema
        self._loaded_from_db = cursor_data is not None

        # Instantiate typed cursor if schema provided
        if cursor_schema:
            if cursor_data:
                # Use Pydantic's model_validate for deserialization
                self._typed_cursor = cursor_schema.model_validate(cursor_data)
            else:
                # Create new empty cursor
                self._typed_cursor = cursor_schema()
        else:
            # Fallback for sources without typed cursors
            self._typed_cursor = None
            self._raw_data = cursor_data or {}

    def update(self, **fields) -> None:
        """Update cursor fields.

        Args:
            **fields: Field name-value pairs to update

        Example:
            cursor.update(history_id="12345")
            cursor.update(table_cursors={"public.users": "2024-11-03T10:00:00Z"})
        """
        if self._typed_cursor:
            # Update typed cursor fields (Pydantic validates)
            for key, value in fields.items():
                setattr(self._typed_cursor, key, value)
        else:
            # Fallback to raw dict
            self._raw_data.update(fields)

    def get(self) -> dict:
        """Get cursor data as dict.

        Returns:
            Cursor data dictionary (serialized for JSON)
        """
        if self._typed_cursor:
            # Use Pydantic's model_dump for serialization
            return self._typed_cursor.model_dump(mode="json")
        return self._raw_data.copy()

    @property
    def data(self) -> dict:
        """Property alias for get() - cleaner syntax.

        Returns:
            Cursor data dictionary (serialized for JSON)
        """
        return self.get()

    @property
    def loaded_from_db(self) -> bool:
        """Whether this cursor was initialized with data from the database.

        Returns True if a previous sync saved cursor data that was loaded
        for this sync run. Returns False on first sync or when cursor loading
        was skipped (force_full_sync, skip_load).
        """
        return self._loaded_from_db

    # Legacy compatibility properties (deprecated)
    @property
    def cursor_data(self) -> dict:
        """Legacy property for backward compatibility.

        Deprecated: Use .data property or .get() method instead.
        """
        return self.get()

    @property
    def cursor_field(self) -> Optional[str]:
        """Legacy property for backward compatibility.

        Deprecated: Typed cursors don't use cursor_field.
        """
        return None
