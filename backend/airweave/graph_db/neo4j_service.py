"""Service class for managing a connection to a Neo4j database."""

import traceback as tb
from typing import Optional

from neo4j import AsyncDriver, AsyncGraphDatabase

from airweave.core.config import settings
from airweave.core.logging import logger


class Neo4jService:
    """Service for configuring, setting up, and terminating a connection to a Neo4j database.

    Attributes:
    ----------
        uri (str): The URI of the Neo4j database.
        username (str): The username for the Neo4j database.
        password (str): The password for the Neo4j database.
        driver (AsyncDriver): The driver for the Neo4j database.
        database (str): The name of the Neo4j database.
    """

    def __init__(
        self,
        uri: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        database: Optional[str] = "neo4j",  # Default database name
    ) -> None:
        """Initialize the Neo4jService with configurable settings.

        Args:
        ----
            uri (Optional[str]): The URI of the Neo4j database.
            username (Optional[str]): The username for the Neo4j database.
            password (Optional[str]): The password for the Neo4j database.
            database (Optional[str]): The name of the Neo4j database.
        """
        self.uri = uri or f"bolt://{settings.NEO4J_HOST}:{settings.NEO4J_PORT}"
        self.username = username or settings.NEO4J_USER
        self.password = password or settings.NEO4J_PASSWORD
        self.driver: Optional[AsyncDriver] = None
        self.database = database

    async def __aenter__(self):
        """Async context manager to connect to the Neo4j database.

        Returns:
        -------
            Neo4jService: The Neo4jService instance
        """
        await self.connect_to_neo4j_database()
        return self

    async def __aexit__(
        self,
        exc_type: Optional[type[BaseException]],
        exc_value: Optional[BaseException],
        traceback: Optional[tb.TracebackException],
    ) -> None:
        """Async context manager to close the connection to the Neo4j database.

        Args:
        ----
            exc_type (Optional[Type[BaseException]]): The exception type if an exception was raised
                in the context.
            exc_value (Optional[BaseException]): The exception instance if an exception was raised.
            traceback (Optional[TracebackType]): Traceback object if an exception was raised.

        """
        try:
            await self.close_connection()
        finally:
            if exc_type is not None:
                logger.error(
                    f"An error occurred during an open Neo4j connection: {exc_value}",
                    exc_info=(exc_type, exc_value, traceback),
                )

    async def ensure_driver_readiness(self) -> None:
        """Ensure the driver is ready to accept requests."""
        if self.driver is None or not await self.is_connected():
            await self.connect_to_neo4j_database()

    async def is_connected(self) -> bool:
        """Check if driver is connected to Neo4j database.

        Returns:
        -------
            bool: True if the driver is connected to the Neo4j database, False otherwise.
        """
        if not self.driver:
            return False
        try:
            await self.driver.verify_connectivity()
            return True
        except Exception:
            return False

    async def connect_to_neo4j_database(self) -> None:
        """Establish connection to the Neo4j database.

        Raises:
        ------
            Exception: If the connection to the Neo4j database fails.
        """
        if not self.driver:
            try:
                self.driver = AsyncGraphDatabase.driver(
                    self.uri, auth=(self.username, self.password)
                )

                # Verify connection is working
                await self.driver.verify_connectivity()
                logger.info(f"Successfully connected to Neo4j database at {self.uri}")
            except Exception:
                logger.error(f"Failed to connect to Neo4j database at {self.uri}")
                logger.error(tb.format_exc())
                raise

    async def close_connection(self) -> None:
        """Close the connection to the Neo4j database."""
        if self.driver:
            try:
                await self.driver.close()
                logger.info(f"Successfully closed connection to Neo4j database at {self.uri}")
            except Exception:
                logger.error(f"Failed to close connection to Neo4j database at {self.uri}")
                logger.error(tb.format_exc())
                raise
            finally:
                self.driver = None

    async def get_session(self, database: Optional[str] = None):
        """Get a session for the specified database.

        Args:
        ----
            database (Optional[str]): The name of the Neo4j database.

        Returns:
        -------
            Session: The session for the specified database.
        """
        await self.ensure_driver_readiness()
        return self.driver.session(database=database or self.database)
