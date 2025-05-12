"""MCP Server for Airweave Asana Integration

This server provides a tool for Cursor or Claude Desktop to semantically search
content stored in Asana and indexed by Airweave.
"""

import logging
import sys
import traceback

import httpx
from mcp.server.fastmcp import FastMCP

# from backend.airweave.core.chat_service import chat_service

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger("asana-search-mcp-server")

# Constants
DEFAULT_BACKEND_URL = "http://localhost:8001"  # Backend service URL for local development
DEFAULT_SYNC_ID = "7fe07244-2337-47ac-abd6-1673debbdc38"  # Default Asana sync ID

# Initialize FastMCP server
mcp = FastMCP(
    name="Airweave Asana Search",
    instructions="""This server allows Claude to semantically search the contents of your Asana workspace using Airweave.""",
    port=8002,
)


# Make sure errors are properly logged to stderr
def log_error(message):
    print(f"ERROR: {message}", file=sys.stderr)
    logger.error(message)


@mcp.tool("airweave-asana-search")
async def search_asana(query: str) -> str:
    """Search through your Asana files using Airweave's semantic search.

    Args:
        query: The search query to find relevant information in your Asana files
    """
    response_type = "raw"
    logger.info(f"Searching Asana with query: '{query}'")

    url = f"{DEFAULT_BACKEND_URL}/search"
    params = {"sync_id": DEFAULT_SYNC_ID, "query": query, "response_type": response_type}

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.get(url, params=params)
            response.raise_for_status()
            data = response.json()

            # Process the results similar to search.py
            results = data.get("results", [])
            if not results:
                return "No matching documents found in your Asana workspace."

            # Process vector data and clean up results
            for result in results:
                if isinstance(result, dict) and "payload" in result:
                    # Remove vector from payload to avoid sending large data back
                    if "vector" in result["payload"]:
                        result["payload"].pop("vector", None)

                    # Also remove download URLs from payload
                    if "download_url" in result["payload"]:
                        result["payload"].pop("download_url", None)

            # For raw response type, return processed results
            if response_type == "raw":
                return str(results)

            # For completion response type, return the AI-generated summary
            elif response_type == "completion":
                completion = data.get("completion", "No completion available.")
                return completion

            # Fallback
            return str(data)

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTPStatusError: {e.response.status_code} - {e.response.text}")

            # Try to parse the error response
            error_message = "Search request failed."
            try:
                error_data = e.response.json()
                if "detail" in error_data:
                    error_message = f"Search failed: {error_data['detail']}"
            except Exception:
                error_message = f"Search failed with status code {e.response.status_code}"

            return error_message

        except Exception as e:
            logger.error(f"Error during search: {str(e)}")
            return f"An error occurred during search: {str(e)}"


if __name__ == "__main__":
    try:
        print("Starting Airweave Asana Search MCP server...", file=sys.stderr)
        logger.info("Starting Airweave Asana Search MCP server...")
        print(f"Using Python version: {sys.version}", file=sys.stderr)
        print(f"Script location: {__file__}", file=sys.stderr)

        # Use stdio for Claude Desktop integration
        mcp.run(transport="stdio")
    except Exception as e:
        error_msg = f"Error starting MCP server: {str(e)}\n{traceback.format_exc()}"
        print(error_msg, file=sys.stderr)
        logger.error(error_msg)
        sys.exit(1)
