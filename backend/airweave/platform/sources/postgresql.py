"""PostgreSQL source implementation.

This source connects to a PostgreSQL database and generates entities for each table
based on its schema structure. It dynamically creates entity classes at runtime
using the PolymorphicEntity system.
"""

import hashlib
import json
from datetime import datetime
from typing import Any, AsyncGenerator, Dict, List, Optional, Type, Union

import asyncpg

from airweave.core.pg_field_catalog_service import overwrite_catalog
from airweave.core.shared_models import RateLimitLevel
from airweave.db.session import get_db_context
from airweave.platform.cursors.postgresql import PostgreSQLCursor
from airweave.platform.decorators import source
from airweave.platform.entities._base import BaseEntity, PolymorphicEntity
from airweave.platform.sources._base import BaseSource
from airweave.schemas.source_connection import AuthenticationMethod

# Mapping of PostgreSQL types to Python types
PG_TYPE_MAP = {
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
    "timestamp": datetime,
    "timestamp with time zone": datetime,
    "date": datetime,
    "time": datetime,
    "json": Any,  # JSON can be dict, list, or primitive
    "jsonb": Any,  # JSONB can be dict, list, or primitive
}


@source(
    name="PostgreSQL",
    short_name="postgresql",
    auth_methods=[AuthenticationMethod.DIRECT, AuthenticationMethod.AUTH_PROVIDER],
    oauth_type=None,
    auth_config_class="PostgreSQLAuthConfig",
    config_class="PostgreSQLConfig",
    labels=["Database"],
    supports_continuous=True,
    rate_limit_level=RateLimitLevel.ORG,
    cursor_class=PostgreSQLCursor,
)
class PostgreSQLSource(BaseSource):
    """PostgreSQL source connector integrates with PostgreSQL databases to extract structured data.

    Synchronizes data from database tables.

    It uses dynamic schema introspection to create appropriate entity classes
    and provides comprehensive access to relational data with proper type mapping and relationships.
    """

    def __init__(self):
        """Initialize the PostgreSQL source."""
        super().__init__()  # Initialize BaseSource to get cursor support
        self.conn: Optional[asyncpg.Connection] = None
        self.entity_classes: Dict[str, Type[PolymorphicEntity]] = {}

    @classmethod
    async def create(
        cls, credentials: Dict[str, Any], config: Optional[Dict[str, Any]] = None
    ) -> "PostgreSQLSource":
        """Create a new PostgreSQL source instance.

        Args:
            credentials: Dictionary containing connection details:
                - host: Database host
                - port: Database port
                - database: Database name
                - user: Username
                - password: Password
                - schema: Schema to sync (defaults to 'public')
                - tables: Table to sync (defaults to '*')
            config: Optional configuration parameters for the PostgreSQL source.
        """
        instance = cls()
        instance.config = credentials.model_dump()
        return instance

    def get_default_cursor_field(self) -> Optional[str]:
        """Get the default cursor field for PostgreSQL source.

        PostgreSQL doesn't have a universal default cursor field since it depends
        on the table schema. Common patterns are 'updated_at' or 'modified_at'.

        Returns:
            None - user must specify cursor field for PostgreSQL
        """
        # PostgreSQL requires user to specify cursor field
        # since table schemas vary widely

        # NOTE: the fact that the source does not have a default cursor field
        # indicates that it should be set by the user

        return None

    def validate_cursor_field(self, cursor_field: str) -> None:
        """Validate if the given cursor field is valid for PostgreSQL.

        For PostgreSQL, we accept a JSON structure that maps tables to cursor fields.
        Format: {"schema.table": "cursor_column", ...}
        Or a single field name to use for all tables.

        Args:
            cursor_field: The cursor field specification to validate
        """
        # PostgreSQL accepts either:
        # 1. A single column name (applies to all tables)
        # 2. A JSON string mapping tables to columns
        if cursor_field.startswith("{") and cursor_field.endswith("}"):
            # Validate JSON format
            try:
                import json

                cursor_map = json.loads(cursor_field)
                if not isinstance(cursor_map, dict):
                    raise ValueError(
                        "Cursor field mapping must be a JSON object like: "
                        '{"public.users": "updated_at", "public.orders": "modified_at"}'
                    )
            except json.JSONDecodeError as e:
                raise ValueError(f"Invalid JSON in cursor field mapping: {e}") from e
        # Otherwise accept any string as a column name

    def _get_table_key(self, schema: str, table: str) -> str:
        """Generate consistent table key for identification."""
        return f"{schema}.{table}"

    def _get_cursor_data(self) -> Dict[str, Any]:
        """Get cursor data from cursor.

        Returns:
            Cursor data dictionary, empty dict if no cursor exists
        """
        if self.cursor:
            return self.cursor.cursor_data or {}
        return {}

    def _get_cursor_field_for_table(self, schema: str, table: str) -> Optional[str]:
        """Get the cursor field to use for a specific table.

        Args:
            schema: Schema name
            table: Table name

        Returns:
            The cursor field for this table, or None if not specified
        """
        cursor_field = self.get_effective_cursor_field()
        if not cursor_field:
            return None

        # Check if cursor_field is a JSON mapping
        if cursor_field.startswith("{") and cursor_field.endswith("}"):
            try:
                import json

                cursor_map = json.loads(cursor_field)
                # Try exact match first
                table_key = self._get_table_key(schema, table)
                if table_key in cursor_map:
                    return cursor_map[table_key]
                # Fall back to table name without schema
                if table in cursor_map:
                    return cursor_map[table]
            except json.JSONDecodeError:
                # If JSON parsing fails, treat as single field
                pass

        # Single field applies to all tables
        return cursor_field

    def _update_cursor_data(self, schema: str, table: str, cursor_value: Any):
        """Update cursor data with the latest cursor value for a table.

        Args:
            schema: Schema name
            table: Table name
            cursor_value: Latest cursor value from the table
        """
        if not self.cursor:
            return

        # Store cursor value per table
        cursor_key = self._get_table_key(schema, table)
        if not self.cursor.cursor_data:
            self.cursor.cursor_data = {}

        # Convert datetime to ISO format string for JSON serialization
        if isinstance(cursor_value, datetime):
            cursor_value = cursor_value.isoformat()

        # Store the maximum value seen for this table
        existing_value = self.cursor.cursor_data.get(cursor_key)

        # Handle comparison when existing value might be a string (ISO format)
        if existing_value is not None:
            # Convert existing string back to datetime for comparison if needed
            if isinstance(existing_value, str) and isinstance(cursor_value, str):
                # Both are ISO strings, compare as strings (works for ISO format)
                should_update = cursor_value > existing_value
            else:
                should_update = cursor_value > existing_value
        else:
            should_update = True

        if should_update:
            self.cursor.cursor_data[cursor_key] = cursor_value
            self.logger.debug(f"Updated cursor for table '{cursor_key}': {cursor_value}")

    async def _connect(self) -> None:
        """Establish database connection with timeout and error handling."""
        if not self.conn:
            try:
                # Convert localhost to 127.0.0.1 to avoid DNS resolution issues
                host = (
                    "127.0.0.1"
                    if self.config["host"].lower() in ("localhost", "127.0.0.1")
                    else self.config["host"]
                )

                self.conn = await asyncpg.connect(
                    host=host,
                    port=self.config["port"],
                    user=self.config["user"],
                    password=self.config["password"],
                    database=self.config["database"],
                    timeout=90.0,  # Connection timeout (1.5 minutes)
                    command_timeout=900.0,  # Command timeout (15 minutes for slow queries)
                    # Add server settings to prevent idle timeouts
                    server_settings={
                        "jit": "off",  # Disable JIT for predictable performance
                        "statement_timeout": "0",  # No statement timeout (handled client-side)
                        "idle_in_transaction_session_timeout": "0",  # Disable idle timeout
                        "tcp_keepalives_idle": "30",  # Send keepalive after 30s of idle
                        "tcp_keepalives_interval": "10",  # Keepalive interval 10s
                        "tcp_keepalives_count": "6",  # Number of keepalives before considering dead
                    },
                )
                self.logger.info(
                    f"Connected to PostgreSQL at {host}:{self.config['port']}, "
                    f"database: {self.config['database']}"
                )
            except asyncpg.InvalidPasswordError as e:
                raise ValueError("Invalid database credentials") from e
            except asyncpg.InvalidCatalogNameError as e:
                raise ValueError(f"Database '{self.config['database']}' does not exist") from e
            except (
                OSError,
                asyncpg.CannotConnectNowError,
                asyncpg.ConnectionDoesNotExistError,
            ) as e:
                raise ValueError(
                    f"Could not connect to database at {self.config['host']}:{self.config['port']}."
                    " Please check if the database is running and the port is correct. "
                    f"Error: {str(e)}"
                ) from e
            except Exception as e:
                raise ValueError(f"Database connection failed: {str(e)}") from e

    async def _ensure_connection(self) -> None:
        """Ensure connection is alive and reconnect if needed."""
        if self.conn:
            try:
                # Test connection with a simple query
                await self.conn.fetchval("SELECT 1")
            except (asyncpg.ConnectionDoesNotExistError, asyncpg.InterfaceError, OSError) as e:
                self.logger.warning(f"Connection lost, reconnecting: {e}")
                self.conn = None
                await self._connect()
            except Exception as e:
                self.logger.error(f"Connection test failed: {e}")
                self.conn = None
                await self._connect()
        else:
            await self._connect()

    async def _get_table_info(self, schema: str, table: str) -> Dict[str, Any]:
        """Get table/view structure information.

        Args:
            schema: Schema name
            table: Table or view name

        Returns:
            Dictionary containing column information and primary keys
        """
        # Get column information (works for both tables and views)
        columns_query = """
            SELECT
                column_name,
                data_type,
                is_nullable,
                column_default
            FROM information_schema.columns
            WHERE table_schema = $1 AND table_name = $2
            ORDER BY ordinal_position
        """
        columns = await self.conn.fetch(columns_query, schema, table)

        # Get primary key information (views won't have primary keys)
        pk_query = """
            SELECT a.attname
            FROM pg_index i
            JOIN pg_attribute a ON a.attrelid = i.indrelid AND a.attnum = ANY(i.indkey)
            WHERE i.indrelid = ($1 || '.' || $2)::regclass AND i.indisprimary
        """
        try:
            primary_keys = [pk["attname"] for pk in await self.conn.fetch(pk_query, schema, table)]
        except asyncpg.exceptions.UndefinedTableError:
            # This can happen for views which don't have primary keys
            primary_keys = []

        # If no primary keys found (common for views), try to find best candidate columns
        # This ensures each row gets a unique entity_id without creating huge keys
        if not primary_keys and columns:
            column_names = [col["column_name"] for col in columns]

            # Heuristic: Look for common primary key column names
            # Priority order: id, uuid, guid, then any column ending with _id
            table_key = self._get_table_key(schema, table)
            if "id" in column_names:
                primary_keys = ["id"]
                self.logger.debug(
                    f"No primary keys found for {table_key} (might be a view). "
                    f"Using 'id' column for entity identification."
                )
            elif "uuid" in column_names:
                primary_keys = ["uuid"]
                self.logger.debug(
                    f"No primary keys found for {table_key} (might be a view). "
                    f"Using 'uuid' column for entity identification."
                )
            elif "guid" in column_names:
                primary_keys = ["guid"]
                self.logger.debug(
                    f"No primary keys found for {table_key} (might be a view). "
                    f"Using 'guid' column for entity identification."
                )
            else:
                # Look for columns ending with _id
                id_columns = [col for col in column_names if col.endswith("_id")]
                if id_columns:
                    # Use the first _id column found
                    primary_keys = [id_columns[0]]
                    self.logger.debug(
                        f"No primary keys found for {table_key} (might be a view). "
                        f"Using '{id_columns[0]}' column for entity identification."
                    )
                else:
                    # Last resort: use first column to avoid huge composite keys
                    # This prevents the index size error while still providing some identification
                    primary_keys = [column_names[0]] if column_names else []
                    table_key = self._get_table_key(schema, table)
                    self.logger.warning(
                        f"No primary keys or id columns found for {table_key}. "
                        f"Using first column '{primary_keys[0] if primary_keys else 'none'}' "
                        f"for entity identification. This may not guarantee uniqueness."
                    )

        # Build column metadata
        column_info = {}
        for col in columns:
            pg_type = col["data_type"].lower()
            python_type = PG_TYPE_MAP.get(pg_type, Any)

            column_info[col["column_name"]] = {
                "python_type": python_type,
                "nullable": col["is_nullable"] == "YES",
                "default": col["column_default"],
                "pg_type": pg_type,
            }

        return {
            "columns": column_info,
            "primary_keys": primary_keys,
        }

    async def _create_entity_class(self, schema: str, table: str) -> Type[PolymorphicEntity]:
        """Create a entity class for a specific table or view.

        Args:
            schema: Schema name
            table: Table or view name

        Returns:
            Dynamically created entity class for the table/view
        """
        table_info = await self._get_table_info(schema, table)

        return PolymorphicEntity.create_table_entity_class(
            table_name=table,
            schema_name=schema,
            columns=table_info["columns"],
            primary_keys=table_info["primary_keys"],
        )

    async def _get_tables(self, schema: str) -> List[str]:
        """Get list of tables in a schema.

        Args:
            schema: Schema name

        Returns:
            List of table names
        """
        query = """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = $1
            AND table_type = 'BASE TABLE'
        """
        tables = await self.conn.fetch(query, schema)
        return [table["table_name"] for table in tables]

    async def _get_tables_and_views(self, schema: str) -> List[str]:
        """Get list of tables and views in a schema.

        Args:
            schema: Schema name

        Returns:
            List of table and view names
        """
        query = """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = $1
            AND table_type IN ('BASE TABLE', 'VIEW')
        """
        tables_and_views = await self.conn.fetch(query, schema)
        return [item["table_name"] for item in tables_and_views]

    async def _get_table_list(self, schema: str) -> List[str]:
        """Get the list of tables to process based on configuration.

        When wildcard (*) is used, only base tables are returned.
        When specific names are provided, both tables and views are checked.
        """
        tables_config = self.config.get("tables", "*") or "*"

        # Handle both wildcard and CSV list of tables
        if tables_config == "*":
            # Default behavior: only sync base tables, not views
            return await self._get_tables(schema)

        # Split by comma and strip whitespace, filter out empty strings
        tables = [t.strip() for t in tables_config.split(",") if t.strip()]

        # If no valid tables after filtering, treat as wildcard
        if not tables:
            return await self._get_tables(schema)

        # When specific names are provided, check both tables and views
        available_tables_and_views = await self._get_tables_and_views(schema)
        invalid_items = set(tables) - set(available_tables_and_views)
        if invalid_items:
            raise ValueError(
                f"Tables/views not found in schema '{schema}': {', '.join(invalid_items)}"
            )

        # Log if any views are being synced
        base_tables = set(await self._get_tables(schema))
        views = [t for t in tables if t not in base_tables]
        if views:
            self.logger.info(f"Including views in sync: {', '.join(views)}")

        return tables

    async def _convert_field_values(
        self, data: Dict[str, Any], model_fields: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Convert field values to the expected types based on the entity model.

        Args:
            data: The raw data dictionary from the database record
            model_fields: The model fields from the entity class

        Returns:
            Dict with processed field values matching the expected types
        """
        processed_data = {}
        for field_name, field_value in data.items():
            # Handle the case where the field name is 'id' in the database
            model_field_name = field_name + "_" if field_name == "id" else field_name

            # Skip if the field doesn't exist in the model
            if model_field_name not in model_fields:
                continue

            # If value is None, keep it as None
            if field_value is None:
                processed_data[model_field_name] = None
                continue

            # Get expected type from model field
            field_info = model_fields[model_field_name]
            field_type = field_info.annotation

            # Handle Union types (including Optional which is Union[T, None])
            if hasattr(field_type, "__origin__") and field_type.__origin__ is Union:
                # For Union types, get the non-None type (if it's Optional pattern)
                union_args = field_type.__args__
                # Filter out NoneType to get the actual type
                non_none_types = [arg for arg in union_args if arg is not type(None)]
                if non_none_types:
                    field_type = non_none_types[0]  # Take the first non-None type

            # Simple conversion: if target is string, convert to string
            if field_type is str and field_value is not None:
                processed_data[model_field_name] = str(field_value)
            else:
                # Let Pydantic handle everything else
                processed_data[model_field_name] = field_value

        return processed_data

    def _parse_json_fields(self, data: Dict[str, Any]) -> None:
        """Parse string fields that contain JSON data.

        Args:
            data: Dictionary to process (modified in place)
        """
        for key, value in data.items():
            if not isinstance(value, str):
                continue

            try:
                parsed_value = json.loads(value)
                data[key] = parsed_value
            except (json.JSONDecodeError, ValueError):
                # Keep as string if not valid JSON
                pass

    def _generate_entity_id(
        self, schema: str, table: str, data: Dict[str, Any], primary_keys: List[str]
    ) -> str:
        """Generate entity ID from primary key values or hash.

        Args:
            schema: Schema name
            table: Table name
            data: Record data
            primary_keys: List of primary key columns

        Returns:
            Generated entity ID
        """
        pk_values = [str(data[pk]) for pk in primary_keys if pk in data]
        table_key = self._get_table_key(schema, table)

        if pk_values:
            return f"{table_key}:" + ":".join(pk_values)

        # Fallback: use a hash of the row data if no primary keys are available
        row_hash = hashlib.md5(str(sorted(data.items())).encode()).hexdigest()[:16]
        entity_id = f"{table_key}:row_{row_hash}"
        self.logger.warning(
            f"No primary key values found for {table_key} row. "
            f"Using hash-based entity_id: {entity_id}"
        )
        return entity_id

    def _ensure_entity_id_length(self, entity_id: str, schema: str, table: str) -> str:
        """Ensure entity ID is within acceptable length limits.

        Args:
            entity_id: Original entity ID
            schema: Schema name
            table: Table name

        Returns:
            Entity ID (possibly hashed if too long)
        """
        # PostgreSQL btree index has a limit of ~2700 bytes, but we use 2000 to be safe
        if len(entity_id) <= 2000:
            return entity_id

        original_id = entity_id
        entity_hash = hashlib.sha256(entity_id.encode()).hexdigest()
        table_key = self._get_table_key(schema, table)
        entity_id = f"{table_key}:hashed_{entity_hash}"
        self.logger.warning(
            f"Entity ID too long ({len(original_id)} chars) for {table_key}. "
            f"Using hashed ID: {entity_id}"
        )
        return entity_id

    async def _process_record_to_entity(
        self,
        record: Any,
        schema: str,
        table: str,
        entity_class: Type[PolymorphicEntity],
        primary_keys: List[str],
        cursor_field: Optional[str] = None,
    ) -> tuple[BaseEntity, Any]:
        """Process a database record into an entity."""
        data = dict(record)
        cursor_value = data.get(cursor_field) if cursor_field else None

        self._parse_json_fields(data)

        entity_id = self._generate_entity_id(schema, table, data, primary_keys)
        entity_id = self._ensure_entity_id_length(entity_id, schema, table)

        processed_data = await self._convert_field_values(data, entity_class.model_fields)

        # Create entity with all base fields
        return (
            entity_class(
                entity_id=entity_id,
                breadcrumbs=[],  # Tables are top-level
                name=table,
                created_at=None,
                updated_at=None,
                **processed_data,
            ),
            cursor_value,
        )

    def _prepare_cursor_value(self, last_cursor_value: Any) -> Any:
        """Convert ISO string back to datetime for PostgreSQL query if needed."""
        if last_cursor_value and isinstance(last_cursor_value, str):
            try:
                # Try to parse as ISO datetime string
                from datetime import datetime

                return datetime.fromisoformat(last_cursor_value)
            except (ValueError, TypeError):
                # If not a datetime string, use as-is (could be an integer ID, etc.)
                pass
        return last_cursor_value

    def _log_sync_type(
        self, schema: str, table: str, cursor_field: Optional[str], last_cursor_value: Any
    ):
        """Log the type of sync being performed for a table."""
        table_key = self._get_table_key(schema, table)
        if cursor_field and last_cursor_value:
            self.logger.info(
                f"Table {table_key}: INCREMENTAL sync using field '{cursor_field}' "
                f"(changes after {last_cursor_value})"
            )
        elif cursor_field:
            self.logger.info(
                f"Table {table_key}: FULL sync (will track '{cursor_field}' for next sync)"
            )
        else:
            self.logger.debug(f"Table {table_key}: FULL sync (no cursor field configured)")

    async def _process_table_with_streaming(  # noqa: C901
        self,
        schema: str,
        table: str,
        entity_class: Type[PolymorphicEntity],
        cursor_field: Optional[str],
        last_cursor_value: Any,
    ) -> AsyncGenerator[BaseEntity, None]:
        """Process table using server-side cursor for efficient streaming.

        Uses PostgreSQL's server-side cursor for optimal performance on large tables.
        This avoids the OFFSET penalty and streams data efficiently.

        Args:
            schema: Schema name
            table: Table name
            entity_class: Entity class for the table
            cursor_field: Field to track for cursor updates
            last_cursor_value: Last cursor value for incremental sync

        Yields:
            Entities from the table
        """
        table_key = self._get_table_key(schema, table)

        total_records = 0
        max_cursor_value = None
        primary_keys = entity_class.model_fields["primary_key_columns"].default_factory()

        try:
            # Use server-side cursor for efficient streaming
            # This is much more efficient than client-side fetch with OFFSET
            self.logger.info(f"Starting server-side cursor stream for {table_key}")

            buffer = []
            BUFFER_SIZE = 1000  # Process in chunks for progress updates

            # Build query for server-side cursor
            if cursor_field and last_cursor_value:
                # Incremental: SELECT with WHERE clause
                query = f"""
                    SELECT * FROM "{schema}"."{table}"
                    WHERE "{cursor_field}" > $1
                    ORDER BY "{cursor_field}"
                """
                query_args = [last_cursor_value]
            elif cursor_field:
                # Full sync with cursor ordering
                query = f"""
                    SELECT * FROM "{schema}"."{table}"
                    ORDER BY "{cursor_field}"
                """
                query_args = []
            else:
                # Full sync without ordering
                query = f"""
                    SELECT * FROM "{schema}"."{table}"
                """
                query_args = []

            # Use server-side cursor with prefetch for efficient streaming
            # This streams data from PostgreSQL without loading all into memory
            async with self.conn.transaction():
                cursor = self.conn.cursor(query, *query_args, prefetch=BUFFER_SIZE)

                async for record in cursor:
                    # Process record to entity using consolidated logic
                    entity, cursor_value = await self._process_record_to_entity(
                        record, schema, table, entity_class, primary_keys, cursor_field
                    )

                    # Track max cursor value
                    if cursor_value is not None:
                        if max_cursor_value is None or cursor_value > max_cursor_value:
                            max_cursor_value = cursor_value

                    # Buffer entity
                    buffer.append(entity)

                    # Yield buffered entities periodically
                    if len(buffer) >= BUFFER_SIZE:
                        for e in buffer:
                            yield e
                            total_records += 1

                        if total_records % 1000 == 0:
                            self.logger.info(f"Table {table_key}: Streamed {total_records} records")
                        buffer = []

            # Yield remaining buffered entities
            for e in buffer:
                yield e
                total_records += 1

            self.logger.info(
                f"Table {table_key}: Completed server-side cursor stream, {total_records} records"
            )

            # Update cursor with max value
            if cursor_field and max_cursor_value is not None:
                self._update_cursor_data(schema, table, max_cursor_value)

        except Exception as e:
            self.logger.error(f"Server-side cursor failed for {table_key}: {e}")
            # Re-raise the exception since we don't have a fallback
            # The sync will fail and can be retried
            raise

    async def _process_table(
        self,
        schema: str,
        table: str,
        cursor_data: Dict[str, Any],
    ) -> AsyncGenerator[BaseEntity, None]:
        """Process a single table with incremental support using server-side cursor.

        Uses PostgreSQL's server-side cursor for efficient streaming of data,
        maintaining transaction consistency and avoiding OFFSET penalties.

        Args:
            schema: Schema name
            table: Table name
            cursor_data: Cursor data from previous syncs

        Yields:
            Entities from the table
        """
        table_key = self._get_table_key(schema, table)

        # Create entity class if not already created
        if table_key not in self.entity_classes:
            self.entity_classes[table_key] = await self._create_entity_class(schema, table)

        entity_class = self.entity_classes[table_key]
        cursor_field = self._get_cursor_field_for_table(schema, table)

        # Get and prepare last cursor value
        last_cursor_value = cursor_data.get(table_key) if cursor_data else None
        last_cursor_value = self._prepare_cursor_value(last_cursor_value)

        # Log sync type
        self._log_sync_type(schema, table, cursor_field, last_cursor_value)

        # Always use server-side cursor for efficient streaming
        # This provides consistent snapshot isolation and better performance
        self.logger.info(f"Using server-side cursor for streaming {table_key}")
        async for entity in self._process_table_with_streaming(
            schema, table, entity_class, cursor_field, last_cursor_value
        ):
            yield entity

    async def generate_entities(self) -> AsyncGenerator[BaseEntity, None]:
        """Generate entities for all tables in specified schemas with incremental support."""
        try:
            await self._connect()
            schema = self.config.get("schema", "public") or "public"
            tables = await self._get_table_list(schema)

            self.logger.info(
                f"Found {len(tables)} table(s) to sync in schema '{schema}': {', '.join(tables)}"
            )

            # Get cursor data for incremental sync
            cursor_data = self._get_cursor_data()

            # Log sync type
            if cursor_data:
                self.logger.info(
                    f"Found cursor data with {len(cursor_data)} table(s). "
                    f"Will perform INCREMENTAL sync for changed records."
                )
            else:
                self.logger.info("No cursor data found. Will perform FULL sync (first sync).")

            # Persist field catalog snapshot for this connection before streaming
            try:
                snapshot = await self._build_field_catalog_snapshot(schema, tables)
                # Best-effort persistence (no failure of sync if catalog fails)
                if getattr(self, "_organization_id", None) and getattr(
                    self, "_source_connection_id", None
                ):
                    async with get_db_context() as db:
                        await overwrite_catalog(
                            db=db,
                            organization_id=self._organization_id,  # type: ignore[arg-type]
                            source_connection_id=self._source_connection_id,  # type: ignore[arg-type]
                            snapshot=snapshot,
                            logger=self.logger,
                        )
                        await db.commit()
            except Exception as e:
                self.logger.warning(f"Failed to update Postgres field catalog: {e}")

            # Process tables WITHOUT a long-running transaction
            # This prevents transaction timeout issues and allows better connection management
            for i, table in enumerate(tables, 1):
                table_key = self._get_table_key(schema, table)
                self.logger.info(f"Processing table {i}/{len(tables)}: {table_key}")

                # Check connection health before processing each table
                await self._ensure_connection()

                async for entity in self._process_table(schema, table, cursor_data):
                    yield entity

            self.logger.info(f"Successfully completed sync for all {len(tables)} table(s)")

        finally:
            if self.conn:
                self.logger.info("Closing PostgreSQL connection")
                await self.conn.close()
                self.conn = None

    async def _build_field_catalog_snapshot(
        self, schema: str, tables: List[str]
    ) -> List[Dict[str, Any]]:
        """Build a full catalog snapshot for the given tables."""
        results: List[Dict[str, Any]] = []

        # Preload FK map for the schema
        fk_query = """
            SELECT
                tc.table_schema,
                tc.table_name,
                kcu.column_name,
                ccu.table_schema AS foreign_table_schema,
                ccu.table_name AS foreign_table_name,
                ccu.column_name AS foreign_column_name
            FROM information_schema.table_constraints AS tc
            JOIN information_schema.key_column_usage AS kcu
              ON tc.constraint_name = kcu.constraint_name
             AND tc.table_schema = kcu.table_schema
            JOIN information_schema.constraint_column_usage AS ccu
              ON ccu.constraint_name = tc.constraint_name
             AND ccu.table_schema = tc.table_schema
            WHERE tc.constraint_type = 'FOREIGN KEY'
              AND tc.table_schema = $1
        """
        fk_rows = await self.conn.fetch(fk_query, schema)
        fk_map: Dict[tuple[str, str, str], Dict[str, str]] = {}
        for r in fk_rows:
            fk_map[(r["table_schema"], r["table_name"], r["column_name"])] = {
                "ref_schema": r["foreign_table_schema"],
                "ref_table": r["foreign_table_name"],
                "ref_column": r["foreign_column_name"],
            }

        # Enum values (user-defined types)
        enum_query = """
            SELECT t.typname AS udt_name, e.enumlabel AS enum_value
            FROM pg_type t
            JOIN pg_enum e ON t.oid = e.enumtypid
            JOIN pg_catalog.pg_namespace n ON n.oid = t.typnamespace
        """
        enum_rows = await self.conn.fetch(enum_query)
        enum_values: Dict[str, List[str]] = {}
        for r in enum_rows:
            enum_values.setdefault(r["udt_name"], []).append(r["enum_value"])

        for table in tables:
            info = await self._get_table_info(schema, table)

            # Columns with details from information_schema
            columns_query = """
                SELECT
                    column_name,
                    data_type,
                    udt_name,
                    is_nullable,
                    column_default,
                    ordinal_position
                FROM information_schema.columns
                WHERE table_schema = $1 AND table_name = $2
                ORDER BY ordinal_position
            """
            col_rows = await self.conn.fetch(columns_query, schema, table)
            cols: List[Dict[str, Any]] = []
            for c in col_rows:
                key = (schema, table, c["column_name"])
                fk = fk_map.get(key)
                udt = c["udt_name"]
                cols.append(
                    {
                        "column_name": c["column_name"],
                        "data_type": c["data_type"],
                        "udt_name": udt,
                        "is_nullable": c["is_nullable"] == "YES",
                        "default_value": c["column_default"],
                        "ordinal_position": c["ordinal_position"],
                        "is_primary_key": c["column_name"] in info["primary_keys"],
                        "is_foreign_key": fk is not None,
                        "ref_schema": fk.get("ref_schema") if fk else None,
                        "ref_table": fk.get("ref_table") if fk else None,
                        "ref_column": fk.get("ref_column") if fk else None,
                        "enum_values": enum_values.get(udt),
                        # Simple filterable heuristic: prefer scalar/text/date
                        "is_filterable": (c["data_type"] not in ("json", "jsonb")),
                    }
                )

            # Choose a recency column heuristically (prefer timestamp-like names and types)
            recency_column = self._select_recency_column(cols)
            try:
                self.logger.debug(
                    f"[PGCatalog] {schema}.{table}: columns={len(cols)}, recency={recency_column}"
                )
            except Exception:
                pass

            results.append(
                {
                    "schema_name": schema,
                    "table_name": table,
                    "recency_column": recency_column,
                    "primary_keys": info["primary_keys"],
                    "foreign_keys": [
                        {
                            "column": k[2],
                            **v,
                        }
                        for k, v in fk_map.items()
                        if k[0] == schema and k[1] == table
                    ],
                    "columns": cols,
                }
            )

        return results

    def _select_recency_column(self, columns: List[Dict[str, Any]]) -> Optional[str]:
        """Select a reasonable recency column from column metadata.

        Heuristic: prefer timestamp/timestamptz types; prefer names containing
        'updated', 'modified', 'last_edited', then fall back to any timestamp/date.
        """
        if not columns:
            return None

        def is_ts(col: Dict[str, Any]) -> bool:
            dt = (col.get("data_type") or "").lower()
            return dt in {"timestamp", "timestamp with time zone", "timestamptz", "date"}

        candidates = [c for c in columns if is_ts(c)]
        if not candidates:
            return None

        name_scores: List[tuple[int, str]] = []
        for c in candidates:
            name = c.get("column_name", "").lower()
            score = 0
            if any(k in name for k in ("updated", "modified", "last_edited", "last_modified")):
                score += 2
            if name.endswith("_at"):
                score += 1
            name_scores.append((score, c["column_name"]))

        # Pick the highest score; if tie, keep first in ordinal_position order
        name_scores.sort(key=lambda x: (-x[0],))
        return name_scores[0][1] if name_scores else candidates[0]["column_name"]

    async def validate(self) -> bool:
        """Verify PostgreSQL credentials, schema access, and (optionally) tables."""
        try:
            # 1) Connect (handles common connection errors and timeouts)
            await self._connect()

            # 2) Simple ping
            try:
                _ = await self.conn.fetchval("SELECT 1;")
            except Exception as e:
                self.logger.error(f"PostgreSQL ping failed: {e}")
                return False

            # 3) Schema existence
            schema = (self.config or {}).get("schema", "public") or "public"
            exists = await self.conn.fetchval(
                "SELECT EXISTS(SELECT 1 FROM information_schema.schemata WHERE schema_name = $1);",
                schema,
            )
            if not exists:
                self.logger.error(f"Schema '{schema}' does not exist or is inaccessible.")
                return False

            # 4) If specific tables were requested, verify they exist
            tables_cfg = (self.config or {}).get("tables", "*") or "*"
            if isinstance(tables_cfg, str) and tables_cfg != "*":
                requested = [t.strip() for t in tables_cfg.split(",") if t.strip()]
                # If no valid tables after filtering, skip validation (will default to all)
                if requested:
                    available = await self._get_tables(schema)
                    missing = [t for t in requested if t not in available]
                    if missing:
                        self.logger.error(
                            f"Tables not found in schema '{schema}': {', '.join(missing)}"
                        )
                        return False

            return True

        except (asyncpg.InvalidPasswordError, asyncpg.InvalidCatalogNameError, ValueError) as e:
            self.logger.error(f"PostgreSQL validation failed (credentials/config): {e}")
            return False
        except Exception as e:
            self.logger.error(f"Unexpected error during PostgreSQL validation: {e}")
            return False
        finally:
            if self.conn:
                await self.conn.close()
                self.conn = None
