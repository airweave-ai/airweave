"""Unit tests for EntityTransformer (with simplified mocking)."""

import pytest
from unittest.mock import MagicMock
from uuid import UUID
from datetime import datetime

from airweave.platform.destinations.vespa.transformer import (
    EntityTransformer,
    _sanitize_for_vespa,
    _validate_text_quality,
)
from airweave.platform.destinations.vespa.types import VespaDocument


@pytest.fixture
def transformer():
    """Create EntityTransformer instance."""
    return EntityTransformer()


@pytest.fixture
def mock_entity():
    """Create simplified mock entity."""
    entity = MagicMock()
    # Use actual string/value properties, not mock objects
    type(entity).entity_id = MagicMock(return_value="entity-123")
    type(entity).name = MagicMock(return_value="Test Entity")
    type(entity).textual_representation = MagicMock(return_value="This is test content")
    type(entity).created_at = MagicMock(return_value=datetime(2024, 1, 1, 12, 0, 0))
    type(entity).updated_at = MagicMock(return_value=datetime(2024, 1, 2, 12, 0, 0))
    type(entity).entity_type = MagicMock(return_value="document")
    
    # Set actual values
    entity.entity_id = "entity-123"
    entity.name = "Test Entity"
    entity.textual_representation = "This is test content"
    entity.created_at = datetime(2024, 1, 1, 12, 0, 0)
    entity.updated_at = datetime(2024, 1, 2, 12, 0, 0)
    entity.entity_type = "document"
    
    entity.to_dict.return_value = {
        "entity_id": "entity-123",
        "name": "Test Entity",
        "textual_representation": "This is test content",
    }
    
    # Mock system metadata
    entity.airweave_system_metadata = MagicMock()
    entity.airweave_system_metadata.entity_type = "document"
    entity.airweave_system_metadata.source_name = "TestSource"
    entity.airweave_system_metadata.sync_id = "sync-123"
    entity.airweave_system_metadata.sync_job_id = None
    entity.airweave_system_metadata.hash = "hash-123"
    entity.airweave_system_metadata.collection_id = UUID("12345678-1234-1234-1234-123456789abc")
    entity.airweave_system_metadata.chunk_index = None
    entity.airweave_system_metadata.original_entity_id = "orig-123"
    entity.airweave_system_metadata.dense_embedding = None
    entity.airweave_system_metadata.sparse_embedding = None
    
    # Mock breadcrumbs
    entity.breadcrumbs = []
    
    # Mock access control
    entity.access = MagicMock()
    entity.access.is_public = True
    entity.access.viewers = []
    entity.access.editors = []
    entity.access.owners = []
    
    return entity


@pytest.fixture
def mock_chunk_entity(mock_entity):
    """Create mock chunk entity."""
    mock_entity.airweave_system_metadata.chunk_index = 5
    return mock_entity


