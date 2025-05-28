"""PostgreSQL source implementation.

This source connects to a PostgreSQL database and generates entities for each table
based on its schema structure. It dynamically creates entity classes at runtime
using the PolymorphicEntity system.
"""

import json
from datetime import datetime
from typing import Any, AsyncGenerator, Dict, List, Optional, Type, Union

import asyncpg

from airweave.platform.auth.schemas import AuthType
from airweave.platform.decorators import source
from airweave.platform.entities._base import ChunkEntity, PolymorphicEntity
from airweave.platform.sources._base import BaseSource

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
    "json": Dict[str, Any],
    "jsonb": Dict[str, Any],
}


@source(
    name="PostgreSQL",
    short_name="postgresql",
    auth_type=AuthType.config_class,
    auth_config_class="PostgreSQLAuthConfig",
    config_class="PostgreSQLConfig",
    labels=["Database"],
)
class PostgreSQLSource(BaseSource):
    """PostgreSQL source implementation.

    This source connects to a PostgreSQL database and generates entities for each table
    in the specified schemas. It uses database introspection to:
    1. Discover tables and their structures
    2. Create appropriate entity classes dynamically
    3. Generate entities for each table's data
    """

    def __init__(self):
        """Initialize the PostgreSQL source."""
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
                    timeout=10.0,  # Add connection timeout
                    command_timeout=10.0,  # Add command timeout
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

    async def _get_table_info(self, schema: str, table: str) -> Dict[str, Any]:
        """Get table structure information.

        Args:
            schema: Schema name
            table: Table name

        Returns:
            Dictionary containing column information and primary keys
        """
        # Get column information
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

        # Get primary key information
        pk_query = """
            SELECT a.attname
            FROM pg_index i
            JOIN pg_attribute a ON a.attrelid = i.indrelid AND a.attnum = ANY(i.indkey)
            WHERE i.indrelid = ($1 || '.' || $2)::regclass AND i.indisprimary
        """
        primary_keys = [pk["attname"] for pk in await self.conn.fetch(pk_query, schema, table)]

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
        """Create a entity class for a specific table.

        Args:
            schema: Schema name
            table: Table name

        Returns:
            Dynamically created entity class for the table
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

    async def _get_table_list(self, schema: str) -> List[str]:
        """Get the list of tables to process based on configuration."""
        tables_config = self.config.get("tables", "*")

        # Handle both wildcard and CSV list of tables
        if tables_config == "*":
            return await self._get_tables(schema)

        # Split by comma and strip whitespace
        tables = [t.strip() for t in tables_config.split(",")]
        # Validate that all specified tables exist
        available_tables = await self._get_tables(schema)
        invalid_tables = set(tables) - set(available_tables)
        if invalid_tables:
            raise ValueError(f"Tables not found in schema '{schema}': {', '.join(invalid_tables)}")
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

    async def _process_table_batch(
        self, schema: str, table: str, entity_class: Type[PolymorphicEntity], batch: List
    ) -> AsyncGenerator[ChunkEntity, None]:
        """Process a batch of records from a table."""
        for record in batch:
            data = dict(record)

            # Simply try to convert all strings to JSON
            for key, value in data.items():
                if isinstance(value, str):
                    try:
                        parsed_value = json.loads(value)
                        data[key] = parsed_value
                    except (json.JSONDecodeError, ValueError):
                        # Keep as string if not valid JSON
                        pass

            model_fields = entity_class.model_fields
            primary_keys = model_fields["primary_key_columns"].default_factory()
            pk_values = [str(data[pk]) for pk in primary_keys]
            entity_id = f"{schema}.{table}:" + ":".join(pk_values)

            # Convert field values to match expected types in the entity model
            processed_data = await self._convert_field_values(data, model_fields)

            yield entity_class(entity_id=entity_id, **processed_data)

    async def generate_entities(self) -> AsyncGenerator[ChunkEntity, None]:
        """Generate entities for all tables in specified schemas."""
        try:
            await self._connect()
            schema = self.config.get("schema", "public")
            tables = await self._get_table_list(schema)

            # Start a transaction
            async with self.conn.transaction():
                for table in tables:
                    # Create entity class if not already created
                    if f"{schema}.{table}" not in self.entity_classes:
                        self.entity_classes[f"{schema}.{table}"] = await self._create_entity_class(
                            schema, table
                        )

                    entity_class = self.entity_classes[f"{schema}.{table}"]
                    BATCH_SIZE = 50
                    offset = 0

                    while True:
                        # Fetch records in batches using LIMIT and OFFSET
                        batch_query = (
                            f'SELECT * FROM "{schema}"."{table}" LIMIT {BATCH_SIZE} OFFSET {offset}'
                        )
                        records = await self.conn.fetch(batch_query)

                        # Break if no more records
                        if not records:
                            break

                        # Process the batch
                        async for entity in self._process_table_batch(
                            schema, table, entity_class, records
                        ):
                            yield entity

                        # Increment offset for next batch
                        offset += BATCH_SIZE

        finally:
            if self.conn:
                await self.conn.close()
                self.conn = None
