"""FastMCP server implementation for Airweave.

This module creates an MCP server from the existing Airweave FastAPI application,
allowing AI agents to interact with Airweave's functionality through the Model Context Protocol.
"""

from fastapi import FastAPI
from fastmcp import FastMCP
from starlette.applications import Starlette

from airweave.core.logging import logger


def create_mcp_server(fastapi_app: FastAPI) -> FastMCP:
    """Create a FastMCP server from the existing Airweave FastAPI application.

    This function automatically converts the existing FastAPI app routes into MCP tools,
    resources, and resource templates based on the route types:
    - GET routes without path params -> Resources
    - GET routes with path params -> Resource Templates
    - POST/PUT/DELETE routes -> Tools

    Args:
    ----
        fastapi_app: The existing Airweave FastAPI application

    Returns:
    -------
        FastMCP: Configured MCP server instance
    """
    logger.info("Creating MCP server from FastAPI application")

    # Create MCP server from FastAPI app with timeout configuration
    mcp_server = FastMCP.from_fastapi(
        app=fastapi_app,
        name="Airweave MCP Server",
        timeout=30.0,  # 30 second timeout for API requests
        description=(
            "Airweave MCP Server - Make any app searchable for your agent. "
            "Provides tools for data synchronization, search, and agent integration."
        ),
    )

    logger.info("FastMCP server created successfully")
    return mcp_server


def get_mcp_app(fastapi_app: FastAPI) -> Starlette:
    """Get an ASGI application for the MCP server that can be mounted.

    This returns a Starlette ASGI application that can be mounted into the main
    FastAPI application without interfering with existing functionality.

    Args:
    ----
        fastapi_app: The existing Airweave FastAPI application

    Returns:
    -------
        Starlette: ASGI application for the MCP server
    """
    logger.info("Creating MCP ASGI application")

    # Create the MCP server
    mcp_server = create_mcp_server(fastapi_app)

    # Get the HTTP app with Streamable HTTP transport (recommended)
    # The MCP endpoint will be available at /mcp within the mounted path
    mcp_app = mcp_server.http_app(path="/mcp")

    logger.info("MCP ASGI application created and ready for mounting")
    return mcp_app