class TestEntityTransformer:
    """Test EntityTransformer conversion logic."""

    def test_transform_creates_vespa_document(self, transformer, mock_entity):
        """Test transform creates VespaDocument."""
        result = transformer.transform(mock_entity)
        
        assert isinstance(result, VespaDocument)
        assert result.schema_name == "base_entity"
        assert "entity-123" in result.id

    def test_transform_extracts_core_fields(self, transformer, mock_entity):
        """Test transform extracts core entity fields."""
        result = transformer.transform(mock_entity)
        
        assert result.fields["entity_id"] == "entity-123"
        assert result.fields["name"] == "Test Entity"
        assert result.fields["textual_representation"] == "This is test content"

    def test_transform_converts_timestamps_to_epoch_ms(self, transformer, mock_entity):
        """Test transform converts datetime to epoch milliseconds."""
        result = transformer.transform(mock_entity)
        
        # Should be epoch in milliseconds
        assert "created_at" in result.fields
        assert "updated_at" in result.fields
        assert isinstance(result.fields["created_at"], int)
        assert isinstance(result.fields["updated_at"], int)

    def test_transform_flattens_system_metadata(self, transformer, mock_entity):
        """Test transform flattens system metadata with prefix."""
        result = transformer.transform(mock_entity)
        
        assert result.fields["airweave_system_metadata_entity_type"] == "document"
        assert result.fields["airweave_system_metadata_source_name"] == "TestSource"
        assert result.fields["airweave_system_metadata_sync_id"] == "sync-123"

    def test_transform_flattens_all_metadata_fields(self, transformer, mock_entity):
        """Test transform flattens various metadata fields."""
        result = transformer.transform(mock_entity)
        
        # Check that system metadata is flattened with prefix
        assert "airweave_system_metadata_entity_type" in result.fields
        assert "airweave_system_metadata_source_name" in result.fields
        assert "airweave_system_metadata_sync_id" in result.fields

    def test_transform_chunk_entity_includes_chunk_index(self, transformer, mock_chunk_entity):
        """Test chunk entities include chunk_index."""
        result = transformer.transform(mock_chunk_entity)
        
        # Chunk entities should have chunk_index field
        assert result.fields["airweave_system_metadata_chunk_index"] == 5

    def test_transform_includes_required_base_fields(self, transformer, mock_entity):
        """Test transform includes required base fields."""
        result = transformer.transform(mock_entity)
        
        # Check required fields are present
        assert "entity_id" in result.fields
        assert "name" in result.fields
        assert "textual_representation" in result.fields

    def test_transform_handles_empty_breadcrumbs(self, transformer, mock_entity):
        """Test transform with empty breadcrumbs."""
        mock_entity.breadcrumbs = []
        
        result = transformer.transform(mock_entity)
        
        assert result.fields.get("breadcrumbs", []) == []

    def test_transform_handles_breadcrumbs_list(self, transformer, mock_entity):
        """Test transform with breadcrumbs."""
        mock_breadcrumb = MagicMock()
        mock_breadcrumb.entity_id = "parent-1"
        mock_breadcrumb.name = "Parent Folder"
        mock_breadcrumb.entity_type = "folder"
        mock_breadcrumb.to_dict.return_value = {
            "entity_id": "parent-1",
            "name": "Parent Folder",
            "entity_type": "folder"
        }
        
        mock_entity.breadcrumbs = [mock_breadcrumb]
        
        result = transformer.transform(mock_entity)
        
        assert "breadcrumbs" in result.fields
        assert len(result.fields["breadcrumbs"]) == 1

    def test_transform_includes_access_control_fields(self, transformer, mock_entity):
        """Test transform includes access control fields."""
        result = transformer.transform(mock_entity)
        
        # Should have access fields
        assert "access_is_public" in result.fields
        assert result.fields["access_is_public"] is True

    def test_transform_handles_access_control(self, transformer, mock_entity):
        """Test transform with access control."""
        mock_access = MagicMock()
        mock_access.is_public = False
        mock_access.viewers = ["user1", "user2"]
        mock_access.editors = []
        mock_access.owners = []
        
        mock_entity.access = mock_access
        
        result = transformer.transform(mock_entity)
        
        assert result.fields["access_is_public"] is False
        assert result.fields["access_viewers"] == ["user1", "user2"]

    def test_transform_generates_unique_ids_for_chunks(self, transformer, mock_chunk_entity):
        """Test chunk entities get unique IDs."""
        mock_chunk_entity.airweave_system_metadata.chunk_index = 3
        
        result = transformer.transform(mock_chunk_entity)
        
        # ID should include chunk index
        assert "entity-123" in result.id
        assert "3" in result.id

    def test_transform_batch_processes_multiple_entities(self, transformer):
        """Test transform_batch processes multiple entities."""
        entity1 = MagicMock()
        entity1.id = "e1"
        entity1.entity_type = "document"
        entity1.airweave_system_metadata = MagicMock()
        entity1.airweave_system_metadata.chunk_index = None
        entity1.airweave_system_metadata.entity_type = "document"
        
        entity2 = MagicMock()
        entity2.id = "e2"
        entity2.entity_type = "folder"
        entity2.airweave_system_metadata = MagicMock()
        entity2.airweave_system_metadata.chunk_index = None
        entity2.airweave_system_metadata.entity_type = "folder"
        
        # Mock transform to return simple VespaDocument
        def mock_transform(entity):
            return VespaDocument(
                schema="base_entity",
                id=entity.id,
                fields={"entity_id": entity.id}
            )
        
        transformer.transform = mock_transform
        
        result = transformer.transform_batch([entity1, entity2])
        
        assert "base_entity" in result
        assert len(result["base_entity"]) == 2

    def test_transform_batch_groups_by_schema(self, transformer):
        """Test transform_batch groups documents by schema."""
        entity_regular = MagicMock()
        entity_regular.id = "regular"
        entity_regular.airweave_system_metadata = MagicMock()
        entity_regular.airweave_system_metadata.chunk_index = None
        
        entity_chunk = MagicMock()
        entity_chunk.id = "chunk"
        entity_chunk.airweave_system_metadata = MagicMock()
        entity_chunk.airweave_system_metadata.chunk_index = 2
        
        def mock_transform(entity):
            schema = "chunk_entity" if entity.airweave_system_metadata.chunk_index else "base_entity"
            return VespaDocument(
                schema=schema,
                id=entity.id,
                fields={"entity_id": entity.id}
            )
        
        transformer.transform = mock_transform
        
        result = transformer.transform_batch([entity_regular, entity_chunk])
        
        assert "base_entity" in result
        assert "chunk_entity" in result
        assert len(result["base_entity"]) == 1
        assert len(result["chunk_entity"]) == 1

    def test_transform_handles_none_timestamps(self, transformer, mock_entity):
        """Test transform handles None timestamps gracefully."""
        mock_entity.created_at = None
        mock_entity.updated_at = None
        
        result = transformer.transform(mock_entity)
        
        # Should handle None gracefully
        assert isinstance(result, VespaDocument)

    def test_transform_serializes_payload_to_json(self, transformer, mock_entity):
        """Test payload is serialized to JSON string."""
        result = transformer.transform(mock_entity)
        
        import json
        payload_str = result.fields.get("payload", "{}")
        
        # Should be valid JSON
        try:
            parsed = json.loads(payload_str)
            assert isinstance(parsed, dict)
        except json.JSONDecodeError:
            pytest.fail("Payload is not valid JSON")

    def test_transform_handles_entities_with_special_characters(self, transformer, mock_entity):
        """Test transform handles entity names with special characters."""
        mock_entity.name = "Test \"Entity\" with 'quotes'"
        mock_entity.entity_id = "entity-with-special-chars"
        
        result = transformer.transform(mock_entity)
        
        assert result.fields["name"] == "Test \"Entity\" with 'quotes'"

    def test_transform_batch_empty_list(self, transformer):
        """Test transform_batch with empty list."""
        result = transformer.transform_batch([])
        
        assert isinstance(result, dict)
        assert len(result) == 0

    def test_transform_web_entity_type(self, transformer):
        """Test transform with WebEntity type."""
        from airweave.platform.entities._base import WebEntity
        
        entity = MagicMock()
        entity.entity_id = "web-123"
        entity.name = "Web Page"
        entity.textual_representation = "Content"
        entity.created_at = datetime(2024, 1, 1)
        entity.updated_at = datetime(2024, 1, 1)
        entity.entity_type = "web_page"
        entity.url = "https://example.com"
        entity.breadcrumbs = []
        entity.access = MagicMock()
        entity.access.is_public = True
        entity.access.viewers = []
        entity.access.editors = []
        entity.access.owners = []
        entity.airweave_system_metadata = MagicMock()
        entity.airweave_system_metadata.entity_type = "web_page"
        entity.airweave_system_metadata.source_name = "Web"
        entity.airweave_system_metadata.sync_id = "sync-1"
        entity.airweave_system_metadata.sync_job_id = None
        entity.airweave_system_metadata.hash = "hash-1"
        entity.airweave_system_metadata.collection_id = UUID("12345678-1234-1234-1234-123456789abc")
        entity.airweave_system_metadata.chunk_index = None
        entity.airweave_system_metadata.original_entity_id = "orig-1"
        entity.airweave_system_metadata.dense_embedding = None
        entity.airweave_system_metadata.sparse_embedding = None
        entity.to_dict.return_value = {"entity_id": "web-123", "url": "https://example.com"}
        
        result = transformer.transform(entity)
        
        assert result.fields["entity_id"] == "web-123"
        assert "web-123" in result.id

    def test_transform_file_entity_type(self, transformer):
        """Test transform with FileEntity type."""
        from airweave.platform.entities._base import FileEntity
        
        entity = MagicMock()
        entity.entity_id = "file-123"
        entity.name = "document.pdf"
        entity.textual_representation = "File content"
        entity.created_at = datetime(2024, 1, 1)
        entity.updated_at = datetime(2024, 1, 1)
        entity.entity_type = "file"
        entity.file_path = "/path/to/document.pdf"
        entity.breadcrumbs = []
        entity.access = MagicMock()
        entity.access.is_public = True
        entity.access.viewers = []
        entity.access.editors = []
        entity.access.owners = []
        entity.airweave_system_metadata = MagicMock()
        entity.airweave_system_metadata.entity_type = "file"
        entity.airweave_system_metadata.source_name = "FileSystem"
        entity.airweave_system_metadata.sync_id = "sync-1"
        entity.airweave_system_metadata.sync_job_id = None
        entity.airweave_system_metadata.hash = "hash-1"
        entity.airweave_system_metadata.collection_id = UUID("12345678-1234-1234-1234-123456789abc")
        entity.airweave_system_metadata.chunk_index = None
        entity.airweave_system_metadata.original_entity_id = "orig-1"
        entity.airweave_system_metadata.dense_embedding = None
        entity.airweave_system_metadata.sparse_embedding = None
        entity.to_dict.return_value = {"entity_id": "file-123", "file_path": "/path/to/document.pdf"}
        
        result = transformer.transform(entity)
        
        assert result.fields["entity_id"] == "file-123"
        assert "file-123" in result.id

    def test_transform_code_file_entity_type(self, transformer):
        """Test transform with CodeFileEntity type."""
        from airweave.platform.entities._base import CodeFileEntity
        
        entity = MagicMock()
        entity.entity_id = "code-123"
        entity.name = "main.py"
        entity.textual_representation = "def main(): pass"
        entity.created_at = datetime(2024, 1, 1)
        entity.updated_at = datetime(2024, 1, 1)
        entity.entity_type = "code_file"
        entity.file_path = "/src/main.py"
        entity.language = "python"
        entity.breadcrumbs = []
        entity.access = MagicMock()
        entity.access.is_public = True
        entity.access.viewers = []
        entity.access.editors = []
        entity.access.owners = []
        entity.airweave_system_metadata = MagicMock()
        entity.airweave_system_metadata.entity_type = "code_file"
        entity.airweave_system_metadata.source_name = "GitHub"
        entity.airweave_system_metadata.sync_id = "sync-1"
        entity.airweave_system_metadata.sync_job_id = None
        entity.airweave_system_metadata.hash = "hash-1"
        entity.airweave_system_metadata.collection_id = UUID("12345678-1234-1234-1234-123456789abc")
        entity.airweave_system_metadata.chunk_index = None
        entity.airweave_system_metadata.original_entity_id = "orig-1"
        entity.airweave_system_metadata.dense_embedding = None
        entity.airweave_system_metadata.sparse_embedding = None
        entity.to_dict.return_value = {"entity_id": "code-123", "language": "python"}
        
        result = transformer.transform(entity)
        
        assert result.fields["entity_id"] == "code-123"
        assert "code-123" in result.id

    def test_transform_email_entity_type(self, transformer):
        """Test transform with EmailEntity type."""
        from airweave.platform.entities._base import EmailEntity
        
        entity = MagicMock()
        entity.entity_id = "email-123"
        entity.name = "Important Email"
        entity.textual_representation = "Email body"
        entity.created_at = datetime(2024, 1, 1)
        entity.updated_at = datetime(2024, 1, 1)
        entity.entity_type = "email"
        entity.subject = "Important Email"
        entity.breadcrumbs = []
        entity.access = MagicMock()
        entity.access.is_public = False
        entity.access.viewers = ["user@example.com"]
        entity.access.editors = []
        entity.access.owners = []
        entity.airweave_system_metadata = MagicMock()
        entity.airweave_system_metadata.entity_type = "email"
        entity.airweave_system_metadata.source_name = "Gmail"
        entity.airweave_system_metadata.sync_id = "sync-1"
        entity.airweave_system_metadata.sync_job_id = None
        entity.airweave_system_metadata.hash = "hash-1"
        entity.airweave_system_metadata.collection_id = UUID("12345678-1234-1234-1234-123456789abc")
        entity.airweave_system_metadata.chunk_index = None
        entity.airweave_system_metadata.original_entity_id = "orig-1"
        entity.airweave_system_metadata.dense_embedding = None
        entity.airweave_system_metadata.sparse_embedding = None
        entity.to_dict.return_value = {"entity_id": "email-123", "subject": "Important Email"}
        
        result = transformer.transform(entity)
        
        assert result.fields["entity_id"] == "email-123"
        assert result.fields["access_is_public"] is False
        assert "user@example.com" in result.fields["access_viewers"]


