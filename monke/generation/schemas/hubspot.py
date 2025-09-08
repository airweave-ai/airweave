from typing import Optional
from pydantic import BaseModel, EmailStr, Field


class HubSpotContact(BaseModel):
    """Structured contact content for HubSpot."""

    token: str = Field(
        description="Verification token that MUST appear in at least one property (e.g., email)."
    )
    email: EmailStr
    firstname: str
    lastname: str
    phone: Optional[str] = None
    company: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip: Optional[str] = None
    notes: Optional[str] = None  # not posted to HubSpot; useful context
