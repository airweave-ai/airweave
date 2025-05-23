"""MCP (Model Context Protocol) information endpoints."""

from typing import Any, Dict, List

from fastapi import HTTPException

from airweave.api.router import TrailingSlashRouter
from airweave.core.config import settings
from airweave.core.logging import logger

router = TrailingSlashRouter()

# Try to import MCP functionality
try:
    from airweave.platform.mcp import create_mcp_server

    MCP_AVAILABLE = True
except ImportError:
    MCP_AVAILABLE = False


@router.get("")
async def get_mcp_info() -> Dict[str, Any]:
    """Get information about MCP server status and capabilities.

    Returns:
    --------
        dict: Information about the MCP server configuration and availability.
    """
    return {
        "mcp_enabled": settings.MCP_ENABLED,
        "mcp_available": MCP_AVAILABLE,
        "mcp_endpoint": "/mcp-server/mcp" if settings.MCP_ENABLED and MCP_AVAILABLE else None,
        "description": "Model Context Protocol integration for Airweave",
        "status": "enabled" if settings.MCP_ENABLED and MCP_AVAILABLE else "disabled",
    }


@router.get("/capabilities")
async def get_mcp_capabilities() -> Dict[str, Any]:
    """Get detailed information about available MCP tools, resources, and prompts.

    This endpoint inspects the current FastAPI application and shows what would be
    exposed via the MCP protocol.

    Returns:
    --------
        dict: Detailed breakdown of MCP capabilities.

    Raises:
    ------
        HTTPException: If MCP is not enabled or available.
    """
    if not settings.MCP_ENABLED:
        raise HTTPException(status_code=404, detail="MCP is not enabled")

    if not MCP_AVAILABLE:
        raise HTTPException(status_code=503, detail="MCP functionality is not available")

    try:
        # Import here to avoid circular imports
        from airweave.main import app

        # Create a temporary MCP server to inspect capabilities
        mcp_server = create_mcp_server(app)

        # Get the capabilities (this is async)
        tools = await mcp_server.get_tools()
        resources = await mcp_server.get_resources()
        resource_templates = await mcp_server.get_resource_templates()

        return {
            "tools": {
                "count": len(tools),
                "names": [tool.name for tool in tools.values()],
                "details": {
                    name: {
                        "description": tool.description,
                        "parameters": (
                            tool.inputSchema.get("properties", {}).keys()
                            if tool.inputSchema
                            else []
                        ),
                    }
                    for name, tool in tools.items()
                },
            },
            "resources": {
                "count": len(resources),
                "names": [resource.name for resource in resources.values()],
                "details": {
                    name: {"description": resource.description, "mimeType": resource.mimeType}
                    for name, resource in resources.items()
                },
            },
            "resource_templates": {
                "count": len(resource_templates),
                "names": [template.name for template in resource_templates.values()],
                "details": {
                    name: {"description": template.description, "uriTemplate": template.uriTemplate}
                    for name, template in resource_templates.items()
                },
            },
            "route_mapping": {
                "GET_without_params": "Resources (for fetching data)",
                "GET_with_params": "Resource Templates (parameterized data access)",
                "POST_PUT_DELETE": "Tools (for operations that modify data)",
            },
        }

    except Exception as e:
        logger.error(f"Error inspecting MCP capabilities: {e}")
        raise HTTPException(status_code=500, detail="Error inspecting MCP capabilities") from e


@router.get("/routes")
async def get_route_mapping() -> List[Dict[str, Any]]:
    """Get information about how FastAPI routes map to MCP components.

    Returns:
    --------
        list: List of route mappings showing how each endpoint becomes an MCP component.

    Raises:
    ------
        HTTPException: If MCP is not enabled or available.
    """
    if not settings.MCP_ENABLED:
        raise HTTPException(status_code=404, detail="MCP is not enabled")

    try:
        # Import here to avoid circular imports
        from airweave.main import app

        route_mappings = []

        for route in app.routes:
            if hasattr(route, "methods") and hasattr(route, "path"):
                for method in route.methods:
                    if method == "OPTIONS":
                        continue

                    # Determine MCP component type based on route characteristics
                    has_path_params = "{" in route.path

                    if method == "GET":
                        if has_path_params:
                            component_type = "Resource Template"
                            description = "Parameterized data access"
                        else:
                            component_type = "Resource"
                            description = "Data fetching"
                    else:
                        component_type = "Tool"
                        description = "Operation that can modify data"

                    route_mappings.append(
                        {
                            "path": route.path,
                            "method": method,
                            "component_type": component_type,
                            "description": description,
                            "name": route.name
                            or f"{method.lower()}_{route.path.replace('/', '_').strip('_')}",
                        }
                    )

        return sorted(route_mappings, key=lambda x: (x["path"], x["method"]))

    except Exception as e:
        logger.error(f"Error mapping routes: {e}")
        raise HTTPException(status_code=500, detail="Error mapping routes to MCP components") from e
