"""Filter schemas for spotlight search.

Defines the allowed filterable fields and operators for search filters.
Pydantic automatically validates all filter inputs.
"""

from enum import Enum
from typing import List, Union

from pydantic import BaseModel, Field


class SpotlightFilterableField(str, Enum):
    """Filterable fields in spotlight search.

    Uses dot notation for nested fields (e.g., breadcrumbs.name,
    airweave_system_metadata.source_name).
    """

    # Base entity fields
    ENTITY_ID = "entity_id"
    NAME = "name"
    CREATED_AT = "created_at"
    UPDATED_AT = "updated_at"

    # Breadcrumb struct fields (for hierarchy navigation)
    BREADCRUMBS_ENTITY_ID = "breadcrumbs.entity_id"
    BREADCRUMBS_NAME = "breadcrumbs.name"
    BREADCRUMBS_ENTITY_TYPE = "breadcrumbs.entity_type"

    # System metadata fields
    SYSTEM_METADATA_ENTITY_TYPE = "airweave_system_metadata.entity_type"
    SYSTEM_METADATA_SOURCE_NAME = "airweave_system_metadata.source_name"
    SYSTEM_METADATA_ORIGINAL_ENTITY_ID = "airweave_system_metadata.original_entity_id"
    SYSTEM_METADATA_CHUNK_INDEX = "airweave_system_metadata.chunk_index"
    SYSTEM_METADATA_SYNC_ID = "airweave_system_metadata.sync_id"
    SYSTEM_METADATA_SYNC_JOB_ID = "airweave_system_metadata.sync_job_id"


class SpotlightFilterOperator(str, Enum):
    """Supported filter operators."""

    EQUALS = "equals"
    NOT_EQUALS = "not_equals"
    CONTAINS = "contains"
    GREATER_THAN = "greater_than"
    LESS_THAN = "less_than"
    GREATER_THAN_OR_EQUAL = "greater_than_or_equal"
    LESS_THAN_OR_EQUAL = "less_than_or_equal"
    IN = "in"
    NOT_IN = "not_in"


class SpotlightFilterCondition(BaseModel):
    """A single filter condition.

    Pydantic validates that:
    - `field` is a valid SpotlightFilterableField enum value
    - `operator` is a valid SpotlightFilterOperator enum value
    - `value` matches the expected types

    Invalid filters raise pydantic.ValidationError automatically.

    Examples:
        {"field": "airweave_system_metadata.source_name", "operator": "equals",
         "value": "notion"}
        {"field": "created_at", "operator": "greater_than",
         "value": "2024-01-01T00:00:00Z"}
        {"field": "breadcrumbs.name", "operator": "contains", "value": "Engineering"}
    """

    field: SpotlightFilterableField = Field(
        ...,
        description="Field to filter on (use dot notation for nested fields).",
    )
    operator: SpotlightFilterOperator = Field(..., description="The comparison operator to use.")
    value: Union[str, int, float, bool, List[str], List[int]] = Field(
        ...,
        description="Value to compare against. Use a list for 'in' and 'not_in' operators.",
    )


class SpotlightFilterGroup(BaseModel):
    """A group of filter conditions combined with AND.

    Multiple filter groups are combined with OR, allowing expressions like:
    (A AND B) OR (C AND D)

    Examples:
        Single group (AND):
            {"conditions": [
                {"field": "airweave_system_metadata.source_name",
                 "operator": "equals", "value": "slack"},
                {"field": "airweave_system_metadata.entity_type",
                 "operator": "equals", "value": "SlackMessageEntity"}
            ]}

        Multiple groups (OR between groups, AND within):
            [
                {"conditions": [{"field": "name", "operator": "equals",
                                 "value": "doc1"}]},
                {"conditions": [{"field": "name", "operator": "equals",
                                 "value": "doc2"}]}
            ]

        Breadcrumb filtering:
            {"conditions": [
                {"field": "breadcrumbs.name", "operator": "contains",
                 "value": "Engineering"}
            ]}
    """

    conditions: List[SpotlightFilterCondition] = Field(
        ...,
        min_length=1,
        description="Filter conditions within this group, combined with AND",
    )
