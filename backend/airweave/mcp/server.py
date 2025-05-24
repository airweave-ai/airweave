"""MCP server implementation for Airweave.

This module provides MCP (Model Context Protocol) server functionality
that can be integrated with the main FastAPI application.
"""

from fastmcp import FastMCP

from airweave.core.config import settings


def create_mcp_server() -> FastMCP:
    """Create and configure the MCP server.

    Returns:
        FastMCP: The configured MCP server instance.
    """
    mcp_server = FastMCP("Airweave MCP Server")

    # Add some basic tools - you can extend this with more specific Airweave functionality
    @mcp_server.tool()
    def get_server_info() -> str:
        """Get information about the Airweave server."""
        return f"Airweave API Server - Project: {settings.PROJECT_NAME}"

    return mcp_server


def get_mcp_app():
    """Get the MCP ASGI application for mounting.

    Returns:
        The MCP ASGI application configured for SSE transport.
    """
    mcp_server = create_mcp_server()
    return mcp_server.http_app(path="/sse", transport="sse")
