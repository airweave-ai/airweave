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
    rate_limit_level=RateLimitLevel.ORG,
)
class PostgreSQLSource(BaseSource):
    """PostgreSQL source connector integrates with PostgreSQL databases to extract structured data.

    Synchronizes data from database tables.

    It uses dynamic schema introspection to create appropriate entity classes
    and provides comprehensive access to relational data with proper type mapping and relationships.
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
        """Initialize the PostgreSQL source."""
        super().__init__()  # Initialize BaseSource to get cursor support
        self.conn: Optional[asyncpg.Connection] = None
        self.entity_classes: Dict[str, Type[PolymorphicEntity]] = {}
        self.column_field_mappings: Dict[str, Dict[str, str]] = {}

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
        instance.config = (
            credentials.model_dump() if hasattr(credentials, "model_dump") else dict(credentials)
        )
        return instance

    def _get_table_key(self, schema: str, table: str) -> str:
        """Generate consistent table key for identification."""
        return f"{schema}.{table}"

    def _normalize_model_field_name(self, column_name: str) -> str:
        """Normalize column names to avoid collisions with entity base fields."""
        if column_name == "id":
            return "id_"
        if column_name in self._RESERVED_ENTITY_FIELDS:
            return f"{column_name}_field"
        return column_name

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
        table_key = self._get_table_key(schema, table)

        normalized_columns: Dict[str, Dict[str, Any]] = {}
        column_mapping: Dict[str, str] = {}
        for original_name, column_meta in table_info["columns"].items():
            base_name = self._normalize_model_field_name(original_name)
            candidate = base_name
            suffix = 1
            while candidate in normalized_columns:
                suffix += 1
                candidate = f"{base_name}_{suffix}"
            normalized_columns[candidate] = column_meta
            column_mapping[original_name] = candidate

        self.column_field_mappings[table_key] = column_mapping

        return PolymorphicEntity.create_table_entity_class(
            table_name=table,
            schema_name=schema,
            columns=normalized_columns,
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
        self, data: Dict[str, Any], model_fields: Dict[str, Any], table_key: str
    ) -> Dict[str, Any]:
        """Convert field values to the expected types based on the entity model.

        Args:
            data: The raw data dictionary from the database record
            model_fields: The model fields from the entity class
            table_key: Unique identifier for the table to resolve column mappings

        Returns:
            Dict with processed field values matching the expected types
        """
        processed_data = {}
        column_mapping = self.column_field_mappings.get(table_key, {})
        for field_name, field_value in data.items():
            model_field_name = column_mapping.get(field_name)
            if not model_field_name:
                model_field_name = self._normalize_model_field_name(field_name)

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
    ) -> BaseEntity:
        """Process a database record into an entity."""
        data = dict(record)

        self._parse_json_fields(data)

        entity_id = self._generate_entity_id(schema, table, data, primary_keys)
        entity_id = self._ensure_entity_id_length(entity_id, schema, table)

        table_key = self._get_table_key(schema, table)
        processed_data = await self._convert_field_values(
            data, entity_class.model_fields, table_key
        )

        entity_name_field = self.column_field_mappings.get(table_key, {}).get("name")
        entity_name = processed_data.get(entity_name_field) if entity_name_field else None
        if not entity_name:
            entity_name = table

        return entity_class(
            entity_id=entity_id,
            breadcrumbs=[],  # Tables are top-level
            name=entity_name,
            created_at=None,
            updated_at=None,
            **processed_data,
        )

    async def _process_table_with_streaming(  # noqa: C901
        self,
        schema: str,
        table: str,
        entity_class: Type[PolymorphicEntity],
    ) -> AsyncGenerator[BaseEntity, None]:
        """Process table using server-side cursor for efficient streaming.

        Uses PostgreSQL's server-side cursor for optimal performance on large tables.
        This avoids the OFFSET penalty and streams data efficiently.

        Args:
            schema: Schema name
            table: Table name
            entity_class: Entity class for the table

        Yields:
            Entities from the table
        """
        table_key = self._get_table_key(schema, table)

        total_records = 0
        primary_keys = entity_class.model_fields["primary_key_columns"].default_factory()

        try:
            # Use server-side cursor for efficient streaming
            # This is much more efficient than client-side fetch with OFFSET
            self.logger.info(f"Starting server-side cursor stream for {table_key}")

            buffer = []
            BUFFER_SIZE = 1000  # Process in chunks for progress updates

            query = f"""
                SELECT * FROM "{schema}"."{table}"
            """
            query_args: list[Any] = []

            # Use server-side cursor with prefetch for efficient streaming
            # This streams data from PostgreSQL without loading all into memory
            async with self.conn.transaction():
                cursor = self.conn.cursor(query, *query_args, prefetch=BUFFER_SIZE)

                async for record in cursor:
                    # Process record to entity using consolidated logic
                    entity = await self._process_record_to_entity(
                        record, schema, table, entity_class, primary_keys
                    )

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

        except Exception as e:
            self.logger.error(f"Server-side cursor failed for {table_key}: {e}")
            # Re-raise the exception since we don't have a fallback
            # The sync will fail and can be retried
            raise

    async def _process_table(
        self,
        schema: str,
        table: str,
    ) -> AsyncGenerator[BaseEntity, None]:
        """Process a single table using server-side cursor streaming.

        Uses PostgreSQL's server-side cursor for efficient streaming of data,
        maintaining transaction consistency and avoiding OFFSET penalties.

        Args:
            schema: Schema name
            table: Table name

        Yields:
            Entities from the table
        """
        table_key = self._get_table_key(schema, table)

        # Create entity class if not already created
        if table_key not in self.entity_classes:
            self.entity_classes[table_key] = await self._create_entity_class(schema, table)

        entity_class = self.entity_classes[table_key]
        # Always use server-side cursor for efficient streaming
        # This provides consistent snapshot isolation and better performance
        self.logger.info(f"Using server-side cursor for streaming {table_key}")
        async for entity in self._process_table_with_streaming(schema, table, entity_class):
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

                async for entity in self._process_table(schema, table):
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
