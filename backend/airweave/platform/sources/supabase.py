"""Supabase source implementation.

Connects to Supabase databases via the PostgREST API to extract table data.
Supabase auto-generates REST endpoints from PostgreSQL schemas using PostgREST.

References:
    https://supabase.com/docs/guides/api
    https://postgrest.org/en/stable/
"""

from typing import Any, AsyncGenerator, Dict, List, Optional, Type

import httpx
from tenacity import retry, stop_after_attempt

from airweave.core.shared_models import RateLimitLevel
from airweave.platform.decorators import source
from airweave.platform.entities._base import BaseEntity, PolymorphicEntity
from airweave.platform.sources._base import BaseSource
from airweave.platform.sources.retry_helpers import (
    retry_if_rate_limit_or_timeout,
    wait_rate_limit_with_backoff,
)
from airweave.schemas.source_connection import AuthenticationMethod

# Mapping of PostgreSQL/Supabase types to Python types
SUPABASE_TYPE_MAP = {
    "integer": int,
    "bigint": int,
    "smallint": int,
    "decimal": float,
    "numeric": float,
    "real": float,
    "double precision": float,
    "character varying": str,
    "character": str,
    "text": str,
    "boolean": bool,
    "timestamp": str,
    "timestamp with time zone": str,
    "date": str,
    "time": str,
    "json": Any,
    "jsonb": Any,
    "uuid": str,
}


