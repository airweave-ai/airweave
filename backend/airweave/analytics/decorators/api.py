"""Decorators for tracking API endpoint metrics."""

import asyncio
import time
from functools import wraps
from typing import Any, Callable, Optional, TypeVar

from fastapi import HTTPException

from airweave.analytics.service import analytics

F = TypeVar("F", bound=Callable[..., Any])


def track_api_endpoint(event_name: Optional[str] = None, include_timing: bool = True):
    """Decorator to track API endpoint calls with performance metrics.

    Args:
    ----
        event_name: Custom event name (defaults to function name)
        include_timing: Whether to include timing metrics
    """
    
    def _extract_api_context(kwargs):
        """Extract ApiContext from function kwargs."""
        for arg in kwargs.values():
            if hasattr(arg, "user") and hasattr(arg, "organization"):
                return arg
        return None
    
    def _track_api_call(ctx, start_time, error, status_code, func_name):
        """Track API call analytics."""
        if not ctx:
            return
            
        properties = {
            "endpoint": event_name or func_name,
            "status_code": status_code,
            "auth_method": getattr(ctx, "auth_method", "unknown"),
            "organization_name": getattr(ctx.organization, "name", "unknown"),
        }

        if include_timing and start_time:
            properties["duration_ms"] = (time.time() - start_time) * 1000

        if error:
            properties["error"] = error

        event_suffix = "_error" if error else ""
        analytics.track_event(
            event_name=f"api_call{event_suffix}",
            distinct_id=str(ctx.user.id)
            if ctx.user
            else f"api_key_{ctx.organization.id}",
            properties=properties,
            groups={"organization": str(ctx.organization.id)},
        )

    def decorator(func: F) -> F:
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            start_time = time.time() if include_timing else None
            ctx = _extract_api_context(kwargs)
            error = None
            status_code = 200

            try:
                result = await func(*args, **kwargs)
                return result
            except HTTPException as e:
                error = e.detail
                status_code = e.status_code
                raise
            except Exception as e:
                error = str(e)
                status_code = 500
                raise
            finally:
                _track_api_call(ctx, start_time, error, status_code, func.__name__)

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            start_time = time.time() if include_timing else None
            ctx = _extract_api_context(kwargs)
            error = None
            status_code = 200

            try:
                result = func(*args, **kwargs)
                return result
            except HTTPException as e:
                error = e.detail
                status_code = e.status_code
                raise
            except Exception as e:
                error = str(e)
                status_code = 500
                raise
            finally:
                _track_api_call(ctx, start_time, error, status_code, func.__name__)

        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper

    return decorator