class TestSanitizeForVespa:
    """Test _sanitize_for_vespa function."""

    def test_sanitize_clean_text(self):
        """Test sanitization of clean text."""
        text = "Hello world! This is clean text."
        result = _sanitize_for_vespa(text)
        assert result == text

    def test_sanitize_removes_null_bytes(self):
        """Test removal of null bytes."""
        text = "Hello\x00world"
        result = _sanitize_for_vespa(text)
        assert result == "Helloworld"
        assert "\x00" not in result

    def test_sanitize_removes_control_characters(self):
        """Test removal of control characters."""
        text = "Hello\x01\x02\x03world"
        result = _sanitize_for_vespa(text)
        assert result == "Helloworld"

    def test_sanitize_preserves_newlines(self):
        """Test preservation of newlines."""
        text = "Hello\nworld\r\ntest"
        result = _sanitize_for_vespa(text)
        assert result == text

    def test_sanitize_preserves_tabs(self):
        """Test preservation of tabs."""
        text = "Hello\tworld"
        result = _sanitize_for_vespa(text)
        assert result == text

    def test_sanitize_removes_unicode_noncharacters(self):
        """Test removal of Unicode noncharacters."""
        text = "Hello\ufffeworld\uffff"
        result = _sanitize_for_vespa(text)
        assert result == "Helloworld"

    def test_sanitize_removes_unicode_replacement_in_nonchar_range(self):
        """Test removal of Unicode noncharacters in FDD0-FDEF range."""
        text = "Hello\ufdd0world\ufdef"
        result = _sanitize_for_vespa(text)
        assert result == "Helloworld"

    def test_sanitize_empty_string(self):
        """Test sanitization of empty string."""
        text = ""
        result = _sanitize_for_vespa(text)
        assert result == ""

    def test_sanitize_none(self):
        """Test sanitization of None."""
        result = _sanitize_for_vespa(None)
        assert result is None

    def test_sanitize_unicode_text(self):
        """Test sanitization preserves valid Unicode."""
        text = "Hello 世界 🌍 こんにちは"
        result = _sanitize_for_vespa(text)
        assert result == text