@source(
    name="Supabase",
    short_name="supabase",
    auth_methods=[AuthenticationMethod.DIRECT, AuthenticationMethod.AUTH_PROVIDER],
    oauth_type=None,
    auth_config_class="SupabaseAuthConfig",
    config_class="SupabaseConfig",
    labels=["Database", "Backend"],
    rate_limit_level=RateLimitLevel.ORG,
)
class SupabaseSource(BaseSource):
    """Supabase source connector for extracting data via PostgREST API.

    Connects to Supabase projects using the auto-generated REST API,
    respecting Row Level Security policies and providing efficient pagination.
    """

    _RESERVED_ENTITY_FIELDS = {
        "entity_id",
        "breadcrumbs",
        "name",
        "created_at",
        "updated_at",
        "textual_representation",
        "airweave_system_metadata",
        "schema_name",
        "table_name",
        "primary_key_columns",
    }

    def __init__(self):
        """Initialize the Supabase source."""
        super().__init__()
        self.entity_classes: Dict[str, Type[PolymorphicEntity]] = {}
        self.column_field_mappings: Dict[str, Dict[str, str]] = {}

    @classmethod
    async def create(
        cls, credentials: Dict[str, Any], config: Optional[Dict[str, Any]] = None
    ) -> "SupabaseSource":
        """Create a new Supabase source instance.

        Args:
            credentials: Dictionary containing:
                - project_url: Supabase project URL (e.g., https://abc123.supabase.co)
                - api_key: Supabase API key (anon or service_role)
            config: Optional configuration parameters.
        """
        instance = cls()
        instance.config = (
            credentials.model_dump() if hasattr(credentials, "model_dump") else dict(credentials)
        )
        instance.project_url = instance.config["project_url"].rstrip("/")
        instance.api_key = instance.config["api_key"]
        instance.page_size = config.get("page_size", 1000) if config else 1000
        instance.respect_rls = config.get("respect_rls", True) if config else True
        return instance

    def _get_headers(self) -> Dict[str, str]:
        """Get HTTP headers for Supabase API requests."""
        return {
            "apikey": self.api_key,
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def _normalize_model_field_name(self, column_name: str) -> str:
        """Normalize column names to avoid collisions with entity base fields."""
        if column_name == "id":
            return "id_"
        if column_name in self._RESERVED_ENTITY_FIELDS:
            return f"{column_name}_field"
        return column_name

    async def validate(self) -> bool:
        """Validate connection by checking API accessibility."""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"{self.project_url}/rest/v1/",
                    headers=self._get_headers()
                )
                return response.status_code == 200
        except Exception as e:
            self.logger.error(f"Validation failed: {e}")
            return False

    @retry(
        stop=stop_after_attempt(5),
        retry=retry_if_rate_limit_or_timeout,
        wait=wait_rate_limit_with_backoff,
        reraise=True,
    )
    async def _get_with_retry(
        self, client: httpx.AsyncClient, url: str, headers: Dict[str, str]
    ) -> httpx.Response:
        """Make GET request with retry logic."""
        response = await client.get(url, headers=headers, timeout=30.0)
        response.raise_for_status()
        return response

    async def _discover_tables(self, client: httpx.AsyncClient) -> List[str]:
        """Discover available tables via PostgREST OpenAPI spec.

        Returns:
            List of table names
        """
        try:
            response = await self._get_with_retry(
                client,
                f"{self.project_url}/rest/v1/",
                self._get_headers()
            )

            # PostgREST returns OpenAPI spec with table definitions
            spec = response.json()
            definitions = spec.get("definitions", {})

            # Filter out internal tables and get table names
            tables = [
                name for name in definitions.keys()
                if not name.startswith("_") and not name.startswith("pg_")
            ]

            self.logger.info(f"Discovered {len(tables)} tables")
            return tables

        except Exception as e:
            self.logger.error(f"Failed to discover tables: {e}")
            raise

    async def _get_table_schema(
        self, client: httpx.AsyncClient, table: str
    ) -> Dict[str, Any]:
        """Get table schema information.

        Args:
            client: HTTP client
            table: Table name

        Returns:
            Dictionary with column information and primary keys
        """
        try:
            # Fetch OpenAPI spec to get table schema
            response = await self._get_with_retry(
                client,
                f"{self.project_url}/rest/v1/",
                self._get_headers()
            )

            spec = response.json()
            table_def = spec.get("definitions", {}).get(table, {})
            properties = table_def.get("properties", {})
            required = table_def.get("required", [])

            # Build column metadata
            columns = {}
            for col_name, col_spec in properties.items():
                pg_type = col_spec.get("type", "text")
                # Map JSON schema types to PostgreSQL types
                if pg_type == "string":
                    if col_spec.get("format") == "uuid":
                        pg_type = "uuid"
                    else:
                        pg_type = "text"
                elif pg_type == "integer":
                    pg_type = "integer"
                elif pg_type == "number":
                    pg_type = "numeric"
                elif pg_type == "boolean":
                    pg_type = "boolean"

                python_type = SUPABASE_TYPE_MAP.get(pg_type, Any)

                columns[col_name] = {
                    "python_type": python_type,
                    "nullable": col_name not in required,
                    "pg_type": pg_type,
                }

            # Try to infer primary keys (common patterns)
            primary_keys = []
            if "id" in columns:
                primary_keys = ["id"]
            elif "uuid" in columns:
                primary_keys = ["uuid"]
            else:
                # Use first column as fallback
                primary_keys = [list(columns.keys())[0]] if columns else []

            return {
                "columns": columns,
                "primary_keys": primary_keys,
            }

        except Exception as e:
            self.logger.error(f"Failed to get schema for table {table}: {e}")
            raise

    async def _create_entity_class(
        self, client: httpx.AsyncClient, table: str
    ) -> Type[PolymorphicEntity]:
        """Create entity class for a table.

        Args:
            client: HTTP client
            table: Table name

        Returns:
            Dynamically created entity class
        """
        schema_info = await self._get_table_schema(client, table)

        # Normalize column names
        normalized_columns: Dict[str, Dict[str, Any]] = {}
        column_mapping: Dict[str, str] = {}

        for original_name, column_meta in schema_info["columns"].items():
            base_name = self._normalize_model_field_name(original_name)
            candidate = base_name
            suffix = 1
            while candidate in normalized_columns:
                suffix += 1
                candidate = f"{base_name}_{suffix}"
            normalized_columns[candidate] = column_meta
            column_mapping[original_name] = candidate

        self.column_field_mappings[table] = column_mapping

        return PolymorphicEntity.create_table_entity_class(
            table_name=table,
            schema_name="public",  # Supabase default schema
            columns=normalized_columns,
            primary_keys=schema_info["primary_keys"],
        )

    async def _fetch_table_data(
        self,
        client: httpx.AsyncClient,
        table: str,
        entity_class: Type[PolymorphicEntity],
    ) -> AsyncGenerator[BaseEntity, None]:
        """Fetch data from a table with pagination.

        Args:
            client: HTTP client
            table: Table name
            entity_class: Entity class for the table

        Yields:
            Entities from the table
        """
        offset = 0
        total_fetched = 0
        primary_keys = entity_class.model_fields["primary_key_columns"].default_factory()

        while True:
            try:
                # PostgREST uses Range headers for pagination
                headers = self._get_headers()
                headers["Range"] = f"{offset}-{offset + self.page_size - 1}"

                response = await self._get_with_retry(
                    client,
                    f"{self.project_url}/rest/v1/{table}",
                    headers
                )

                records = response.json()

                if not records:
                    break

                # Process each record
                for record in records:
                    # Generate entity ID
                    pk_values = [str(record.get(pk, "")) for pk in primary_keys]
                    if pk_values:
                        entity_id = f"{table}:" + ":".join(pk_values)
                    else:
                        entity_id = f"{table}:unknown"

                    # Map columns to normalized field names
                    processed_data = {}
                    column_mapping = self.column_field_mappings.get(table, {})

                    for col_name, value in record.items():
                        field_name = column_mapping.get(col_name, col_name)
                        if field_name in entity_class.model_fields:
                            processed_data[field_name] = value

                    # Determine entity name
                    entity_name = record.get("name") or record.get("title") or table

                    yield entity_class(
                        entity_id=entity_id,
                        breadcrumbs=[],
                        name=str(entity_name),
                        created_at=None,
                        updated_at=None,
                        **processed_data,
                    )

                    total_fetched += 1

                # Check if we've fetched all records
                content_range = response.headers.get("Content-Range")
                if content_range:
                    # Format: "0-999/5000" or "0-999/*"
                    parts = content_range.split("/")
                    if len(parts) == 2 and parts[1] != "*":
                        total = int(parts[1])
                        if total_fetched >= total:
                            break

                # If we got fewer records than page size, we're done
                if len(records) < self.page_size:
                    break

                offset += self.page_size

                if total_fetched % 1000 == 0:
                    self.logger.info(f"Table {table}: Fetched {total_fetched} records")

            except httpx.HTTPStatusError as e:
                if e.response.status_code in (401, 403) and self.respect_rls:
                    self.logger.warning(
                        f"Table {table} is protected by RLS. Skipping (respect_rls=True)."
                    )
                    break
                raise

        self.logger.info(f"Table {table}: Completed, {total_fetched} total records")

    async def generate_entities(self) -> AsyncGenerator[BaseEntity, None]:
        """Generate entities for all tables in the Supabase project."""
        async with httpx.AsyncClient(timeout=60.0) as client:
            # Discover tables
            tables = await self._discover_tables(client)

            # Filter tables based on config
            tables_config = self.config.get("tables", "*") or "*"
            if tables_config != "*":
                requested_tables = [t.strip() for t in tables_config.split(",") if t.strip()]
                tables = [t for t in tables if t in requested_tables]

            self.logger.info(f"Processing {len(tables)} table(s)")

            # Process each table
            for i, table in enumerate(tables, 1):
                self.logger.info(f"Processing table {i}/{len(tables)}: {table}")

                try:
                    # Create entity class if not cached
                    if table not in self.entity_classes:
                        self.entity_classes[table] = await self._create_entity_class(client, table)

                    entity_class = self.entity_classes[table]

                    # Fetch and yield entities
                    async for entity in self._fetch_table_data(client, table, entity_class):
                        yield entity

                except Exception as e:
                    self.logger.error(f"Failed to process table {table}: {e}")
                    if not self.respect_rls:
                        raise

            self.logger.info(f"Successfully completed sync for {len(tables)} table(s)")
