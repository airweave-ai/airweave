"""Tests for the regex-based SCE extractors."""

import pytest

from airweave.platform.sce.extractors.regex import (
    RegexExtractor,
    RegexExtractorType,
    URL_EXTRACTOR_TYPE,
    EMAIL_EXTRACTOR_TYPE,
    MENTION_EXTRACTOR_TYPE,
    TICKET_ID_EXTRACTOR_TYPE,
    FILE_PATH_EXTRACTOR_TYPE,
    REGEX_EXTRACTOR_TYPES,
)
from airweave.platform.sce.types import ExtractedRefType


def _make_extractor(*types: RegexExtractorType) -> RegexExtractor:
    return RegexExtractor(extractor_types=list(types))


# ---------------------------------------------------------------------------
# URL
# ---------------------------------------------------------------------------

class TestURLExtractor:
    @pytest.mark.asyncio
    async def test_extracts_https_links(self):
        ext = _make_extractor(URL_EXTRACTOR_TYPE)
        refs = await ext.extract("Visit https://example.com/page for info")
        assert len(refs) == 1
        assert refs[0].value == "https://example.com/page"
        assert refs[0].ref_type == ExtractedRefType.URL

    @pytest.mark.asyncio
    async def test_strips_trailing_punctuation(self):
        ext = _make_extractor(URL_EXTRACTOR_TYPE)
        refs = await ext.extract("See https://example.com/page.")
        assert refs[0].value == "https://example.com/page"

    @pytest.mark.asyncio
    async def test_multiple_urls(self):
        ext = _make_extractor(URL_EXTRACTOR_TYPE)
        refs = await ext.extract("https://a.com and https://b.com")
        assert len(refs) == 2
        values = {r.value for r in refs}
        assert values == {"https://a.com", "https://b.com"}

    @pytest.mark.asyncio
    async def test_empty_input(self):
        ext = _make_extractor(URL_EXTRACTOR_TYPE)
        refs = await ext.extract("")
        assert refs == []


# ---------------------------------------------------------------------------
# EMAIL
# ---------------------------------------------------------------------------

class TestEmailExtractor:
    @pytest.mark.asyncio
    async def test_extracts_email(self):
        ext = _make_extractor(EMAIL_EXTRACTOR_TYPE)
        refs = await ext.extract("Contact Alice@Example.COM for help")
        assert len(refs) == 1
        assert refs[0].value == "alice@example.com"
        assert refs[0].ref_type == ExtractedRefType.EMAIL

    @pytest.mark.asyncio
    async def test_lowercases(self):
        ext = _make_extractor(EMAIL_EXTRACTOR_TYPE)
        refs = await ext.extract("BOB@CORP.IO")
        assert refs[0].value == "bob@corp.io"

    @pytest.mark.asyncio
    async def test_empty_input(self):
        ext = _make_extractor(EMAIL_EXTRACTOR_TYPE)
        refs = await ext.extract("")
        assert refs == []


# ---------------------------------------------------------------------------
# MENTION
# ---------------------------------------------------------------------------

class TestMentionExtractor:
    @pytest.mark.asyncio
    async def test_extracts_mention(self):
        ext = _make_extractor(MENTION_EXTRACTOR_TYPE)
        refs = await ext.extract("Hey @alice please review")
        assert len(refs) == 1
        assert refs[0].value == "@alice"
        assert refs[0].ref_type == ExtractedRefType.MENTION

    @pytest.mark.asyncio
    async def test_skips_email_at(self):
        ext = _make_extractor(MENTION_EXTRACTOR_TYPE)
        refs = await ext.extract("email bob@domain.com")
        assert refs == []

    @pytest.mark.asyncio
    async def test_multiple_mentions(self):
        ext = _make_extractor(MENTION_EXTRACTOR_TYPE)
        refs = await ext.extract("@alice and @bob")
        assert len(refs) == 2
        values = {r.value for r in refs}
        assert values == {"@alice", "@bob"}


# ---------------------------------------------------------------------------
# TICKET_ID
# ---------------------------------------------------------------------------

