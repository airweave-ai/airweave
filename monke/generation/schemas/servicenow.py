"""ServiceNow Pydantic schemas for LLM content generation."""

from pydantic import BaseModel, Field


class ServiceNowIncidentSpec(BaseModel):
    """Metadata for incident generation."""

    short_description: str = Field(
        description="Brief one-line summary of the incident"
    )
    token: str = Field(description="Unique verification token to embed in the content")


class ServiceNowIncidentContent(BaseModel):
    """Content for generated incident."""

    description: str = Field(
        description="Detailed incident description with embedded token"
    )
    steps_to_reproduce: str = Field(
        description="Steps to reproduce the issue if applicable"
    )


class ServiceNowIncident(BaseModel):
    """Schema for generating ServiceNow incident content."""

    spec: ServiceNowIncidentSpec
    content: ServiceNowIncidentContent
