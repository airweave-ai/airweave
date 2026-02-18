"""Apollo-specific Pydantic schemas for LLM structured generation."""

from typing import List
from pydantic import BaseModel, Field


class ApolloAccountSpec(BaseModel):
    """Metadata for account (company) generation."""

    name: str = Field(description="Company/account name")
    token: str = Field(description="Unique verification token to embed in the name")
    domain: str = Field(description="Company domain without www (e.g. acme.com)")


class ApolloAccountContent(BaseModel):
    """Content for generated account - name is primary searchable field."""

    tagline: str = Field(description="Short company tagline with embedded token")
    industry: str = Field(description="Industry or sector")


class ApolloAccount(BaseModel):
    """Schema for generating Apollo account content."""

    spec: ApolloAccountSpec
    content: ApolloAccountContent


class ApolloContactSpec(BaseModel):
    """Metadata for contact generation."""

    first_name: str = Field(description="Contact first name")
    last_name: str = Field(description="Contact last name")
    token: str = Field(description="Unique verification token")
    email: str = Field(description="Email address")
    title: str = Field(description="Job title")
    organization_name: str = Field(description="Company name")


class ApolloContactContent(BaseModel):
    """Content for generated contact - title/name are searchable."""

    title_suffix: str = Field(
        description="Extra title detail with embedded token (e.g. 'Focused on X')"
    )


class ApolloContact(BaseModel):
    """Schema for generating Apollo contact content."""

    spec: ApolloContactSpec
    content: ApolloContactContent
