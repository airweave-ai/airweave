"""Shared HTTP utilities for Monke test steps."""

import os
from typing import Any, Dict, Optional
import httpx


def get_headers() -> Dict[str, str]:
    """Get standard HTTP headers for Airweave API requests."""
    headers = {"Content-Type": "application/json"}
    api_key = os.getenv("AIRWEAVE_API_KEY")
    if api_key:
        headers["x-api-key"] = api_key
    return headers


def get_base_url() -> str:
    """Get the Airweave API base URL."""
    return os.getenv("AIRWEAVE_API_URL", "http://localhost:8001").rstrip("/")


def http_get(path: str, timeout: float = 30.0) -> Any:
    """Perform HTTP GET request to Airweave API."""
    resp = httpx.get(f"{get_base_url()}{path}", headers=get_headers(), timeout=timeout)
    resp.raise_for_status()
    return resp.json()


def http_post(
    path: str,
    json: Optional[Dict[str, Any]] = None,
    params: Optional[Dict[str, Any]] = None,
    timeout: float = 30.0,
) -> Any:
    """Perform HTTP POST request to Airweave API."""
    resp = httpx.post(
        f"{get_base_url()}{path}",
        headers=get_headers(),
        json=json,
        params=params,
        timeout=timeout,
    )
    if resp.status_code == 422:
        # Log validation error details for debugging
        try:
            error_body = resp.json()
            import json as json_lib
            from monke.utils.logging import get_logger

            logger = get_logger("http_utils")
            logger.error(
                f"Validation error (422) for POST {path}: {json_lib.dumps(error_body, indent=2)}"
            )
        except Exception:
            pass  # If we can't parse the error, continue with raise_for_status
    resp.raise_for_status()
    return resp.json()


def http_delete(path: str, timeout: float = 30.0) -> httpx.Response:
    """Perform HTTP DELETE request to Airweave API."""
    return httpx.delete(
        f"{get_base_url()}{path}",
        headers=get_headers(),
        timeout=timeout,
    )