class TestValidateTextQuality:
    """Test _validate_text_quality function."""

    def test_validate_clean_text(self):
        """Test validation of clean text returns None."""
        text = "Hello world! This is clean text."
        result = _validate_text_quality(text, "test-id")
        assert result is None

    def test_validate_empty_text(self):
        """Test validation of empty text returns None."""
        result = _validate_text_quality("", "test-id")
        assert result is None

    def test_validate_none_text(self):
        """Test validation of None returns None."""
        result = _validate_text_quality(None, "test-id")
        assert result is None

    def test_validate_text_with_no_replacement_chars(self):
        """Test text without replacement characters passes."""
        text = "Normal text with Unicode: 世界 🌍"
        result = _validate_text_quality(text, "test-id")
        assert result is None

    def test_validate_text_with_few_replacement_chars(self):
        """Test text with acceptable replacement characters passes."""
        # 10 replacement chars out of 1000 chars = 1% (below 25% threshold)
        text = "Hello" + "\ufffd" * 10 + "world" + "x" * 1000
        result = _validate_text_quality(text, "test-id")
        assert result is None

    def test_validate_text_exceeds_absolute_threshold(self):
        """Test text exceeding 5000 replacement characters fails."""
        text = "Hello" + "\ufffd" * 6000 + "world" + "x" * 100000
        result = _validate_text_quality(text, "test-id")
        assert result is not None
        assert "6000" in result
        assert "replacement characters" in result

    def test_validate_text_exceeds_ratio_threshold(self):
        """Test text exceeding 25% replacement ratio fails."""
        # 100 chars total, 30 replacement (30%)
        text = "\ufffd" * 30 + "x" * 70
        result = _validate_text_quality(text, "test-id")
        assert result is not None
        assert "30" in result
        assert "replacement characters" in result

    def test_validate_text_at_exact_threshold(self):
        """Test text at exactly 5000 replacement chars passes."""
        text = "\ufffd" * 5000 + "x" * 100000
        result = _validate_text_quality(text, "test-id")
        assert result is None

    def test_validate_text_at_exact_ratio_threshold(self):
        """Test text at exactly 25% replacement ratio passes."""
        # 100 chars total, 25 replacement (25%)
        text = "\ufffd" * 25 + "x" * 75
        result = _validate_text_quality(text, "test-id")
        assert result is None

    def test_validate_error_message_includes_stats(self):
        """Test error message includes character counts and ratio."""
        text = "\ufffd" * 6000 + "x" * 2000
        result = _validate_text_quality(text, "test-id")
        assert result is not None
        assert "6000" in result
        assert "8000" in result  # total length
        assert "%" in result  # should include percentage

    def test_validate_100_percent_replacement_chars(self):
        """Test text that is 100% replacement characters fails."""
        text = "\ufffd" * 10000
        result = _validate_text_quality(text, "test-id")
        assert result is not None
        assert "10000" in result


