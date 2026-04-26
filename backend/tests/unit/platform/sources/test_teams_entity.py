"""Unit tests for Microsoft Teams entity sanitization.

Covers the control-character stripping added to fix Vespa ingestion failures
caused by non-printable characters (e.g. ESC/0x1B) in message bodies.
See: https://github.com/airweave-ai/airweave/issues/1269
"""

import pytest

from airweave.platform.entities.teams import TeamsMessageEntity, _sanitize_text


class TestSanitizeText:
    """Tests for the _sanitize_text helper."""

    def test_returns_none_for_none(self):
        assert _sanitize_text(None) is None

    def test_passes_through_plain_text(self):
        assert _sanitize_text("Hello, world!") == "Hello, world!"

    def test_preserves_newline_tab_carriage_return(self):
        text = "line1\nline2\ttabbed\r\n"
        assert _sanitize_text(text) == text

    def test_removes_escape_character(self):
        assert _sanitize_text("text\x1bmore") == "textmore"

    def test_removes_nul_character(self):
        assert _sanitize_text("a\x00b") == "ab"

    def test_removes_multiple_control_chars(self):
        # ESC (\x1b), BEL (\x07), DEL (\x7f) should all be stripped
        assert _sanitize_text("\x1b[31mred\x07\x7f") == "[31mred"

    def test_removes_ansi_escape_sequence_control_byte(self):
        # Real-world case: ANSI colour reset pasted from a terminal
        assert _sanitize_text("normal \x1b[0m text") == "normal [0m text"

    def test_empty_string(self):
        assert _sanitize_text("") == ""


class TestTeamsMessageEntityFromApi:
    """Tests for TeamsMessageEntity.from_api with sanitization."""

    _BASE_DATA = {
        "id": "msg-001",
        "messageType": "message",
        "createdDateTime": "2024-01-15T10:00:00Z",
        "lastModifiedDateTime": "2024-01-15T10:00:00Z",
        "subject": None,
        "importance": "normal",
        "from": {"user": {"displayName": "Alice"}},
        "mentions": [],
        "attachments": [],
        "reactions": [],
        "webUrl": "https://teams.microsoft.com/",
    }

    def _make_data(self, content: str, content_type: str = "text") -> dict:
        return {**self._BASE_DATA, "body": {"content": content, "contentType": content_type}}

    def test_control_chars_stripped_from_body_content(self):
        data = self._make_data("Hello \x1b[31mworld\x1b[0m")
        entity = TeamsMessageEntity.from_api(data, breadcrumbs=[])
        assert "\x1b" not in (entity.body_content or "")
        assert "Hello [31mworld[0m" == entity.body_content

    def test_clean_body_content_unchanged(self):
        data = self._make_data("Plain text with\nnewlines\tand tabs")
        entity = TeamsMessageEntity.from_api(data, breadcrumbs=[])
        assert entity.body_content == "Plain text with\nnewlines\tand tabs"

    def test_name_derived_from_sanitized_body(self):
        # When subject is absent, name is derived from body_content;
        # ensure the name preview also does not contain control chars.
        long_body = "A" * 40 + "\x1b" + "B" * 20
        data = self._make_data(long_body)
        entity = TeamsMessageEntity.from_api(data, breadcrumbs=[])
        assert "\x1b" not in entity.name
