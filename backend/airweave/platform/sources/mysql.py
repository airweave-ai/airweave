"""MySQL source implementation.

This source connects to a MySQL database and generates entities for each table
based on its schema structure. It dynamically creates entity classes at runtime
using the PolymorphicEntity system.
"""

from datetime import datetime
from typing import Any, AsyncGenerator, Dict, List, Optional, Type

import aiomysql

from airweave.platform.auth.schemas import AuthType
from airweave.platform.decorators import source
from airweave.platform.entities._base import ChunkEntity, PolymorphicEntity
from airweave.platform.sources._base import BaseSource

# Mapping of MySQL types to Python types
MYSQL_TYPE_MAP = {
    "int": int,
    "bigint": int,
    "smallint": int,
    "tinyint": int,
    "mediumint": int,
    "decimal": float,
    "numeric": float,
    "float": float,
    "double": float,
    "varchar": str,
    "char": str,
    "text": str,
    "mediumtext": str,
    "longtext": str,
    "tinytext": str,
    "boolean": bool,
    "bool": bool,
    "datetime": datetime,
    "timestamp": datetime,
    "date": datetime,
    "time": datetime,
    "json": Dict[str, Any],
}


@source("MySQL", "mysql", AuthType.config_class, "MySQLAuthConfig", labels=["Database"])
class MySQLSource(BaseSource):
    """MySQL source implementation.

    This source connects to a MySQL database and generates entities for each table
    in the specified schemas. It uses database introspection to:
    1. Discover tables and their structures
    2. Create appropriate entity classes dynamically
    3. Generate entities for each table's data
    """

    def __init__(self):
        """Initialize the MySQL source."""
        self.pool: Optional[aiomysql.Pool] = None
        self.entity_classes: Dict[str, Type[PolymorphicEntity]] = {}

    @classmethod
    async def create(cls, config: Dict[str, Any]) -> "MySQLSource":
        """Create a new MySQL source instance.

        Args:
            config: Dictionary containing connection details:
                - host: Database host
                - port: Database port
                - database: Database name
                - user: Username
                - password: Password
                - schema: Schema to sync (defaults to database name)
                - tables: Table to sync (defaults to '*')
        """
        instance = cls()
        instance.config = config.model_dump()
        return instance

    async def _connect(self) -> None:
        """Establish database connection with timeout and error handling."""
        if not self.pool:
            try:
                # Convert localhost to 127.0.0.1 to avoid DNS resolution issues
                host = (
                    "127.0.0.1"
                    if self.config["host"].lower() in ("localhost", "127.0.0.1")
                    else self.config["host"]
                )

                self.pool = await aiomysql.create_pool(
                    host=host,
                    port=self.config["port"],
                    user=self.config["user"],
                    password=self.config["password"],
                    db=self.config["database"],
                    connect_timeout=10,
                )
            except aiomysql.Error as e:
                raise ValueError(f"Database connection failed: {str(e)}") from e

    async def _get_table_info(self, schema: str, table: str) -> Dict[str, Any]:
        """Get table structure information.

        Args:
            schema: Schema name
            table: Table name

        Returns:
            Dictionary containing column information and primary keys
        """
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                # Get column information
                columns_query = """
                    SELECT
                        COLUMN_NAME,
                        DATA_TYPE,
                        IS_NULLABLE,
                        COLUMN_DEFAULT
                    FROM INFORMATION_SCHEMA.COLUMNS
                    WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s
                    ORDER BY ORDINAL_POSITION
                """
                await cursor.execute(columns_query, (schema, table))
                columns = await cursor.fetchall()

                # Get primary key information
                pk_query = """
                    SELECT COLUMN_NAME
                    FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE
                    WHERE TABLE_SCHEMA = %s
                        AND TABLE_NAME = %s
                        AND CONSTRAINT_NAME = 'PRIMARY'
                """
                await cursor.execute(pk_query, (schema, table))
                primary_keys = [row[0] for row in await cursor.fetchall()]

                # Build column metadata
                column_info = {}
                for col in columns:
                    mysql_type = col[1].lower()
                    python_type = MYSQL_TYPE_MAP.get(mysql_type, Any)

                    column_info[col[0]] = {
                        "python_type": python_type,
                        "nullable": col[2] == "YES",
                        "default": col[3],
                        "mysql_type": mysql_type,
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
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                query = """
                    SELECT TABLE_NAME
                    FROM INFORMATION_SCHEMA.TABLES
                    WHERE TABLE_SCHEMA = %s
                    AND TABLE_TYPE = 'BASE TABLE'
                """
                await cursor.execute(query, (schema,))
                tables = await cursor.fetchall()
                return [table[0] for table in tables]

    async def generate_entities(self) -> AsyncGenerator[ChunkEntity, None]:
        """Generate entities for all tables in specified schemas."""
        try:
            await self._connect()

            schema = self.config.get("schema", self.config["database"])
            tables_config = self.config.get("tables", "*")

            # Handle both wildcard and CSV list of tables
            if tables_config == "*":
                tables = await self._get_tables(schema)
            else:
                # Split by comma and strip whitespace
                tables = [t.strip() for t in tables_config.split(",")]
                # Validate that all specified tables exist
                available_tables = await self._get_tables(schema)
                invalid_tables = set(tables) - set(available_tables)
                if invalid_tables:
                    raise ValueError(
                        f"Tables not found in schema '{schema}': {', '.join(invalid_tables)}"
                    )

            async with self.pool.acquire() as conn:
                async with conn.cursor() as cursor:
                    for table in tables:
                        # Create entity class if not already created
                        if f"{schema}.{table}" not in self.entity_classes:
                            self.entity_classes[
                                f"{schema}.{table}"
                            ] = await self._create_entity_class(schema, table)

                        entity_class = self.entity_classes[f"{schema}.{table}"]

                        # Fetch and yield data
                        BATCH_SIZE = 50
                        offset = 0

                        while True:
                            # Fetch records in batches using LIMIT and OFFSET
                            batch_query = f"""
                                SELECT *
                                FROM `{schema}`.`{table}`
                                LIMIT {BATCH_SIZE} OFFSET {offset}
                            """
                            await cursor.execute(batch_query)
                            records = await cursor.fetchall()

                            # Break if no more records
                            if not records:
                                break

                            # Get column names from cursor description
                            columns = [column[0] for column in cursor.description]

                            # Process the batch
                            for record in records:
                                # Convert record to dictionary using column names
                                data = dict(zip(columns, record, strict=False))
                                model_fields = entity_class.model_fields
                                primary_keys = model_fields["primary_key_columns"].default_factory()
                                pk_values = [str(data[pk]) for pk in primary_keys]
                                entity_id = f"{schema}.{table}:" + ":".join(pk_values)

                                entity = entity_class(entity_id=entity_id, **data)
                                yield entity

                            # Increment offset for next batch
                            offset += BATCH_SIZE

        finally:
            if self.pool:
                self.pool.close()
                await self.pool.wait_closed()
                self.pool = None
