"""Custom router implementation that simply disables slash redirects."""

from typing import Any, Callable

from fastapi import APIRouter
from fastapi.types import DecoratedCallable


class TrailingSlashRouter(APIRouter):
    """Registers endpoints for both a non-trailing-slash and a trailing slash.

    In regards to the exported API schema only the non-trailing slash will be included.

    Examples:
        @router.get("", include_in_schema=False) - not included in the OpenAPI schema, responds to
            both the naked url (no slash) and /

        @router.get("/some/path") - included in the OpenAPI schema as /some/path, responds to both
            /some/path and /some/path/

        @router.get("/some/path/") - included in the OpenAPI schema as /some/path, responds to both
            /some/path and /some/path/

    Co-opted from https://github.com/tiangolo/fastapi/issues/2060#issuecomment-974527690
    """

    def api_route(
        self, path: str, *, include_in_schema: bool = True, **kwargs: Any
    ) -> Callable[[DecoratedCallable], DecoratedCallable]:
        """Override the api_route decorator to register both slash and non-slash versions.

        Args:
            path (str): The path for the endpoint
            include_in_schema (bool): Whether to include the route in the OpenAPI schema
            **kwargs: Additional arguments to pass to the parent api_route method

        Returns:
            Callable[[DecoratedCallable], DecoratedCallable]: A decorator that registers both slash
                and non-slash versions.
        """
        if path.endswith("/"):
            path = path[:-1]

        add_path = super().api_route(path, include_in_schema=include_in_schema, **kwargs)

        alternate_path = path + "/"
        add_alternate_path = super().api_route(alternate_path, include_in_schema=False, **kwargs)

        def decorator(func: DecoratedCallable) -> DecoratedCallable:
            add_alternate_path(func)
            return add_path(func)

        return decorator
