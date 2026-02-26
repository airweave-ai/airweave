"""Configuration for API groups to include in the OpenAPI spec."""

# Dictionary of endpoints to include in the SDK, structured by path and methods
INCLUDED_ENDPOINTS = {
    # Sources
    "/sources/": {"get": True},
    "/sources/{short_name}/": {"get": True},
    # Collections
    "/collections/": {"get": True, "post": True},
    "/collections/{readable_id}/": {"get": True, "patch": True, "delete": True},
    "/collections/{readable_id}/search/": {"get": True, "post": True},
    # Source Connections
    "/source-connections/": {"get": True, "post": True},
    "/source-connections/{source_connection_id}/": {
        "get": True,
        "patch": True,
        "delete": True,
    },
    "/source-connections/{source_connection_id}/run/": {"post": True},
    "/source-connections/{source_connection_id}/jobs/": {"get": True},
    "/source-connections/{source_connection_id}/jobs/{job_id}/cancel/": {"post": True},
    # Webhooks
    "/webhooks/messages/": {"get": True},
    "/webhooks/messages/{message_id}/": {"get": True},
    "/webhooks/subscriptions/": {"get": True, "post": True},
    "/webhooks/subscriptions/{subscription_id}/": {
        "get": True,
        "patch": True,
        "delete": True,
    },
    "/webhooks/subscriptions/{subscription_id}/recover/": {"post": True},
}

# API group descriptions for documentation
API_GROUPS = {
    "Sources": "API endpoints for discovering available data source connectors and their configuration requirements",
    "Collections": "API endpoints for managing collections - logical groups of data sources that provide unified search capabilities",
    "Source Connections": "API endpoints for managing live connections to data sources. Source connections are the actual configured instances that Airweave uses to sync data from your apps and databases, transforming it into searchable, structured information within collections",
    "Webhooks": "API endpoints for managing webhook subscriptions and messages. Subscribe to events like sync completions to receive real-time notifications at your webhook URL",
}


def is_included_endpoint(path: str, method: str) -> bool:
    """Check if an endpoint should be included in the OpenAPI spec.

    Args:
        path: The path of the endpoint
        method: The HTTP method (lowercase)

    Returns:
        True if the endpoint should be included, False otherwise
    """
    # Remove trailing slash for consistency in matching
    normalized_path = path
    if normalized_path.endswith("/") and len(normalized_path) > 1:
        normalized_path = normalized_path[:-1]

    # Add trailing slash for matching with the dictionary
    path_with_slash = path
    if not path_with_slash.endswith("/"):
        path_with_slash = path_with_slash + "/"

    # Try both with and without trailing slash
    for try_path in [normalized_path, path_with_slash]:
        if try_path in INCLUDED_ENDPOINTS:
            methods = INCLUDED_ENDPOINTS[try_path]
            return method.lower() in methods and methods[method.lower()]

    return False
