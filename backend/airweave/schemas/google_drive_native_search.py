"""Google Drive native search request/response schemas."""

from __future__ import annotations

from typing import List

from pydantic import BaseModel, Field, field_validator

from airweave.platform.entities.google_drive import GoogleDriveFileEntity


class GoogleDriveNativeSearchRequest(BaseModel):
    """Request payload for connection-scoped Google Drive native search."""

    query: str = Field(..., description="Search query text.")
    limit: int = Field(default=10, ge=1, le=100, description="Max results to return (1-100).")

    @field_validator("query")
    @classmethod
    def query_not_empty(cls, v: str) -> str:
        """Ensure the search query is not empty or whitespace-only."""
        if not v.strip():
            raise ValueError("Query cannot be empty")
        return v


class GoogleDriveNativeSearchResponse(BaseModel):
    """Response payload for Google Drive native search."""

    results: List[GoogleDriveFileEntity] = Field(default_factory=list)
