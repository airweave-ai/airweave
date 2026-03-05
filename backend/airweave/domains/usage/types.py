"""Usage domain types and pure business logic.

Constants, enums, and pure functions used by the usage service, factory,
and consumers. No IO — everything here is deterministic.
"""

from enum import Enum
from typing import Optional

from airweave.domains.billing.types import get_plan_limits
from airweave.schemas.billing_period import BillingPeriodStatus
from airweave.schemas.organization_billing import BillingPlan
from airweave.schemas.usage import UsageLimit


class ActionType(str, Enum):
    """Action type enum."""

    ENTITIES = "entities"
    QUERIES = "queries"
    SOURCE_CONNECTIONS = "source_connections"
    TEAM_MEMBERS = "team_members"


# Billing status restrictions — which action types are blocked for each status.
BILLING_STATUS_RESTRICTIONS: dict[BillingPeriodStatus, set[ActionType]] = {
    BillingPeriodStatus.ACTIVE: set(),
    BillingPeriodStatus.TRIAL: set(),
    BillingPeriodStatus.GRACE: {
        ActionType.SOURCE_CONNECTIONS,
    },
    BillingPeriodStatus.ENDED_UNPAID: {
        ActionType.ENTITIES,
        ActionType.SOURCE_CONNECTIONS,
    },
    BillingPeriodStatus.COMPLETED: {
        ActionType.ENTITIES,
        ActionType.SOURCE_CONNECTIONS,
        ActionType.QUERIES,
    },
}


def infer_usage_limit(plan: Optional[BillingPlan] = None) -> UsageLimit:
    """Build a UsageLimit from a billing plan.

    Falls back to DEVELOPER limits when plan is None.
    """
    plan = plan or BillingPlan.DEVELOPER
    limits = get_plan_limits(plan)
    return UsageLimit(
        max_entities=limits.get("max_entities"),
        max_queries=limits.get("max_queries"),
        max_source_connections=limits.get("max_source_connections"),
        max_team_members=limits.get("max_team_members"),
    )
