"""Query interpretation operation.

Uses LLM to interpret natural language queries and extract structured Qdrant filters.
Enables users to filter results using natural language without knowing filter syntax.
"""

from typing import TYPE_CHECKING, Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator

from airweave import crud
from airweave.api.context import ApiContext
from airweave.db.session import get_db_context
from airweave.search.context import SearchContext
from airweave.search.prompts import QUERY_INTERPRETATION_SYSTEM_PROMPT
from airweave.search.providers._base import BaseProvider

from ._base import SearchOperation

if TYPE_CHECKING:
    from airweave.search.state import SearchState


class ValueMatch(BaseModel):
    """Exact match condition for a single value."""

    model_config = {"extra": "forbid"}
    value: str | int | float | bool


class AnyMatch(BaseModel):
    """Any-of match condition for multiple values (IN semantics)."""

    model_config = {"extra": "forbid"}
    any: List[str | int | float | bool]


class RangeSpec(BaseModel):
    """Range condition with standard comparison operators."""

    model_config = {"extra": "forbid"}
    gt: Optional[str | float] = None
    gte: Optional[str | float] = None
    lt: Optional[str | float] = None
    lte: Optional[str | float] = None


class FilterCondition(BaseModel):
    """A single filter condition."""

    model_config = {"extra": "forbid"}

    key: str
    match: Optional[ValueMatch | AnyMatch] = None
    range: Optional[RangeSpec] = None


class ExtractedFilters(BaseModel):
    """Structured output schema for extracted filters."""

    model_config = {"extra": "forbid"}

    filters: List[FilterCondition] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)

    @field_validator("filters", mode="before")
    @classmethod
    def convert_none_to_empty_list(cls, v):
        """Convert None to empty list for compatibility with providers that return null."""
        if v is None:
            return []
        return v


