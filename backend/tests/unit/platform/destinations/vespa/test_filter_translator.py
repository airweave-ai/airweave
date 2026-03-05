"""Unit tests for Vespa FilterTranslator."""

import pytest
from datetime import datetime

from airweave.platform.destinations.vespa.filter_translator import FilterTranslator, FIELD_NAME_MAP


class TestFilterTranslator:
    """Test FilterTranslator converts Qdrant filters to Vespa YQL."""

    def test_none_filter_returns_none(self, filter_translator):
        """Test that None filter returns None."""
        result = filter_translator.translate(None)
        assert result is None

    def test_empty_filter_returns_empty_string(self, filter_translator):
        """Test that empty filter dict returns empty string."""
        result = filter_translator.translate({})
        assert result == ""

    # =========================================================================
    # Match Conditions
    # =========================================================================

    def test_simple_string_match(self, filter_translator):
        """Test simple string match condition."""
        filter_dict = {
            "must": [
                {"key": "source_name", "match": {"value": "GitHub"}}
            ]
        }
        result = filter_translator.translate(filter_dict)
        assert 'airweave_system_metadata_source_name contains "GitHub"' in result

    def test_match_with_special_characters(self, filter_translator):
        """Test match condition with special chars requiring escaping."""
        filter_dict = {
            "must": [
                {"key": "name", "match": {"value": 'Test "quoted" value'}}
            ]
        }
        result = filter_translator.translate(filter_dict)
        assert r'Test \"quoted\" value' in result

    def test_match_boolean_value(self, filter_translator):
        """Test match condition with boolean value."""
        filter_dict = {
            "must": [
                {"key": "access.is_public", "match": {"value": True}}
            ]
        }
        result = filter_translator.translate(filter_dict)
        assert "access_is_public = true" in result

    def test_match_numeric_value(self, filter_translator):
        """Test match condition with numeric value."""
        filter_dict = {
            "must": [
                {"key": "some_field", "match": {"value": 42}}
            ]
        }
        result = filter_translator.translate(filter_dict)
        assert "some_field = 42" in result

    def test_match_any_operator(self, filter_translator):
        """Test match condition with 'any' operator for array fields."""
        filter_dict = {
            "must": [
                {"key": "access.viewers", "match": {"any": ["user1", "user2", "user3"]}}
            ]
        }
        result = filter_translator.translate(filter_dict)
        assert 'access_viewers contains "user1"' in result
        assert 'access_viewers contains "user2"' in result
        assert 'access_viewers contains "user3"' in result
        assert " OR " in result

    def test_match_any_empty_array(self, filter_translator):
        """Test match any with empty array returns false."""
        filter_dict = {
            "must": [
                {"key": "access.viewers", "match": {"any": []}}
            ]
        }
        result = filter_translator.translate(filter_dict)
        assert "false" in result

    def test_match_except_operator(self, filter_translator):
        """Test match condition with 'except' operator for exclusion."""
        filter_dict = {
            "must": [
                {"key": "source_name", "match": {"except": ["Slack", "Teams"]}}
            ]
        }
        result = filter_translator.translate(filter_dict)
        assert '!(airweave_system_metadata_source_name contains "Slack")' in result
        assert '!(airweave_system_metadata_source_name contains "Teams")' in result
        assert " AND " in result

    def test_match_except_empty_array(self, filter_translator):
        """Test match except with empty array returns true."""
        filter_dict = {
            "must": [
                {"key": "source_name", "match": {"except": []}}
            ]
        }
        result = filter_translator.translate(filter_dict)
        assert "true" in result

    # =========================================================================
    # Range Conditions
    # =========================================================================

    def test_range_greater_than(self, filter_translator):
        """Test range condition with gt operator."""
        filter_dict = {
            "must": [
                {"key": "score", "range": {"gt": 0.5}}
            ]
        }
        result = filter_translator.translate(filter_dict)
        assert "score > 0.5" in result

    def test_range_greater_than_or_equal(self, filter_translator):
        """Test range condition with gte operator."""
        filter_dict = {
            "must": [
                {"key": "score", "range": {"gte": 0.8}}
            ]
        }
        result = filter_translator.translate(filter_dict)
        assert "score >= 0.8" in result

    def test_range_less_than(self, filter_translator):
        """Test range condition with lt operator."""
        filter_dict = {
            "must": [
                {"key": "age", "range": {"lt": 100}}
            ]
        }
        result = filter_translator.translate(filter_dict)
        assert "age < 100" in result

    def test_range_less_than_or_equal(self, filter_translator):
        """Test range condition with lte operator."""
        filter_dict = {
            "must": [
                {"key": "age", "range": {"lte": 50}}
            ]
        }
        result = filter_translator.translate(filter_dict)
        assert "age <= 50" in result

    def test_range_multiple_operators(self, filter_translator):
        """Test range condition with multiple operators."""
        filter_dict = {
            "must": [
                {"key": "score", "range": {"gte": 0.3, "lte": 0.9}}
            ]
        }
        result = filter_translator.translate(filter_dict)
        assert "score >= 0.3" in result
        assert "score <= 0.9" in result
        assert " AND " in result

    def test_range_datetime_conversion(self, filter_translator):
        """Test range condition with datetime string converts to epoch ms."""
        filter_dict = {
            "must": [
                {"key": "created_at", "range": {"gte": "2024-01-01T00:00:00Z"}}
            ]
        }
        result = filter_translator.translate(filter_dict)
        # Should convert to epoch milliseconds
        assert "created_at >=" in result
        assert "1704067200000" in result  # 2024-01-01T00:00:00Z in epoch ms

    # =========================================================================
    # HasId Conditions
    # =========================================================================

    def test_has_id_single_id(self, filter_translator):
        """Test has_id condition with single ID."""
        filter_dict = {
            "must": [
                {"has_id": ["entity-123"]}
            ]
        }
        result = filter_translator.translate(filter_dict)
        assert 'entity_id contains "entity-123"' in result

    def test_has_id_multiple_ids(self, filter_translator):
        """Test has_id condition with multiple IDs."""
        filter_dict = {
            "must": [
                {"has_id": ["id1", "id2", "id3"]}
            ]
        }
        result = filter_translator.translate(filter_dict)
        assert 'entity_id contains "id1"' in result
        assert 'entity_id contains "id2"' in result
        assert 'entity_id contains "id3"' in result
        assert " OR " in result

    def test_has_id_empty_list(self, filter_translator):
        """Test has_id with empty list returns empty string."""
        filter_dict = {
            "must": [
                {"has_id": []}
            ]
        }
        result = filter_translator.translate(filter_dict)
        # Should result in empty condition which gets filtered out
        assert result == "" or "entity_id" not in result

    # =========================================================================
    # IsNull Conditions
    # =========================================================================

    def test_is_null_true(self, filter_translator):
        """Test is_null condition checking for null value."""
        filter_dict = {
            "must": [
                {"key": "some_field", "is_null": True}
            ]
        }
        result = filter_translator.translate(filter_dict)
        assert "isNull(some_field)" in result

    def test_is_null_false(self, filter_translator):
        """Test is_null condition checking for not null."""
        filter_dict = {
            "must": [
                {"key": "some_field", "is_null": False}
            ]
        }
        result = filter_translator.translate(filter_dict)
        assert "!isNull(some_field)" in result

    # =========================================================================
    # IsEmpty Conditions
    # =========================================================================

    def test_is_empty_true(self, filter_translator):
        """Test is_empty condition checking for empty array."""
        filter_dict = {
            "must": [
                {"key": "breadcrumbs", "is_empty": True}
            ]
        }
        result = filter_translator.translate(filter_dict)
        assert "size(breadcrumbs) = 0" in result

    def test_is_empty_false(self, filter_translator):
        """Test is_empty condition checking for non-empty array."""
        filter_dict = {
            "must": [
                {"key": "breadcrumbs", "is_empty": False}
            ]
        }
        result = filter_translator.translate(filter_dict)
        assert "size(breadcrumbs) > 0" in result

    # =========================================================================
    # ValuesCount Conditions
    # =========================================================================

    def test_values_count_single_operator(self, filter_translator):
        """Test values_count condition with single operator."""
        filter_dict = {
            "must": [
                {"key": "tags", "values_count": {"gt": 5}}
            ]
        }
        result = filter_translator.translate(filter_dict)
        assert "size(tags) > 5" in result

    def test_values_count_multiple_operators(self, filter_translator):
        """Test values_count condition with multiple operators."""
        filter_dict = {
            "must": [
                {"key": "tags", "values_count": {"gte": 2, "lte": 10}}
            ]
        }
        result = filter_translator.translate(filter_dict)
        assert "size(tags) >= 2" in result
        assert "size(tags) <= 10" in result
        assert " AND " in result

    # =========================================================================
    # Nested Conditions
    # =========================================================================

    def test_nested_condition_single_must(self, filter_translator):
        """Test nested condition for array field filtering."""
        filter_dict = {
            "must": [
                {
                    "nested": {
                        "key": "breadcrumbs",
                        "filter": {
                            "must": [
                                {"key": "entity_id", "match": {"value": "parent-123"}}
                            ]
                        }
                    }
                }
            ]
        }
        result = filter_translator.translate(filter_dict)
        assert 'breadcrumbs.entity_id contains "parent-123"' in result

    def test_nested_condition_multiple_must(self, filter_translator):
        """Test nested condition with multiple must clauses."""
        filter_dict = {
            "must": [
                {
                    "nested": {
                        "key": "breadcrumbs",
                        "filter": {
                            "must": [
                                {"key": "entity_id", "match": {"value": "id1"}},
                                {"key": "name", "match": {"value": "Folder"}}
                            ]
                        }
                    }
                }
            ]
        }
        result = filter_translator.translate(filter_dict)
        assert 'breadcrumbs.entity_id contains "id1"' in result
        assert 'breadcrumbs.name contains "Folder"' in result
        assert " AND " in result

    def test_nested_condition_should_clauses(self, filter_translator):
        """Test nested condition with should (OR) clauses."""
        filter_dict = {
            "must": [
                {
                    "nested": {
                        "key": "breadcrumbs",
                        "filter": {
                            "should": [
                                {"key": "entity_type", "match": {"value": "folder"}},
                                {"key": "entity_type", "match": {"value": "workspace"}}
                            ]
                        }
                    }
                }
            ]
        }
        result = filter_translator.translate(filter_dict)
        assert 'breadcrumbs.entity_type contains "folder"' in result
        assert 'breadcrumbs.entity_type contains "workspace"' in result
        assert " OR " in result

    # =========================================================================
    # Must/Should/MustNot Combinations
    # =========================================================================

    def test_must_conditions(self, filter_translator):
        """Test multiple must conditions combined with AND."""
        filter_dict = {
            "must": [
                {"key": "source_name", "match": {"value": "GitHub"}},
                {"key": "entity_type", "match": {"value": "issue"}}
            ]
        }
        result = filter_translator.translate(filter_dict)
        assert 'airweave_system_metadata_source_name contains "GitHub"' in result
        assert 'airweave_system_metadata_entity_type contains "issue"' in result
        assert " AND " in result

    def test_should_conditions(self, filter_translator):
        """Test multiple should conditions combined with OR."""
        filter_dict = {
            "should": [
                {"key": "source_name", "match": {"value": "GitHub"}},
                {"key": "source_name", "match": {"value": "GitLab"}}
            ]
        }
        result = filter_translator.translate(filter_dict)
        assert 'airweave_system_metadata_source_name contains "GitHub"' in result
        assert 'airweave_system_metadata_source_name contains "GitLab"' in result
        assert " OR " in result

    def test_must_not_conditions(self, filter_translator):
        """Test must_not conditions negated."""
        filter_dict = {
            "must_not": [
                {"key": "source_name", "match": {"value": "Slack"}},
                {"key": "entity_type", "match": {"value": "draft"}}
            ]
        }
        result = filter_translator.translate(filter_dict)
        assert 'airweave_system_metadata_source_name contains "Slack"' in result
        assert 'airweave_system_metadata_entity_type contains "draft"' in result
        assert "!(" in result
        assert " AND " in result

    def test_combined_must_should_must_not(self, filter_translator):
        """Test complex filter with must, should, and must_not."""
        filter_dict = {
            "must": [
                {"key": "collection_id", "match": {"value": "col-123"}}
            ],
            "should": [
                {"key": "source_name", "match": {"value": "GitHub"}},
                {"key": "source_name", "match": {"value": "GitLab"}}
            ],
            "must_not": [
                {"key": "entity_type", "match": {"value": "archived"}}
            ]
        }
        result = filter_translator.translate(filter_dict)
        # All three sections should be present and combined with AND
        assert 'airweave_system_metadata_collection_id contains "col-123"' in result
        assert 'airweave_system_metadata_source_name contains "GitHub"' in result
        assert " OR " in result  # From should clause
        assert 'airweave_system_metadata_entity_type contains "archived"' in result
        assert "!(" in result  # From must_not
        # Top level should be AND of all three
        parts = result.split(" AND ")
        assert len(parts) == 3

    # =========================================================================
    # Nested Filter (Recursive)
    # =========================================================================

    def test_nested_filter_dict(self, filter_translator):
        """Test recursive nested filter handling."""
        filter_dict = {
            "must": [
                {
                    "must": [
                        {"key": "field1", "match": {"value": "value1"}}
                    ],
                    "should": [
                        {"key": "field2", "match": {"value": "value2"}},
                        {"key": "field3", "match": {"value": "value3"}}
                    ]
                }
            ]
        }
        result = filter_translator.translate(filter_dict)
        assert 'field1 contains "value1"' in result
        assert 'field2 contains "value2"' in result
        assert 'field3 contains "value3"' in result
        assert " OR " in result  # From nested should
        assert " AND " in result  # From nested must

    # =========================================================================
    # Field Name Mapping
    # =========================================================================

    def test_field_name_mapping_short_form(self, filter_translator):
        """Test field name mapping from short form to Vespa field."""
        filter_dict = {
            "must": [
                {"key": "collection_id", "match": {"value": "col-123"}}
            ]
        }
        result = filter_translator.translate(filter_dict)
        assert "airweave_system_metadata_collection_id" in result

    def test_field_name_mapping_dotted_form(self, filter_translator):
        """Test field name mapping from dotted notation."""
        filter_dict = {
            "must": [
                {"key": "airweave_system_metadata.sync_id", "match": {"value": "sync-123"}}
            ]
        }
        result = filter_translator.translate(filter_dict)
        assert "airweave_system_metadata_sync_id" in result

    def test_field_name_mapping_access_control(self, filter_translator):
        """Test access control field mapping."""
        filter_dict = {
            "must": [
                {"key": "access.is_public", "match": {"value": True}},
                {"key": "access.viewers", "match": {"any": ["user1"]}}
            ]
        }
        result = filter_translator.translate(filter_dict)
        assert "access_is_public" in result
        assert "access_viewers" in result

    def test_unmapped_field_passthrough(self, filter_translator):
        """Test that unmapped fields pass through unchanged."""
        filter_dict = {
            "must": [
                {"key": "custom_field", "match": {"value": "custom_value"}}
            ]
        }
        result = filter_translator.translate(filter_dict)
        assert 'custom_field contains "custom_value"' in result

    # =========================================================================
    # Edge Cases and Error Handling
    # =========================================================================

    def test_unknown_condition_type_skipped(self, filter_translator):
        """Test that unknown condition types are skipped gracefully."""
        filter_dict = {
            "must": [
                {"unknown_key": "unknown_value"}
            ]
        }
        result = filter_translator.translate(filter_dict)
        # Should return empty or minimal result, not crash
        assert isinstance(result, str)

    def test_pydantic_model_input(self, filter_translator):
        """Test that Pydantic models are converted to dicts."""
        class MockFilter:
            def model_dump(self, exclude_none=True):
                return {
                    "must": [
                        {"key": "source_name", "match": {"value": "GitHub"}}
                    ]
                }
        
        mock_filter = MockFilter()
        result = filter_translator.translate(mock_filter)
        assert 'airweave_system_metadata_source_name contains "GitHub"' in result

    def test_invalid_datetime_handled_gracefully(self, filter_translator):
        """Test that invalid datetime strings don't crash."""
        filter_dict = {
            "must": [
                {"key": "created_at", "range": {"gte": "not-a-datetime"}}
            ]
        }
        # Should not crash, will log warning
        result = filter_translator.translate(filter_dict)
        assert isinstance(result, str)

    def test_yql_value_escaping(self, filter_translator):
        """Test YQL value escaping for special characters."""
        filter_dict = {
            "must": [
                {"key": "name", "match": {"value": 'Test\\Path"Quote'}}
            ]
        }
        result = filter_translator.translate(filter_dict)
        # Both backslashes and quotes should be escaped
        assert r'Test\\Path\"Quote' in result or 'Test\\\\Path\\"Quote' in result


class TestFieldNameMapping:
    """Test FIELD_NAME_MAP constants."""

    def test_field_name_map_has_expected_mappings(self):
        """Verify key mappings exist in FIELD_NAME_MAP."""
        assert "collection_id" in FIELD_NAME_MAP
        assert "entity_type" in FIELD_NAME_MAP
        assert "source_name" in FIELD_NAME_MAP
        assert "access.is_public" in FIELD_NAME_MAP
        assert "access.viewers" in FIELD_NAME_MAP

    def test_field_name_map_values_correct(self):
        """Verify field name mapping values."""
        assert FIELD_NAME_MAP["collection_id"] == "airweave_system_metadata_collection_id"
        assert FIELD_NAME_MAP["source_name"] == "airweave_system_metadata_source_name"
        assert FIELD_NAME_MAP["access.is_public"] == "access_is_public"

