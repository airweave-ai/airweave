"""Tests for the SCE orchestration service."""

import pytest

from airweave.platform.sce.service import StructuralContextExtractorService
from airweave.platform.sce.types import (
    EntityAnnotations,
    EntityExtractionInput,
    ExtractedRef,
    ExtractedRefType,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class StubExtractor:
    """Extractor that returns a fixed list of refs."""

    def __init__(self, refs: list[ExtractedRef]):
        self._refs = refs

    async def extract(self, text: str) -> list[ExtractedRef]:
        return list(self._refs)


def _ref(ref_type: ExtractedRefType, value: str) -> ExtractedRef:
    return ExtractedRef(ref_type=ref_type, value=value)


def _input(entity_id: str, text: str = "") -> EntityExtractionInput:
    return EntityExtractionInput(entity_id=entity_id, text=text)


# ---------------------------------------------------------------------------
# extract()
# ---------------------------------------------------------------------------

class TestExtract:
    @pytest.mark.asyncio
    async def test_two_extractors_different_refs(self):
        e1 = StubExtractor([_ref(ExtractedRefType.URL, "https://a.com")])
        e2 = StubExtractor([_ref(ExtractedRefType.EMAIL, "a@b.com")])
        svc = StructuralContextExtractorService(extractors=[e1, e2])

        refs = await svc.extract(_input("e1", "ignored"))
        assert len(refs) == 2
        values = {r.value for r in refs}
        assert values == {"https://a.com", "a@b.com"}

    @pytest.mark.asyncio
    async def test_duplicate_ref_deduplicated(self):
        dup = _ref(ExtractedRefType.URL, "https://dup.com")
        e1 = StubExtractor([dup])
        e2 = StubExtractor([dup])
        svc = StructuralContextExtractorService(extractors=[e1, e2])

        refs = await svc.extract(_input("e1", "ignored"))
        assert len(refs) == 1

    @pytest.mark.asyncio
    async def test_same_value_different_type_both_kept(self):
        e1 = StubExtractor([_ref(ExtractedRefType.URL, "foo")])
        e2 = StubExtractor([_ref(ExtractedRefType.EMAIL, "foo")])
        svc = StructuralContextExtractorService(extractors=[e1, e2])

        refs = await svc.extract(_input("e1", "ignored"))
        assert len(refs) == 2

    @pytest.mark.asyncio
    async def test_all_extractors_empty(self):
        e1 = StubExtractor([])
        e2 = StubExtractor([])
        svc = StructuralContextExtractorService(extractors=[e1, e2])

        refs = await svc.extract(_input("e1", "ignored"))
        assert refs == []


# ---------------------------------------------------------------------------
# process_entities()
# ---------------------------------------------------------------------------

class TestProcessEntities:
    @pytest.mark.asyncio
    async def test_three_inputs_yield_three_annotations(self):
        stub = StubExtractor([_ref(ExtractedRefType.URL, "https://x.com")])
        svc = StructuralContextExtractorService(extractors=[stub])

        inputs = [_input("a"), _input("b"), _input("c")]
        results = [ann async for ann in svc.process_entities(inputs)]

        assert len(results) == 3
        assert [r.entity_id for r in results] == ["a", "b", "c"]
        for r in results:
            assert isinstance(r, EntityAnnotations)

    @pytest.mark.asyncio
    async def test_empty_list_yields_nothing(self):
        svc = StructuralContextExtractorService(extractors=[StubExtractor([])])
        results = [ann async for ann in svc.process_entities([])]
        assert results == []

    @pytest.mark.asyncio
    async def test_entity_with_no_refs(self):
        svc = StructuralContextExtractorService(extractors=[StubExtractor([])])
        results = [ann async for ann in svc.process_entities([_input("lonely")])]
        assert len(results) == 1
        assert results[0].entity_id == "lonely"
        assert results[0].refs == []

    @pytest.mark.asyncio
    async def test_ordering_preserved(self):
        stub = StubExtractor([_ref(ExtractedRefType.MENTION, "@x")])
        svc = StructuralContextExtractorService(extractors=[stub])

        ids = ["z", "a", "m", "b"]
        inputs = [_input(i) for i in ids]
        results = [ann async for ann in svc.process_entities(inputs)]
        assert [r.entity_id for r in results] == ids
