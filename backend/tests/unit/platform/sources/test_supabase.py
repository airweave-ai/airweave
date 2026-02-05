"""Unit tests for Supabase source connector."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from airweave.platform.sources.supabase import SupabaseSource


class TestSupabaseSource:
    """Test suite for Supabase source connector."""

    @pytest.mark.asyncio
    async def test_create_instance(self):
        """Test creating a Supabase source instance."""
        credentials = {
            "project_url": "https://test123.supabase.co",
            "api_key": "test_api_key_1234567890",
        }
        config = {
            "tables": "*",
            "page_size": 500,
            "respect_rls": True,
        }

        source = await SupabaseSource.create(credentials, config)

        assert source.project_url == "https://test123.supabase.co"
        assert source.api_key == "test_api_key_1234567890"
        assert source.page_size == 500
        assert source.respect_rls is True

    @pytest.mark.asyncio
    async def test_create_instance_default_config(self):
        """Test creating instance with default config values."""
        credentials = {
            "project_url": "https://test123.supabase.co/",
            "api_key": "test_api_key_1234567890",
        }

        source = await SupabaseSource.create(credentials)

        assert source.project_url == "https://test123.supabase.co"  # Trailing slash removed
        assert source.page_size == 1000  # Default
        assert source.respect_rls is True  # Default

    def test_get_headers(self):
        """Test HTTP headers generation."""
        source = SupabaseSource()
        source.api_key = "test_key_123"

        headers = source._get_headers()

        assert headers["apikey"] == "test_key_123"
        assert headers["Authorization"] == "Bearer test_key_123"
        assert headers["Content-Type"] == "application/json"
        assert headers["Accept"] == "application/json"

    def test_normalize_model_field_name(self):
        """Test column name normalization."""
        source = SupabaseSource()

        # Test id normalization
        assert source._normalize_model_field_name("id") == "id_"

        # Test reserved field normalization
        assert source._normalize_model_field_name("entity_id") == "entity_id_field"
        assert source._normalize_model_field_name("breadcrumbs") == "breadcrumbs_field"

        # Test normal field
        assert source._normalize_model_field_name("user_name") == "user_name"

    @pytest.mark.asyncio
    async def test_validate_success(self):
        """Test successful validation."""
        source = SupabaseSource()
        source.project_url = "https://test123.supabase.co"
        source.api_key = "test_key"

        mock_response = MagicMock()
        mock_response.status_code = 200

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )

            result = await source.validate()

        assert result is True

    @pytest.mark.asyncio
    async def test_validate_failure(self):
        """Test validation failure."""
        source = SupabaseSource()
        source.project_url = "https://test123.supabase.co"
        source.api_key = "invalid_key"

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                side_effect=Exception("Connection failed")
            )

            result = await source.validate()

        assert result is False

    @pytest.mark.asyncio
    async def test_discover_tables(self):
        """Test table discovery via OpenAPI spec."""
        source = SupabaseSource()
        source.project_url = "https://test123.supabase.co"
        source.api_key = "test_key"

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "definitions": {
                "users": {},
                "posts": {},
                "comments": {},
                "_internal_table": {},  # Should be filtered out
                "pg_stat": {},  # Should be filtered out
            }
        }

        mock_client = MagicMock()
        source._get_with_retry = AsyncMock(return_value=mock_response)

        tables = await source._discover_tables(mock_client)

        assert len(tables) == 3
        assert "users" in tables
        assert "posts" in tables
        assert "comments" in tables
        assert "_internal_table" not in tables
        assert "pg_stat" not in tables

    @pytest.mark.asyncio
    async def test_get_table_schema(self):
        """Test getting table schema information."""
        source = SupabaseSource()
        source.project_url = "https://test123.supabase.co"
        source.api_key = "test_key"

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "definitions": {
                "users": {
                    "properties": {
                        "id": {"type": "integer"},
                        "name": {"type": "string"},
                        "email": {"type": "string"},
                        "is_active": {"type": "boolean"},
                    },
                    "required": ["id", "email"],
                }
            }
        }

        mock_client = MagicMock()
        source._get_with_retry = AsyncMock(return_value=mock_response)

        schema = await source._get_table_schema(mock_client, "users")

        assert "columns" in schema
        assert "primary_keys" in schema
        assert len(schema["columns"]) == 4
        assert schema["columns"]["id"]["python_type"] == int
        assert schema["columns"]["name"]["python_type"] == str
        assert schema["columns"]["is_active"]["python_type"] == bool
        assert schema["primary_keys"] == ["id"]

    @pytest.mark.asyncio
    async def test_create_entity_class(self):
        """Test dynamic entity class creation."""
        source = SupabaseSource()
        source.project_url = "https://test123.supabase.co"
        source.api_key = "test_key"

        mock_schema = {
            "columns": {
                "id": {"python_type": int, "nullable": False, "pg_type": "integer"},
                "name": {"python_type": str, "nullable": True, "pg_type": "text"},
            },
            "primary_keys": ["id"],
        }

        mock_client = MagicMock()
        source._get_table_schema = AsyncMock(return_value=mock_schema)

        entity_class = await source._create_entity_class(mock_client, "users")

        # Verify entity class was created successfully
        assert entity_class is not None
        assert "users" in source.column_field_mappings
        # Verify column mappings exist (exact field names may vary due to normalization)
        assert len(source.column_field_mappings["users"]) == 2
