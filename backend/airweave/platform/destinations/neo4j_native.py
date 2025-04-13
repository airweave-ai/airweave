"""Neo4j native destination implementation."""

from airweave.platform.decorators import destination
from airweave.platform.destinations.neo4j import Neo4jDestination


@destination("Neo4j Native", "neo4j_native", labels=["Graph"])
class Neo4jNativeDestination(Neo4jDestination):
    """Neo4j native destination implementation."""