class QueryInterpretation(SearchOperation):
    """Extract structured Qdrant filters from natural language query."""

    CONFIDENCE_THRESHOLD = 0.7

    # System metadata fields that are stored in airweave_system_metadata nested object
    # These need to be mapped from simple names to nested paths for Qdrant
    NESTED_SYSTEM_FIELDS = {
        "source_name": "Source connector name (case-sensitive)",
        "entity_type": "Entity type name",
        "sync_id": "Sync ID (UUID, for debugging)",
    }

    # Entity-level timestamp fields (not nested)
    ENTITY_TIMESTAMP_FIELDS = {
        "created_at": "Entity creation timestamp (ISO8601 datetime)",
        "updated_at": "Entity last update timestamp (ISO8601 datetime)",
    }

    # Fields that actually exist as filterable attributes in the Vespa schema.
    # After the Vespa migration, source-specific entity fields (e.g. title, status,
    # assignee from Jira/Notion/etc.) are stored in the `payload` JSON string field
    # and are NOT individually indexed or filterable. Only fields defined as
    # `attribute` in base_entity.sd are filterable.
    # See: vespa/app/schemas/base_entity.sd
    VESPA_FILTERABLE_FIELDS = {
        # Base entity fields
        "entity_id",
        "name",
        "created_at",
        "updated_at",
        # System metadata fields (logical names, mapped by _map_to_qdrant_path)
        "source_name",
        "entity_type",
        "sync_id",
        # Already-prefixed dotted paths (in case LLM uses full notation)
        "airweave_system_metadata.source_name",
        "airweave_system_metadata.entity_type",
        "airweave_system_metadata.sync_id",
        "airweave_system_metadata.sync_job_id",
        "airweave_system_metadata.hash",
        "airweave_system_metadata.original_entity_id",
        "airweave_system_metadata.collection_id",
        "airweave_system_metadata.chunk_index",
    }

    def __init__(self, providers: List[BaseProvider]) -> None:
        """Initialize with list of LLM providers in preference order.

        Args:
            providers: List of LLM providers for structured output with fallback support
        """
        if not providers:
            raise ValueError("QueryInterpretation requires at least one provider")
        self.providers = providers

    def depends_on(self) -> List[str]:
        """Depends on query expansion to get all query variations."""
        return ["QueryExpansion"]

    async def execute(
        self,
        context: SearchContext,
        state: "SearchState",
        ctx: ApiContext,
    ) -> None:
        """Extract filters from query using LLM."""
        ctx.logger.debug("[QueryInterpretation] Extracting filters from query")

        query = context.query
        expanded_queries = state.expanded_queries or []

        # Emit interpretation start
        await context.emitter.emit(
            "interpretation_start",
            {},
            op_name=self.__class__.__name__,
        )

        # Discover available fields for this collection
        available_fields = await self._discover_fields(context.readable_collection_id, ctx)

        # Build prompts
        system_prompt = self._build_system_prompt(available_fields)
        user_prompt = self._build_user_prompt(query, expanded_queries)

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        # Get structured output from provider with fallback
        # Note: Token validation happens per-provider in the fallback loop
        async def call_provider(provider: BaseProvider) -> BaseModel:
            # Validate prompt length for this specific provider
            self._validate_prompt_length_for_provider(system_prompt, user_prompt, provider)
            return await provider.structured_output(messages, ExtractedFilters)

        result = await self._execute_with_provider_fallback(
            providers=self.providers,
            operation_call=call_provider,
            operation_name="QueryInterpretation",
            ctx=ctx,
            state=state,
        )

        # Check confidence threshold
        ctx.logger.debug(f"[QueryInterpretation] Confidence: {result.confidence}")
        if result.confidence < self.CONFIDENCE_THRESHOLD:
            # Low confidence - don't apply filters
            self._report_metrics(
                state,
                filters_extracted=0,
                enabled=True,
                confidence=result.confidence,
                skipped=True,
            )
            await context.emitter.emit(
                "interpretation_skipped",
                {
                    "reason": "confidence_below_threshold",
                    "confidence": result.confidence,
                    "threshold": self.CONFIDENCE_THRESHOLD,
                },
                op_name=self.__class__.__name__,
            )
            return

        # Validate and map filter conditions
        validated_filters = self._validate_filters(result.filters, available_fields)
        ctx.logger.debug(f"[QueryInterpretation] Validated filters: {validated_filters}")

        if not validated_filters:
            # No valid filters to apply
            self._report_metrics(
                state,
                filters_extracted=0,
                enabled=True,
                confidence=result.confidence,
                skipped=True,
            )
            await context.emitter.emit(
                "interpretation_skipped",
                {
                    "reason": "no_valid_filters",
                    "confidence": result.confidence,
                },
                op_name=self.__class__.__name__,
            )
            return

        # Build Qdrant filter dict
        filter_dict = self._build_qdrant_filter(validated_filters)
        ctx.logger.debug(f"[QueryInterpretation] Filter dict: {filter_dict}")

        # Write to state (UserFilter will merge with this if it runs)
        state.filter = filter_dict

        # Report metrics for analytics
        self._report_metrics(
            state,
            filters_extracted=len(validated_filters),
            enabled=True,
            confidence=result.confidence,
            skipped=False,
        )

        # Emit filter applied
        await context.emitter.emit(
            "filter_applied",
            {"filter": filter_dict},
            op_name=self.__class__.__name__,
        )

    async def _discover_fields(
        self, collection_id: str, ctx: ApiContext
    ) -> Dict[str, Dict[str, str]]:
        """Discover available fields from collection's entity definitions."""
        from airweave import schemas
        from airweave.platform.locator import resource_locator

        fields = {}

        async with get_db_context() as db:
            # Get source connections for this collection
            source_connections = await crud.source_connection.get_for_collection(
                db, readable_collection_id=collection_id, ctx=ctx
            )

            if not source_connections:
                raise ValueError(f"No source connections found for collection {collection_id}")

            # Get unique short_names to avoid duplicate field discovery
            unique_short_names = {conn.short_name for conn in source_connections}

            # Get fields for each unique source
            for short_name in unique_short_names:
                # Skip PostgreSQL - doesn't support query interpretation
                if short_name == "postgresql":
                    continue

                source = await crud.source.get_by_short_name(db, short_name=short_name)
                if not source:
                    continue

                source_fields = await self._get_source_fields(db, source, resource_locator, schemas)

                if not source_fields:
                    raise ValueError(
                        f"No fields discovered for source '{short_name}'. "
                        f"Cannot perform query interpretation."
                    )

                # Store using just the short_name as the key so LLM uses correct value
                # Add display name in a special comment field for clarity
                fields[short_name] = source_fields

        if not fields:
            raise ValueError(
                "No valid sources found for query interpretation. "
                "PostgreSQL sources do not support query interpretation."
            )

        return fields

    async def _get_source_fields(
        self, db: Any, source: Any, resource_locator: Any, schemas: Any
    ) -> Dict[str, str]:
        """Get fields for a specific source from its entity definitions."""
        entity_defs = await crud.entity_definition.get_multi_by_source_short_name(
            db, source_short_name=source.short_name
        )

        if not entity_defs:
            return {}

        all_fields = {}

        for entity_def in entity_defs:
            # Convert to schema and get entity class
            entity_schema = schemas.EntityDefinition.model_validate(
                entity_def, from_attributes=True
            )
            entity_class = resource_locator.get_entity_definition(entity_schema)

            # Extract filterable fields from entity class
            if hasattr(entity_class, "model_fields"):
                for field_name, field_info in entity_class.model_fields.items():
                    if field_name.startswith("_") or field_name == "airweave_system_metadata":
                        continue

                    # Skip source-specific fields that aren't Vespa attributes
                    if field_name not in self.VESPA_FILTERABLE_FIELDS:
                        continue

                    # Get description from field
                    description = getattr(field_info, "description", None)

                    # Check json_schema_extra for description (used by AirweaveField)
                    if not description and hasattr(field_info, "json_schema_extra"):
                        extra = field_info.json_schema_extra
                        if isinstance(extra, dict):
                            description = extra.get("description")

                    all_fields[field_name] = description or f"{field_name} field"

        # Add system metadata fields from class constant
        all_fields.update(self.NESTED_SYSTEM_FIELDS)

        # Add entity-level timestamp fields (not nested)
        all_fields.update(self.ENTITY_TIMESTAMP_FIELDS)

        return all_fields

    def _build_system_prompt(self, available_fields: Dict[str, Dict[str, str]]) -> str:
        """Build system prompt with available fields."""
        # Format available fields
        fields_description = self._format_available_fields(available_fields)

        # Inject into template
        return QUERY_INTERPRETATION_SYSTEM_PROMPT.format(available_fields=fields_description)

    def _format_available_fields(self, available_fields: Dict[str, Dict[str, str]]) -> str:
        """Format available fields for prompt."""
        lines = []

        # List sources
        sources = list(available_fields.keys())
        lines.append(f"Sources in this collection: {sources}\n")

        # Source-specific fields
        for source, fields in available_fields.items():
            if fields:
                lines.append(f"{source} fields:")
                for fname, desc in sorted(fields.items()):
                    lines.append(f"  - {fname}: {desc}")
                lines.append("")

        return "\n".join(lines)

    def _build_user_prompt(self, query: str, expanded_queries: List[str]) -> str:
        """Build user prompt with query and expansions."""
        all_queries = [query]

        # Add expanded queries if available
        for variant in expanded_queries:
            if variant not in all_queries:
                all_queries.append(variant)

        query_lines = "\n- ".join(all_queries)

        return (
            f"Extract filters from the following search phrasings "
            f"(use ALL to infer constraints).\n"
            f"Consider role/company/location/education/time/source constraints when explicit.\n"
            f"Phrasings (original first):\n"
            f"- {query_lines}"
        )

    def _validate_prompt_length_for_provider(
        self, system_prompt: str, user_prompt: str, provider: BaseProvider
    ) -> None:
        """Validate prompts fit in specific provider's context window.

        This validates against the actual provider that will be used, not a random one.
        """
        tokenizer = getattr(provider, "llm_tokenizer", None)
        if not tokenizer:
            provider_name = provider.__class__.__name__
            raise RuntimeError(
                f"Provider {provider_name} does not have an LLM tokenizer. "
                "Cannot validate prompt length."
            )

        system_tokens = provider.count_tokens(system_prompt, tokenizer)
        user_tokens = provider.count_tokens(user_prompt, tokenizer)

        total_tokens = system_tokens + user_tokens

        if total_tokens > provider.model_spec.llm_model.context_window:
            raise ValueError(
                f"Query interpretation prompts too long for {provider.__class__.__name__}: "
                f"{total_tokens} tokens exceeds context window of "
                f"{provider.model_spec.llm_model.context_window}"
            )

    def _validate_filters(
        self, filters: List[FilterCondition], available_fields: Dict[str, Dict[str, str]]
    ) -> List[Dict[str, Any]]:
        """Validate filter conditions against available fields and convert to Qdrant format."""
        allowed_keys = set()
        allowed_sources = set(available_fields.keys())

        for source_fields in available_fields.values():
            allowed_keys.update(source_fields.keys())

        validated = []
        for condition in filters:
            if condition.key not in allowed_keys:
                continue

            # Skip fields that are not actually filterable as Vespa attributes.
            # Source-specific fields (e.g. title, status) are stored in the payload
            # JSON field and cannot be filtered on directly. Silently dropping these
            # prevents 500 errors from Vespa when the LLM generates filters on them.
            if condition.key not in self.VESPA_FILTERABLE_FIELDS:
                continue

            cond_dict = {"key": self._map_to_qdrant_path(condition.key)}

            if condition.match:
                match_dict = self._convert_match_to_dict(condition.match)
                if condition.key == "source_name":
                    validated_match = self._validate_source_name_match(match_dict, allowed_sources)
                else:
                    validated_match = match_dict

                if not validated_match:
                    continue
                cond_dict["match"] = validated_match

            if condition.range:
                cond_dict["range"] = self._convert_range_to_dict(condition.range)

            validated.append(cond_dict)

        return validated

    def _convert_match_to_dict(self, match: ValueMatch | AnyMatch) -> Dict[str, Any]:
        """Convert match model to Qdrant-compatible dict format."""
        if isinstance(match, ValueMatch):
            return {"value": match.value}
        elif isinstance(match, AnyMatch):
            return {"any": match.any}
        # Fallback for any other match type
        try:
            return match.model_dump(exclude_none=True)  # type: ignore[attr-defined]
        except Exception:
            return {}

    def _convert_range_to_dict(self, range_spec: RangeSpec) -> Dict[str, Any]:
        """Convert range model to Qdrant-compatible dict format."""
        try:
            return range_spec.model_dump(exclude_none=True)
        except Exception:
            return {
                k: v
                for k, v in {
                    "gt": range_spec.gt,
                    "gte": range_spec.gte,
                    "lt": range_spec.lt,
                    "lte": range_spec.lte,
                }.items()
                if v is not None
            }

    def _validate_source_name_match(
        self, match: Dict[str, Any], allowed_sources: set
    ) -> Optional[Dict[str, Any]]:
        """Validate source_name match values against allowed sources.

        Args:
            match: Match dict with 'value' or 'any' key
            allowed_sources: Set of valid source names

        Returns:
            Validated match dict or None if invalid
        """
        if "value" in match:
            return self._validate_single_source_value(match["value"], allowed_sources)

        if "any" in match and isinstance(match["any"], list):
            return self._validate_multiple_source_values(match["any"], allowed_sources)

        return match

    def _validate_single_source_value(
        self, value: Any, allowed_sources: set
    ) -> Optional[Dict[str, Any]]:
        """Validate a single source name value."""
        value_str = str(value)
        if value_str in allowed_sources:
            return {"value": value_str}
        if value_str.lower() in allowed_sources:
            return {"value": value_str.lower()}
        return None

    def _validate_multiple_source_values(
        self, values: List[Any], allowed_sources: set
    ) -> Optional[Dict[str, Any]]:
        """Validate multiple source name values (any-of match)."""
        valid_values = []
        for val in values:
            val_str = str(val)
            if val_str in allowed_sources:
                valid_values.append(val_str)
            elif val_str.lower() in allowed_sources:
                valid_values.append(val_str.lower())

        if not valid_values:
            return None
        if len(valid_values) == 1:
            return {"value": valid_values[0]}
        return {"any": valid_values}

    def _map_to_qdrant_path(self, key: str) -> str:
        """Map field names to Qdrant payload paths."""
        # Already has prefix
        if key.startswith("airweave_system_metadata."):
            return key

        # Needs prefix (from class constant to avoid drift)
        if key in self.NESTED_SYSTEM_FIELDS:
            return f"airweave_system_metadata.{key}"

        # Regular field, no mapping needed
        return key

    def _build_qdrant_filter(self, conditions: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Build Qdrant filter dict from conditions."""
        if not conditions:
            return {}

        return {"must": conditions}
