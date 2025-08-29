import asyncio
import httpx

BASE_URL = "http://localhost:8001"  # default


async def connect_composio_provider_polyfill(body_api_key: str) -> dict:
    """
    PUT /auth-providers/connect with only the body api_key configurable.
    No X-API-Key or X-Organization-ID headers are sent.
    """
    url = f"{BASE_URL}/auth-providers/connect"
    payload = {
        "auth_fields": {"api_key": body_api_key},
        "description": "My Composio Connection",
        "name": "My Composio Connection",
        "short_name": "composio",
    }
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        # Intentionally NOT setting X-API-Key or X-Organization-ID
    }

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.put(url, json=payload, headers=headers)
        resp.raise_for_status()
        return resp.json()
