"""Usage domain factories.

UsageServiceFactory creates per-organization UsageEnforcementService instances.
NullUsageServiceFactory creates NullUsageEnforcementService (no-op) for local dev.
"""

from uuid import UUID

from airweave.core.logging import ContextualLogger
from airweave.domains.billing.repository import (
    BillingPeriodRepositoryProtocol,
    OrganizationBillingRepositoryProtocol,
)
from airweave.domains.organizations.protocols import UserOrganizationRepositoryProtocol
from airweave.domains.source_connections.protocols import SourceConnectionRepositoryProtocol
from airweave.domains.usage.protocols import UsageEnforcementProtocol, UsageServiceFactoryProtocol
from airweave.domains.usage.repository import UsageRepositoryProtocol
from airweave.domains.usage.service import NullUsageEnforcementService, UsageEnforcementService


class UsageServiceFactory(UsageServiceFactoryProtocol):
    """Builds UsageEnforcementService instances wired to real repositories."""

    def __init__(
        self,
        usage_repo: UsageRepositoryProtocol,
        billing_repo: OrganizationBillingRepositoryProtocol,
        period_repo: BillingPeriodRepositoryProtocol,
        sc_repo: SourceConnectionRepositoryProtocol,
        user_org_repo: UserOrganizationRepositoryProtocol,
    ) -> None:
        """Store repository dependencies for per-organization service creation."""
        self._usage_repo = usage_repo
        self._billing_repo = billing_repo
        self._period_repo = period_repo
        self._sc_repo = sc_repo
        self._user_org_repo = user_org_repo

    def create(self, organization_id: UUID, logger: ContextualLogger) -> UsageEnforcementProtocol:
        """Create a UsageEnforcementService for the given organization."""
        return UsageEnforcementService(
            organization_id=organization_id,
            usage_repo=self._usage_repo,
            billing_repo=self._billing_repo,
            period_repo=self._period_repo,
            sc_repo=self._sc_repo,
            user_org_repo=self._user_org_repo,
            logger=logger,
        )


class NullUsageServiceFactory(UsageServiceFactoryProtocol):
    """Factory that always returns NullUsageEnforcementService."""

    def create(self, organization_id: UUID, logger: ContextualLogger) -> UsageEnforcementProtocol:
        """Return a no-op service — no enforcement in local dev."""
        return NullUsageEnforcementService()
