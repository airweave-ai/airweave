"""Dropbox-specific generation schema."""

from datetime import datetime
from typing import List, Optional, Dict
from pydantic import BaseModel, Field


class DropboxArtifact(BaseModel):
    """Schema for Dropbox file generation."""

    title: str = Field(description="File title")
    description: str = Field(description="File description or main content")
    token: str = Field(description="Unique token to embed in content")
    sections: Optional[List[Dict[str, str]]] = Field(default=None, description="Optional sections for documents")
    data_rows: Optional[List[str]] = Field(default=None, description="Optional data rows for CSV files")
    metadata: Optional[Dict[str, str]] = Field(default=None, description="Optional metadata for structured files")
    created_at: datetime = Field(default_factory=datetime.now)
