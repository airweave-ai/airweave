"""Schemas for transformers."""

from typing import Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class TransformerBase(BaseModel):
    """Base schema for transformer."""

    name: str
    description: Optional[str] = None
    method_name: str
    module_name: str
    input_entity_definition_ids: List[str]
    output_entity_definition_ids: List[str]
    config_schema: Dict = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def convert_uuids_to_strings(cls, data: dict) -> dict:
        """Convert UUID lists to string lists."""
        if isinstance(data.get("input_entity_definition_ids", []), list):
            data["input_entity_definition_ids"] = [
                str(x) for x in data["input_entity_definition_ids"]
            ]
        if isinstance(data.get("output_entity_definition_ids", []), list):
            data["output_entity_definition_ids"] = [
                str(x) for x in data["output_entity_definition_ids"]
            ]
        return data


class TransformerCreate(TransformerBase):
    """Schema for creating a transformer."""

    pass


class TransformerUpdate(TransformerBase):
    """Schema for updating a transformer."""

    pass


class Transformer(TransformerBase):
    """Schema for a transformer."""

    id: UUID
    organization_id: UUID
    created_by_email: str
    modified_by_email: str

    model_config = ConfigDict(from_attributes=True)
