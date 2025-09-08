from typing import List
from pydantic import BaseModel, EmailStr, Field


class OutlookMessage(BaseModel):
    token: str = Field(description="Verification token")
    subject: str
    body_html: str
    to: List[EmailStr] = Field(default_factory=list)