class TestEntityTransformerWithValidation:
    """Test EntityTransformer with text quality validation."""

    def test_transform_rejects_corrupted_text(self):
        """Test transform rejects entity with excessive replacement characters."""
        transformer = EntityTransformer()
        
        entity = MagicMock()
        entity.entity_id = "corrupted-123"
        entity.name = "Corrupted File"
        # Text with 6000 replacement chars out of 8000 total (75%)
        entity.textual_representation = "\ufffd" * 6000 + "x" * 2000
        entity.created_at = datetime(2024, 1, 1)
        entity.updated_at = datetime(2024, 1, 1)
        entity.breadcrumbs = []
        entity.access = MagicMock()
        entity.access.is_public = True
        entity.access.viewers = []
        entity.access.editors = []
        entity.access.owners = []
        entity.airweave_system_metadata = MagicMock()
        entity.airweave_system_metadata.entity_type = "file"
        entity.airweave_system_metadata.source_name = "GoogleDrive"
        entity.airweave_system_metadata.sync_id = "sync-1"
        entity.airweave_system_metadata.sync_job_id = None
        entity.airweave_system_metadata.hash = "hash-1"
        entity.airweave_system_metadata.collection_id = UUID("12345678-1234-1234-1234-123456789abc")
        entity.airweave_system_metadata.chunk_index = None
        entity.airweave_system_metadata.original_entity_id = "orig-1"
        entity.airweave_system_metadata.dense_embedding = None
        entity.airweave_system_metadata.sparse_embedding = None
        entity.to_dict.return_value = {"entity_id": "corrupted-123"}
        
        with pytest.raises(ValueError) as exc_info:
            transformer.transform(entity)
        
        assert "6000" in str(exc_info.value)
        assert "replacement characters" in str(exc_info.value)

    def test_transform_accepts_clean_text(self):
        """Test transform accepts entity with clean text."""
        transformer = EntityTransformer()
        
        entity = MagicMock()
        entity.entity_id = "clean-123"
        entity.name = "Clean File"
        entity.textual_representation = "This is clean text without any corruption."
        entity.created_at = datetime(2024, 1, 1)
        entity.updated_at = datetime(2024, 1, 1)
        entity.breadcrumbs = []
        entity.access = MagicMock()
        entity.access.is_public = True
        entity.access.viewers = []
        entity.access.editors = []
        entity.access.owners = []
        entity.airweave_system_metadata = MagicMock()
        entity.airweave_system_metadata.entity_type = "file"
        entity.airweave_system_metadata.source_name = "GoogleDrive"
        entity.airweave_system_metadata.sync_id = "sync-1"
        entity.airweave_system_metadata.sync_job_id = None
        entity.airweave_system_metadata.hash = "hash-1"
        entity.airweave_system_metadata.collection_id = UUID("12345678-1234-1234-1234-123456789abc")
        entity.airweave_system_metadata.chunk_index = None
        entity.airweave_system_metadata.original_entity_id = "orig-1"
        entity.airweave_system_metadata.dense_embedding = None
        entity.airweave_system_metadata.sparse_embedding = None
        entity.to_dict.return_value = {"entity_id": "clean-123"}
        
        result = transformer.transform(entity)
        
        assert isinstance(result, VespaDocument)
        assert result.fields["textual_representation"] == "This is clean text without any corruption."

