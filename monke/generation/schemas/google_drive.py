"""Google Drive-specific generation schema."""

from datetime import datetime
from typing import List, Optional, Dict
from pydantic import BaseModel, Field


class GoogleDriveArtifact(BaseModel):
    """Schema for Google Drive file generation."""

    title: str = Field(description="File title")
    description: str = Field(description="File description or main content")
    token: str = Field(description="Unique token to embed in content")
    sections: Optional[List[Dict[str, str]]] = Field(default=None, description="Optional sections for documents")
    rows: Optional[List[str]] = Field(default=None, description="Optional data rows for spreadsheets")
    created_at: datetime = Field(default_factory=datetime.now)
