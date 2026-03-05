"""Filter schemas for agentic search.

Defines the allowed filterable fields and operators for search filters.
Pydantic automatically validates all filter inputs, including semantic
checks that reject nonsensical combinations (e.g. ``entity_id > "boat"``).
"""

from enum import Enum
from typing import List, Optional, Union

from pydantic import BaseModel, Field, model_validator


class AgenticSearchFilterableField(str, Enum):
    """Filterable fields in agentic search.

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


class AgenticSearchFilterOperator(str, Enum):
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


# ── Field-type classification ─────────────────────────────────────────────────
# Used by the semantic validator to decide which operator+value combos are sane.

_TEXT_FIELDS: frozenset[AgenticSearchFilterableField] = frozenset(
    {
        AgenticSearchFilterableField.ENTITY_ID,
        AgenticSearchFilterableField.NAME,
        AgenticSearchFilterableField.BREADCRUMBS_ENTITY_ID,
        AgenticSearchFilterableField.BREADCRUMBS_NAME,
        AgenticSearchFilterableField.BREADCRUMBS_ENTITY_TYPE,
        AgenticSearchFilterableField.SYSTEM_METADATA_ENTITY_TYPE,
        AgenticSearchFilterableField.SYSTEM_METADATA_SOURCE_NAME,
        AgenticSearchFilterableField.SYSTEM_METADATA_ORIGINAL_ENTITY_ID,
        AgenticSearchFilterableField.SYSTEM_METADATA_SYNC_ID,
        AgenticSearchFilterableField.SYSTEM_METADATA_SYNC_JOB_ID,
    }
)

_DATE_FIELDS: frozenset[AgenticSearchFilterableField] = frozenset(
    {
        AgenticSearchFilterableField.CREATED_AT,
        AgenticSearchFilterableField.UPDATED_AT,
    }
)

_NUMERIC_FIELDS: frozenset[AgenticSearchFilterableField] = frozenset(
    {
        AgenticSearchFilterableField.SYSTEM_METADATA_CHUNK_INDEX,
    }
)

_ORDERABLE_FIELDS = _DATE_FIELDS | _NUMERIC_FIELDS

# ── Operator groups ───────────────────────────────────────────────────────────

_ORDERING_OPS: frozenset[AgenticSearchFilterOperator] = frozenset(
    {
        AgenticSearchFilterOperator.GREATER_THAN,
        AgenticSearchFilterOperator.LESS_THAN,
        AgenticSearchFilterOperator.GREATER_THAN_OR_EQUAL,
        AgenticSearchFilterOperator.LESS_THAN_OR_EQUAL,
    }
)

_LIST_OPS: frozenset[AgenticSearchFilterOperator] = frozenset(
    {
        AgenticSearchFilterOperator.IN,
        AgenticSearchFilterOperator.NOT_IN,
    }
)


class AgenticSearchFilterCondition(BaseModel):
    """A single filter condition.

    Pydantic validates that:
    - ``field`` is a valid AgenticSearchFilterableField enum value
    - ``operator`` is a valid AgenticSearchFilterOperator enum value
    - ``value`` matches the expected types
    - The combination of field + operator + value is semantically valid

    Invalid filters raise ``pydantic.ValidationError`` automatically.

    Examples:
        {"field": "airweave_system_metadata.source_name", "operator": "equals",
         "value": "notion"}
        {"field": "created_at", "operator": "greater_than",
         "value": "2024-01-01T00:00:00Z"}
        {"field": "breadcrumbs.name", "operator": "contains", "value": "Engineering"}
    """

    field: AgenticSearchFilterableField = Field(
        ...,
        description="Field to filter on (use dot notation for nested fields).",
    )
    operator: AgenticSearchFilterOperator = Field(
        ..., description="The comparison operator to use."
    )
    value: Union[str, int, float, bool, List[str], List[int]] = Field(
        ...,
        description="Value to compare against. Use a list for 'in' and 'not_in' operators.",
    )

    # ── Semantic validation ────────────────────────────────────────────────────

    @model_validator(mode="after")
    def check_semantic_validity(self) -> "AgenticSearchFilterCondition":
        """Reject nonsensical field / operator / value combinations.

        Rules:
            1. Ordering operators (>, <, >=, <=) only on date or numeric fields.
            2. ``contains`` only on text fields.
            3. ``in`` / ``not_in`` require a list value.
            4. Scalar operators must not receive a list value.
            5. Numeric fields require numeric (or numeric-string) values.
        """
        f, op, v = self.field, self.operator, self.value

        # 1. Ordering operators on text fields are nonsensical
        #    e.g. entity_id > "boat"
        if op in _ORDERING_OPS and f not in _ORDERABLE_FIELDS:
            raise ValueError(
                f"Cannot use '{op.value}' on text field '{f.value}'. "
                f"Ordering operators (greater_than, less_than, …) only work on "
                f"date fields (created_at, updated_at) or numeric fields "
                f"(chunk_index). Use 'equals', 'not_equals', 'contains', 'in', "
                f"or 'not_in' instead."
            )

        # 2. 'contains' is a substring match — meaningless on dates/numbers
        #    e.g. created_at contains "2024"
        if op == AgenticSearchFilterOperator.CONTAINS and f not in _TEXT_FIELDS:
            kind = "date" if f in _DATE_FIELDS else "numeric"
            raise ValueError(
                f"Cannot use 'contains' on {kind} field '{f.value}'. "
                f"Use 'equals' or an ordering operator instead."
            )

        # 3. in / not_in require list values
        #    e.g. source_name in "slack"  →  should be ["slack"]
        if op in _LIST_OPS and not isinstance(v, list):
            raise ValueError(
                f"Operator '{op.value}' requires a list value, "
                f'got {type(v).__name__} ("{v}"). '
                f'Example: ["val1", "val2"]'
            )

        # 4. Scalar operators must not receive list values
        #    e.g. name equals ["a", "b"]  →  use 'in' instead
        if op not in _LIST_OPS and isinstance(v, list):
            raise ValueError(
                f"Operator '{op.value}' expects a single value, not a list. "
                f"Use 'in' or 'not_in' for list matching."
            )

        # 5. Numeric fields must receive a numeric value
        #    e.g. chunk_index = "boat"
        if f in _NUMERIC_FIELDS and not isinstance(v, list):
            if isinstance(v, (int, float)):
                pass  # fine
            elif isinstance(v, str):
                try:
                    float(v)
                except ValueError:
                    raise ValueError(
                        f"Field '{f.value}' is numeric — expected a number, got '{v}'."
                    )
            elif isinstance(v, bool):
                raise ValueError(
                    f"Field '{f.value}' is numeric — expected a number, got boolean {v}."
                )

        return self

    def to_md(self) -> str:
        """Render the condition as markdown.

        Returns:
            Markdown string: ``field operator value``
        """
        return f"`{self.field.value}` {self.operator.value} `{self.value!r}`"


class AgenticSearchFilterGroup(BaseModel):
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

    conditions: List[AgenticSearchFilterCondition] = Field(
        ...,
        min_length=1,
        description="Filter conditions within this group, combined with AND",
    )

    def to_md(self) -> str:
        """Render the filter group as markdown.

        Conditions are joined with AND.

        Returns:
            Markdown string: (condition1 AND condition2 AND ...)
        """
        conditions_md = " AND ".join(c.to_md() for c in self.conditions)
        return f"({conditions_md})"


def format_filter_groups_md(filter_groups: Optional[List[AgenticSearchFilterGroup]]) -> str:
    """Format a list of filter groups as readable markdown.

    Renders filter groups using their to_md() methods, joined with OR.
    Used by prompt builders to display user filters in LLM context.

    Args:
        filter_groups: Filter groups to format, or None/empty for no filters.

    Returns:
        Markdown string representing the filter groups, or "None" if empty.
    """
    if not filter_groups:
        return "None"
    return " OR ".join(group.to_md() for group in filter_groups)
