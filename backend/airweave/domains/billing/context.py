"""Billing system context factory.

Provides a standalone function for creating system-level ApiContext instances
used by billing service and webhook handler for internal operations.
"""

from uuid import uuid4

from airweave import schemas
from airweave.api.context import ApiContext
from airweave.core.logging import logger
from airweave.core.shared_models import AuthMethod


def create_billing_system_context(
    organization: schemas.Organization,
    source: str = "billing_service",
) -> ApiContext:
    """Create a system context for billing operations.

    Args:
        organization: The organization to create context for.
        source: Identifier for the billing subsystem creating the context.

    Returns:
        ApiContext configured for internal system operations.
    """
    request_id = str(uuid4())
    return ApiContext(
        request_id=request_id,
        auth_method=AuthMethod.INTERNAL_SYSTEM,
        auth_subject_id=str(uuid4()),
        auth_subject_name=f"billing_{source}",
        organization=organization,
        user=None,
        logger=logger.with_context(
            request_id=request_id,
            organization_id=str(organization.id),
            auth_method=AuthMethod.INTERNAL_SYSTEM.value,
            source=source,
        ),
    )