class TestTicketIdExtractor:
    @pytest.mark.asyncio
    async def test_extracts_ticket(self):
        ext = _make_extractor(TICKET_ID_EXTRACTOR_TYPE)
        refs = await ext.extract("Fixed in ENG-456")
        assert len(refs) == 1
        assert refs[0].value == "ENG-456"
        assert refs[0].ref_type == ExtractedRefType.TICKET_ID

    @pytest.mark.asyncio
    async def test_requires_uppercase(self):
        ext = _make_extractor(TICKET_ID_EXTRACTOR_TYPE)
        refs = await ext.extract("eng-456 should not match")
        assert refs == []

    @pytest.mark.asyncio
    async def test_skips_html_entities(self):
        ext = _make_extractor(TICKET_ID_EXTRACTOR_TYPE)
        refs = await ext.extract("code &#123; not a ticket")
        assert refs == []


# ---------------------------------------------------------------------------
# FILE_PATH
# ---------------------------------------------------------------------------

class TestFilePathExtractor:
    @pytest.mark.asyncio
    async def test_extracts_absolute_path(self):
        ext = _make_extractor(FILE_PATH_EXTRACTOR_TYPE)
        refs = await ext.extract("See /src/file.py for details")
        assert len(refs) == 1
        assert refs[0].value == "/src/file.py"
        assert refs[0].ref_type == ExtractedRefType.FILE_PATH

    @pytest.mark.asyncio
    async def test_extracts_relative_path(self):
        ext = _make_extractor(FILE_PATH_EXTRACTOR_TYPE)
        refs = await ext.extract("Edit ./relative.yaml")
        assert len(refs) == 1
        assert refs[0].value == "./relative.yaml"

    @pytest.mark.asyncio
    async def test_empty_input(self):
        ext = _make_extractor(FILE_PATH_EXTRACTOR_TYPE)
        refs = await ext.extract("")
        assert refs == []


# ---------------------------------------------------------------------------
# Cross-cutting: ref_type correctness & empty-string contract
# ---------------------------------------------------------------------------

class TestRefTypeAndEmptyContract:
    @pytest.mark.asyncio
    async def test_empty_string_returns_empty_list_for_all(self):
        ext = _make_extractor(*REGEX_EXTRACTOR_TYPES)
        refs = await ext.extract("")
        assert refs == []

    @pytest.mark.asyncio
    async def test_correct_ref_types_on_returned_refs(self):
        ext = _make_extractor(URL_EXTRACTOR_TYPE, EMAIL_EXTRACTOR_TYPE)
        refs = await ext.extract("https://x.com alice@b.com")
        types = {r.ref_type for r in refs}
        assert ExtractedRefType.URL in types
        assert ExtractedRefType.EMAIL in types

    @pytest.mark.asyncio
    async def test_mixed_types_and_multiple_occurrences(self):
        ext = _make_extractor(*REGEX_EXTRACTOR_TYPES)
        text = (
            "Hey @alice, ticket ENG-123 is fixed in https://github.com/org/repo/pull/42. "
            "Also see ENG-789 and https://docs.example.com/guide. "
            "Details in /src/main.py — ping @bob or email support@acme.com for questions."
        )
        refs = await ext.extract(text)

        by_type = {}
        for r in refs:
            by_type.setdefault(r.ref_type, []).append(r.value)

        assert set(by_type[ExtractedRefType.URL]) == {
            "https://github.com/org/repo/pull/42",
            "https://docs.example.com/guide",
        }
        assert by_type[ExtractedRefType.EMAIL] == ["support@acme.com"]
        assert set(by_type[ExtractedRefType.MENTION]) == {"@alice", "@bob"}
        assert set(by_type[ExtractedRefType.TICKET_ID]) == {"ENG-123", "ENG-789"}
        assert by_type[ExtractedRefType.FILE_PATH] == ["/src/main.py"]

        # All five ref types present
        assert set(by_type.keys()) == set(ExtractedRefType)
