"""Role-Based Access Control (RBAC) utilities for API endpoints.

This module provides authorization helpers for enforcing role-based permissions
on sensitive API operations.
"""

from fastapi import HTTPException

from airweave.api.context import ApiContext


def require_org_role(ctx: ApiContext, min_role: str = "admin") -> None:
    """Validate user has minimum organization role for sensitive operations.

    Args:
    ----
        ctx (ApiContext): API context with user and organization
        min_role (str): Minimum required role ("owner" or "admin")

    Raises:
    ------
        HTTPException: 403 if user lacks required role or uses API key auth
    """
    # Block API key authentication for administrative operations
    if not ctx.has_user_context:
        raise HTTPException(
            status_code=403,
            detail="This operation requires user authentication with admin privileges",
        )

    # Find user's role in current organization
    user_role = None
    for org in ctx.user.user_organizations:
        if org.organization.id == ctx.organization.id:
            user_role = org.role
            break

    if not user_role:
        raise HTTPException(
            status_code=403,
            detail="User not member of organization",
        )

    # Validate role hierarchy
    role_hierarchy = {"owner": 3, "admin": 2, "member": 1}
    if role_hierarchy.get(user_role, 0) < role_hierarchy.get(min_role, 99):
        raise HTTPException(
            status_code=403,
            detail=f"This operation requires {min_role} role or higher",
        )
