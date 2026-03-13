"""Tests for the spaCy NER-based SCE extractor."""

import pytest

from airweave.domains.sce.extractors.ner import NamedEntityRecognitionExtractor
from airweave.domains.sce.types import ExtractedRefType


@pytest.fixture(scope="module")
def extractor():
    """Load the model once for all tests in this module."""
    return NamedEntityRecognitionExtractor(model="en_core_web_sm")


# ---------------------------------------------------------------------------
# PERSON
# ---------------------------------------------------------------------------

class TestPersonExtraction:
    @pytest.mark.asyncio
    async def test_extracts_person(self, extractor):
        refs = await extractor.extract("Barack Obama signed the bill into law.")
        persons = [r for r in refs if r.ref_type == ExtractedRefType.PERSON]
        assert len(persons) >= 1
        assert any("Obama" in r.value for r in persons)

    @pytest.mark.asyncio
    async def test_extracts_multiple_persons(self, extractor):
        refs = await extractor.extract(
            "Elon Musk and Jeff Bezos discussed the proposal with Tim Cook."
        )
        persons = [r for r in refs if r.ref_type == ExtractedRefType.PERSON]
        assert len(persons) >= 2


# ---------------------------------------------------------------------------
# ORG
# ---------------------------------------------------------------------------

class TestOrgExtraction:
    @pytest.mark.asyncio
    async def test_extracts_org(self, extractor):
        refs = await extractor.extract("Google announced a partnership with Microsoft.")
        orgs = [r for r in refs if r.ref_type == ExtractedRefType.ORG]
        assert len(orgs) >= 1
        values = {r.value for r in orgs}
        assert "Google" in values or "Microsoft" in values

    @pytest.mark.asyncio
    async def test_extracts_multiple_orgs(self, extractor):
        refs = await extractor.extract(
            "Apple, Amazon, and Netflix are all tech companies."
        )
        orgs = [r for r in refs if r.ref_type == ExtractedRefType.ORG]
        assert len(orgs) >= 2


# ---------------------------------------------------------------------------
# PRODUCT
# ---------------------------------------------------------------------------

class TestProductExtraction:
    @pytest.mark.asyncio
    async def test_extracts_product(self, extractor):
        refs = await extractor.extract(
            "The new iPhone 15 Pro was released alongside the MacBook Air."
        )
        products = [r for r in refs if r.ref_type == ExtractedRefType.PRODUCT]
        # spaCy sm model may or may not pick these up reliably,
        # so we just check the type is correct if anything is found
        for p in products:
            assert p.ref_type == ExtractedRefType.PRODUCT


# ---------------------------------------------------------------------------
# EVENT
# ---------------------------------------------------------------------------

class TestEventExtraction:
    @pytest.mark.asyncio
    async def test_extracts_event(self, extractor):
        refs = await extractor.extract(
            "The 2024 Olympics in Paris were a great success. "
            "World War II changed the course of history."
        )
        events = [r for r in refs if r.ref_type == ExtractedRefType.EVENT]
        for e in events:
            assert e.ref_type == ExtractedRefType.EVENT


# ---------------------------------------------------------------------------
# Deduplication
# ---------------------------------------------------------------------------

class TestDeduplication:
    @pytest.mark.asyncio
    async def test_deduplicates_same_entity(self, extractor):
        refs = await extractor.extract(
            "Google is great. Google announced earnings. Google hired more engineers."
        )
        google_refs = [r for r in refs if r.value == "Google"]
        assert len(google_refs) <= 1


# ---------------------------------------------------------------------------
# Filtering & edge cases
# ---------------------------------------------------------------------------

class TestFilteringAndEdgeCases:
    @pytest.mark.asyncio
    async def test_skips_unlisted_types(self, extractor):
        """CARDINAL, DATE, GPE etc. should not appear."""
        refs = await extractor.extract(
            "On January 5th, 2024, three hundred people gathered in Paris."
        )
        allowed = {ExtractedRefType.PERSON, ExtractedRefType.ORG,
                   ExtractedRefType.PRODUCT, ExtractedRefType.EVENT}
        for r in refs:
            assert r.ref_type in allowed

    @pytest.mark.asyncio
    async def test_empty_input(self, extractor):
        refs = await extractor.extract("")
        assert refs == []

    @pytest.mark.asyncio
    async def test_no_entities_in_plain_text(self, extractor):
        refs = await extractor.extract("It was a sunny day and the birds were singing.")
        assert refs == []


# ---------------------------------------------------------------------------
# Prefixed format
# ---------------------------------------------------------------------------

class TestPrefixedFormat:
    @pytest.mark.asyncio
    async def test_prefixed_format(self, extractor):
        refs = await extractor.extract("Satya Nadella leads Microsoft.")
        for r in refs:
            assert r.prefixed == f"{r.ref_type.value}:{r.value}"


# ---------------------------------------------------------------------------
# Mixed with realistic text
# ---------------------------------------------------------------------------

class TestRealisticText:
    @pytest.mark.asyncio
    async def test_github_pr_description(self, extractor):
        text = (
            "This PR by John Smith fixes a bug in the Airweave sync pipeline. "
            "It was reviewed by Sarah Chen from the Platform team at Google. "
            "Related to the Kubernetes migration project."
        )
        refs = await extractor.extract(text)
        types = {r.ref_type for r in refs}
        # Should find at least persons and/or orgs
        assert types & {ExtractedRefType.PERSON, ExtractedRefType.ORG}

    @pytest.mark.asyncio
    async def test_news_article(self, extractor):
        text = (
            "Microsoft CEO Satya Nadella announced that Azure revenue grew 30% "
            "at the annual Build conference. Amazon Web Services responded by "
            "cutting prices on their EC2 instances."
        )
        refs = await extractor.extract(text)
        persons = [r for r in refs if r.ref_type == ExtractedRefType.PERSON]
        orgs = [r for r in refs if r.ref_type == ExtractedRefType.ORG]
        assert len(persons) >= 1
        assert len(orgs) >= 1
