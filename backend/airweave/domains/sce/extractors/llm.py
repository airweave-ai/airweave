"""LLM-based entity extractor for implicit/semantic references."""

from typing import List

from pydantic import BaseModel

from airweave.domains.sce.protocols import ExtractorProtocol
from airweave.domains.sce.types import ExtractedRef, ExtractedRefType
from airweave.search.agentic_search.external.llm import AgenticSearchLLMInterface

# Allowed ref_type values for the LLM prompt
_ALLOWED_REF_TYPES = [t.value for t in ExtractedRefType]

SYSTEM_PROMPT = f"""\
You extract structured references from enterprise text. Return ONLY references
that pattern-based extractors would miss — focus on:
- People mentioned by role or partial name ("the PM", "our CTO")
- Organizations/teams mentioned indirectly ("the platform team", "vendor")
- Products/projects mentioned by nickname or abbreviation
- Implicit ticket/issue references ("the auth bug", "that PR")
- Dates mentioned relatively ("next sprint", "after the launch")

Each ref must have:
- ref_type: one of {_ALLOWED_REF_TYPES}
- value: the clean, canonical form (not "the Platform team" but "Platform team")

You should extract a ref multiple times IF it appears in the text multiple times.

Do NOT extract:
- URLs, emails, file paths, @mentions (regex handles these)
- Obvious named entities that spaCy would catch (full proper names like "John Smith")
- Generic words or phrases that aren't specific references

Be conservative — fewer high-quality refs are better than many noisy ones.
If there are no implicit references to extract, return an empty list.\
"""


class LLMExtractedItem(BaseModel):
    """A single reference extracted by the LLM."""

    ref_type: str
    value: str


class LLMExtractionResult(BaseModel):
    """Schema for LLM structured output."""

    refs: List[LLMExtractedItem]


class LLMExtractor(ExtractorProtocol):
    """Extract implicit/semantic references using an LLM.

    Complements regex and NER extractors by catching references that require
    language understanding — indirect mentions, abbreviations, contextual
    relationships, and relative dates.
    """

    def __init__(
        self,
        llm: AgenticSearchLLMInterface,
        excluded_entity_types: set[str] | None = None,
        max_text_length: int = 4000,
    ):
        """Initialize with an LLM interface and optional exclusions."""
        self._llm = llm
        self.excluded_entity_types = excluded_entity_types
        self._max_text_length = max_text_length

    def should_extract(self, entity_type: str | None) -> bool:
        """Check if extraction should run for this entity type."""
        if self.excluded_entity_types is None:
            return True
        return (
            entity_type is not None
            and entity_type not in self.excluded_entity_types
        )

    async def extract(self, text: str) -> List[ExtractedRef]:
        """Extract implicit references from text via LLM structured output."""
        truncated = text[: self._max_text_length]

        result = await self._llm.structured_output(
            prompt=truncated,
            schema=LLMExtractionResult,
            system_prompt=SYSTEM_PROMPT,
        )

        refs: List[ExtractedRef] = []
        for item in result.refs:
            if item.ref_type not in _ALLOWED_REF_TYPES:
                continue
            refs.append(ExtractedRef(ref_type=ExtractedRefType(item.ref_type), value=item.value))

        return refs
