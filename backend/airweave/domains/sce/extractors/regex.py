"""Regex-based reference extractor."""

import re
from typing import Callable, List

from pydantic import BaseModel

from airweave.domains.sce.protocols import ExtractorProtocol
from airweave.domains.sce.types import ExtractedRef, ExtractedRefType


class RegexExtractorType(BaseModel):
    """Configuration for a single regex extraction pattern."""

    ref_type: ExtractedRefType
    pattern: str
    normalizer: Callable[[str], str] | None


URL_EXTRACTOR_TYPE = RegexExtractorType(
    ref_type=ExtractedRefType.URL,
    pattern=r"https?://[^\s<>\"')\]]+",
    normalizer=lambda s: s.rstrip(".,;:!?)"),
)

EMAIL_EXTRACTOR_TYPE = RegexExtractorType(
    ref_type=ExtractedRefType.EMAIL,
    pattern=r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+",
    normalizer=lambda s: s.lower(),
)

MENTION_EXTRACTOR_TYPE = RegexExtractorType(
    ref_type=ExtractedRefType.MENTION,
    pattern=r"(?<!\w)@[a-zA-Z0-9_-]+",
    normalizer=lambda s: s,
)

TICKET_ID_EXTRACTOR_TYPE = RegexExtractorType(
    ref_type=ExtractedRefType.TICKET_ID,
    pattern=r"(?<!&)(?<!\w)[A-Z][A-Z0-9]+-\d+",
    normalizer=lambda s: s,
)

FILE_PATH_EXTRACTOR_TYPE = RegexExtractorType(
    ref_type=ExtractedRefType.FILE_PATH,
    pattern=r"(?<!\S)\.{0,2}/[a-zA-Z0-9_][a-zA-Z0-9_./-]*\.[a-zA-Z0-9]+",
    normalizer=lambda s: s,
)

REGEX_EXTRACTOR_TYPES = [
    URL_EXTRACTOR_TYPE,
    EMAIL_EXTRACTOR_TYPE,
    MENTION_EXTRACTOR_TYPE,
    TICKET_ID_EXTRACTOR_TYPE,
    FILE_PATH_EXTRACTOR_TYPE,
]


class RegexExtractor(ExtractorProtocol):
    """Extract references from text using configurable regex patterns."""

    excluded_entity_types = None

    def __init__(self, extractor_types: List[RegexExtractorType]):
        """Initialize with a list of regex extractor type configurations."""
        self.extractor_types = extractor_types

    def should_extract(self, entity_type: str | None) -> bool:
        """Always extract — regex works on all entity types."""
        return True

    async def extract(self, text: str) -> List[ExtractedRef]:
        """Extract references from text using all configured patterns."""
        extracted_refs = []
        for extractor_type in self.extractor_types:
            refs = [
                ExtractedRef(
                    ref_type=extractor_type.ref_type, value=extractor_type.normalizer(m.group())
                )
                for m in re.compile(extractor_type.pattern).finditer(text)
            ]
            extracted_refs.extend(refs)
        return extracted_refs
