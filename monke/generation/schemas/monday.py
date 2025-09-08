from typing import Optional, List
from pydantic import BaseModel, Field


class MondayItem(BaseModel):
    token: str = Field(description="Verification token to embed in item name or text column")
    name: str = Field(description="Item name; should contain the token")
    note: Optional[str] = Field(default=None, description="Short note to put into a text column")
    comments: List[str] = Field(default_factory=list, description="Optional updates/comments")
