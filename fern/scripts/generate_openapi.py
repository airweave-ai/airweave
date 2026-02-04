"""Generate OpenAPI schema for Airweave API."""

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict

from airweave.main import app
from api_config import API_GROUPS, is_included_endpoint
from fastapi.openapi.utils import get_openapi

# Get the absolute path to the project root (2 levels up from fern/scripts)
project_root = Path(__file__).parent.parent.parent.absolute()
backend_dir = project_root / "backend"
scripts_dir = Path(__file__).parent.absolute()

# Add scripts and backend to Python path
sys.path.append(str(scripts_dir))
sys.path.append(str(backend_dir))
os.chdir(backend_dir)  # Change working directory to backend


def filter_paths(openapi_schema: Dict[str, Any]) -> Dict[str, Any]:
    """Filter OpenAPI paths to only include allowed endpoints."""
    if "paths" not in openapi_schema:
        return openapi_schema

    filtered_paths = {}
    for path, path_item in openapi_schema["paths"].items():
        include_path = False
        filtered_operations = {}

        for method, operation in path_item.items():
            if method.lower() in [
                "get",
                "post",
                "put",
                "delete",
                "patch",
            ] and is_included_endpoint(path, method):
                filtered_operations[method] = operation
                include_path = True

        if include_path:
            filtered_paths[path] = filtered_operations

    openapi_schema["paths"] = filtered_paths
    return openapi_schema


def fix_security_scheme(openapi_schema: Dict[str, Any]) -> Dict[str, Any]:
    """Fix the security scheme definition to handle authentication properly.

    We'll completely replace the existing Auth0HTTPBearer security scheme with
    just the ApiKeyAuth scheme, ensuring the SDK only requires an API key.

    This function thoroughly removes any duplicated authentication parameters
    to avoid the "duplicate parameter" error in generated SDKs.
    """
    # Ensure components exists
    if "components" not in openapi_schema:
        openapi_schema["components"] = {}

    # Replace the security scheme to use only apiKey with header
    openapi_schema["components"]["securitySchemes"] = {
        "ApiKeyAuth": {
            "type": "apiKey",
            "in": "header",
            "name": "x-api-key",
            "description": "API key for authentication",
        }
    }

    # Process all paths to fix authentication
    for path, path_item in openapi_schema["paths"].items():
        for method, operation in path_item.items():
            if method.lower() in ["get", "post", "put", "delete", "patch"]:
                # Replace any existing security with just the API key
                operation["security"] = [{"ApiKeyAuth": []}]

                # Remove all auth-related parameters from operations
                # This is critical to avoid duplication with the security scheme
                if "parameters" in operation:
                    operation["parameters"] = [
                        param
                        for param in operation["parameters"]
                        if not (
                            # Remove Authorization header
                            (param.get("name") == "Authorization" and param.get("in") == "header")
                            # Remove x-api-key (lowercase)
                            or (param.get("name") == "x-api-key" and param.get("in") == "header")
                            # Remove X-API-Key (capitalized)
                            or (param.get("name") == "X-API-Key" and param.get("in") == "header")
                            # Remove X-Organization-ID (we don't want this in the public API spec)
                            or (
                                param.get("name") == "X-Organization-ID"
                                and param.get("in") == "header"
                            )
                        )
                    ]

    # Remove any global security definitions if they exist
    if "security" in openapi_schema:
        openapi_schema["security"] = [{"ApiKeyAuth": []}]

    return openapi_schema


def add_tag_display_names(openapi_schema: Dict[str, Any]) -> Dict[str, Any]:
    """Add display names to tags in the OpenAPI schema."""
    # Mapping from tag name to display name
    tag_display_names = {
        "collections": "Collections",
        "source-connections": "Source Connections",
        "sources": "Sources",
        "events": "Events",
    }

    # Update existing tags with display names
    if "tags" in openapi_schema:
        for tag in openapi_schema["tags"]:
            if tag["name"] in tag_display_names:
                tag["x-display-name"] = tag_display_names[tag["name"]]
    else:
        # Create tags section if it doesn't exist
        openapi_schema["tags"] = []
        for tag_name, display_name in tag_display_names.items():
            openapi_schema["tags"].append(
                {
                    "name": tag_name,
                    "x-display-name": display_name,
                    "description": API_GROUPS.get(
                        display_name, f"API endpoints for {display_name}"
                    ),
                }
            )

    return openapi_schema


def generate_openapi():
    """Generate OpenAPI schema for Airweave API."""
    print("Generating OpenAPI schema...")

    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        openapi_version=app.openapi_version,
        description=app.description,
        routes=app.routes,
    )

    # Filter the schema to only include allowed endpoints
    print("Filtering OpenAPI schema to include only specified API groups...")
    filtered_schema = filter_paths(openapi_schema)

    # Fix the security scheme
    print("Updating security scheme...")
    filtered_schema = fix_security_scheme(filtered_schema)

    # Add display names to tags
    print("Adding display names to tags...")
    filtered_schema = add_tag_display_names(filtered_schema)

    # Add server configurations
    filtered_schema["servers"] = [
        {
            "url": "https://api.airweave.ai",
            "description": "Production",
            "x-fern-server-name": "Production",
        },
        {
            "url": "http://localhost:8001",
            "description": "Local",
            "x-fern-server-name": "Local",
        },
    ]

    # Add info about included API groups
    if "info" in filtered_schema:
        api_groups_desc = (
            "\n\n## API Groups\nThis API spec only includes the following API groups:\n"
        )
        for group, description in API_GROUPS.items():
            api_groups_desc += f"- **{group}**: {description}\n"

        if "description" in filtered_schema["info"]:
            filtered_schema["info"]["description"] += api_groups_desc
        else:
            filtered_schema["info"]["description"] = api_groups_desc

    # Path to fern/definition directory from project root
    fern_dir = project_root / "fern" / "definition"
    fern_dir.mkdir(parents=True, exist_ok=True)

    output_path = fern_dir / "openapi.json"
    print(f"📝 Writing filtered OpenAPI spec to: {output_path}")

    with open(output_path, "w") as f:
        json.dump(filtered_schema, f, indent=2)

    # Count included endpoints and methods
    endpoint_count = 0
    method_count = 0
    if "paths" in filtered_schema:
        endpoint_count = len(filtered_schema["paths"])
        for path_item in filtered_schema["paths"].values():
            method_count += len(
                [
                    m
                    for m in path_item.keys()
                    if m.lower() in ["get", "post", "put", "delete", "patch"]
                ]
            )

    print(f"✅ Filtered OpenAPI schema saved to {output_path}")
    print(
        f"Included {endpoint_count} endpoints with {method_count} HTTP methods in the OpenAPI spec"
    )
    print("API groups included:")
    for group in API_GROUPS:
        print(f"- {group}")


if __name__ == "__main__":
    generate_openapi()
