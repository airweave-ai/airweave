"""spaCy NER-based entity extractor."""

import asyncio
from typing import Dict, List

import spacy

from airweave.domains.sce.protocols import ExtractorProtocol
from airweave.domains.sce.types import ExtractedRef, ExtractedRefType


class NamedEntityRecognitionExtractor(ExtractorProtocol):
    """Extract named entities from text using spaCy NER."""

    # spaCy label -> ExtractedRefType mapping
    SPACY_LABEL_MAP: Dict[str, ExtractedRefType] = {
        "PERSON": ExtractedRefType.PERSON,
        # "ORG": ExtractedRefType.ORG,
        "PRODUCT": ExtractedRefType.PRODUCT,
        "EVENT": ExtractedRefType.EVENT,
        "GPE": ExtractedRefType.GPE,
        "DATE": ExtractedRefType.DATE,
    }

    def __init__(
        self,
        model: str = "en_core_web_lg",
        excluded_entity_types: set[str] | None = None,
    ):
        """Initialize with a spaCy model.

        Args:
            model: spaCy model name (e.g. "en_core_web_sm", "en_core_web_md").
            excluded_entity_types: Entity types to skip (e.g. code file classes).
        """
        self._nlp = spacy.load(model, disable=["parser", "lemmatizer"])
        self.excluded_entity_types = excluded_entity_types

    def should_extract(self, entity_type: str | None) -> bool:
        """Check if extraction should run for this entity type."""
        if self.excluded_entity_types is None:
            return True
        return entity_type is not None and entity_type not in self.excluded_entity_types

    async def extract(self, text: str) -> List[ExtractedRef]:
        """Extract named entities from text.

        Runs spaCy in a thread pool since it is CPU-bound.
        """
        doc: spacy.DocJSONSchema = await asyncio.to_thread(self._nlp, text)

        seen: set[str] = set()
        refs: List[ExtractedRef] = []
        for ent in doc.ents:
            ref_type = NamedEntityRecognitionExtractor.SPACY_LABEL_MAP.get(ent.label_)
            if ref_type is None:
                continue

            ref = ExtractedRef(ref_type=ref_type, value=ent.text)
            if ref.prefixed in seen:
                continue
            seen.add(ref.prefixed)

            refs.append(ref)

        return refs
