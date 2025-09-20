"""API endpoints for usage data."""

from datetime import datetime, timedelta
from typing import Dict, List, Optional
from uuid import UUID

from fastapi import Body, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from airweave import crud, schemas
from airweave.api import deps
from airweave.api.context import ApiContext
from airweave.api.router import TrailingSlashRouter
from airweave.core.exceptions import PaymentRequiredException, UsageLimitExceededException
from airweave.core.guard_rail_service import GuardRailService
from airweave.core.shared_models import ActionType
from airweave.models import BillingPeriod, Usage
from airweave.schemas.organization_billing import BillingPlan
from airweave.schemas.usage_dashboard import (
    BillingPeriodUsage,
    UsageDashboard,
    UsageSnapshot,
    UsageTrend,
)

router = TrailingSlashRouter()


class ActionCheckRequest(BaseModel):
    """Request schema for checking multiple actions."""

    actions: Dict[str, int] = Field(
        ...,
        description="Dictionary of action types to check with their amounts",
        examples=[
            {
                "collections": 1,
                "source_connections": 1,
                "entities": 1,
                "syncs": 1,
                "queries": 1,
            }
        ],
    )


class ActionCheckResponse(BaseModel):
    """Response schema for multiple action checks."""

    results: Dict[str, schemas.SingleActionCheckResponse] = Field(
        ...,
        description="Dictionary of action check results keyed by action type",
    )


@router.post("/check-actions", response_model=ActionCheckResponse)
async def check_actions(
    request: ActionCheckRequest = Body(...),
    ctx: ApiContext = Depends(deps.get_context),
    guard_rail: GuardRailService = Depends(deps.get_guard_rail_service),
) -> ActionCheckResponse:
    """Check multiple actions for usage limits and billing status.

    Returns a dictionary of action check results keyed by action type.
    """
    ctx.logger.info(f"Checking actions: {list(request.actions.keys())}")

    results = {}

    for action, amount in request.actions.items():
        # Validate action type
        try:
            action_type = ActionType(action)
        except ValueError:
            # Skip invalid action types but log them
            ctx.logger.warning(f"Invalid action type in check: {action}")
            results[action] = schemas.SingleActionCheckResponse(
                allowed=False,
                action=action,
                reason="usage_limit_exceeded",
                details={"message": f"Invalid action type: {action}"},
            )
            continue

        try:
            # Check if the action is allowed
            is_allowed = await guard_rail.is_allowed(action_type, amount=amount)

            results[action] = schemas.SingleActionCheckResponse(
                allowed=is_allowed, action=action, reason=None, details=None
            )

        except PaymentRequiredException as e:
            # Action blocked due to billing status
            results[action] = schemas.SingleActionCheckResponse(
                allowed=False,
                action=action,
                reason="payment_required",
                details={"message": str(e), "payment_status": e.payment_status},
            )

        except UsageLimitExceededException as e:
            # Action blocked due to usage limit
            results[action] = schemas.SingleActionCheckResponse(
                allowed=False,
                action=action,
                reason="usage_limit_exceeded",
                details={"message": str(e), "current_usage": e.current_usage, "limit": e.limit},
            )

        except Exception as e:
            # Unexpected error for this action
            ctx.logger.error(f"Unexpected error checking action {action}: {str(e)}")
            results[action] = schemas.SingleActionCheckResponse(
                allowed=False,
                action=action,
                reason="usage_limit_exceeded",
                details={"message": f"Error checking action: {str(e)}"},
            )

    return ActionCheckResponse(results=results)


def _create_usage_snapshot(
    usage_record: Optional[Usage],
    plan_limits: dict,
    billing_period_id: UUID,
) -> UsageSnapshot:
    """Create a usage snapshot from usage record and plan limits."""
    return UsageSnapshot(
        syncs=usage_record.syncs if usage_record else 0,
        entities=usage_record.entities if usage_record else 0,
        queries=usage_record.queries if usage_record else 0,
        collections=usage_record.collections if usage_record else 0,
        source_connections=usage_record.source_connections if usage_record else 0,
        max_syncs=plan_limits.get("max_syncs"),
        max_entities=plan_limits.get("max_entities"),
        max_queries=plan_limits.get("max_queries"),
        max_collections=plan_limits.get("max_collections"),
        max_source_connections=plan_limits.get("max_source_connections"),
        timestamp=datetime.utcnow(),
        billing_period_id=billing_period_id,
    )


def _get_status_and_plan_strings(period: BillingPeriod) -> tuple[str, str]:
    """Extract status and plan strings from billing period, handling enums."""
    if hasattr(period.status, "value"):
        status_str = period.status.value
    else:
        status_str = str(period.status) if period.status else "unknown"

    if hasattr(period.plan, "value"):
        plan_str = period.plan.value
    else:
        plan_str = str(period.plan) if period.plan else "unknown"

    return status_str, plan_str


def _create_default_dashboard() -> UsageDashboard:
    """Create a default dashboard for organizations without billing."""
    return UsageDashboard(
        current_period=BillingPeriodUsage(
            period_id=UUID("00000000-0000-0000-0000-000000000000"),
            period_start=datetime.utcnow(),
            period_end=datetime.utcnow() + timedelta(days=30),
            status="legacy",
            plan="legacy",
            usage=UsageSnapshot(
                syncs=0,
                entities=0,
                queries=0,
                collections=0,
                source_connections=0,
                max_syncs=None,
                max_entities=None,
                max_queries=None,
                max_collections=None,
                max_source_connections=None,
                timestamp=datetime.utcnow(),
                billing_period_id=UUID("00000000-0000-0000-0000-000000000000"),
            ),
            days_remaining=None,
            is_current=True,
        ),
        previous_periods=[],
        total_entities_all_time=0,
        total_queries_all_time=0,
        average_daily_entities=0,
        average_daily_queries=0,
        trends=[],
    )


async def _get_target_period(
    db: AsyncSession,
    period_id: Optional[UUID],
    ctx: ApiContext,
) -> Optional[BillingPeriod]:
    """Get the target billing period based on period_id or current period."""
    if period_id:
        target_period = await crud.billing_period.get(db, id=period_id, ctx=ctx)
        if not target_period:
            raise HTTPException(status_code=404, detail="Billing period not found")
        return target_period
    else:
        return await crud.billing_period.get_current_period(db, organization_id=ctx.organization.id)


def _calculate_trends(
    current_usage: UsageSnapshot,
    prev_usage: Optional[Usage],
) -> List[UsageTrend]:
    """Calculate usage trends by comparing current and previous periods."""
    trends = []
    if not prev_usage:
        return trends

    metrics = [
        ("entities", current_usage.entities, prev_usage.entities),
        ("queries", current_usage.queries, prev_usage.queries),
        ("syncs", current_usage.syncs, prev_usage.syncs),
    ]

    for metric_name, current_val, prev_val in metrics:
        if prev_val > 0:
            percentage_change = ((current_val - prev_val) / prev_val) * 100
            direction = (
                "up" if percentage_change > 5 else "down" if percentage_change < -5 else "stable"
            )
        else:
            percentage_change = 100 if current_val > 0 else 0
            direction = "up" if current_val > 0 else "stable"

        trends.append(
            UsageTrend(
                metric=metric_name,
                direction=direction,
                percentage_change=round(percentage_change, 1),
            )
        )

    return trends


async def _build_previous_periods(
    db: AsyncSession,
    organization_id: UUID,
    limit: int = 6,
) -> List[BillingPeriodUsage]:
    """Build list of previous billing period usage data."""
    previous_periods_data = await crud.billing_period.get_previous_periods(
        db, organization_id=organization_id, limit=limit
    )

    previous_periods = []
    for period in previous_periods_data:
        period_usage = await crud.usage.get_by_billing_period(db, billing_period_id=period.id)

        period_limits = GuardRailService.PLAN_LIMITS.get(
            period.plan, GuardRailService.PLAN_LIMITS[BillingPlan.DEVELOPER]
        )

        status_str, plan_str = _get_status_and_plan_strings(period)

        previous_periods.append(
            BillingPeriodUsage(
                period_id=period.id,
                period_start=period.period_start,
                period_end=period.period_end,
                status=status_str,
                plan=plan_str,
                usage=_create_usage_snapshot(period_usage, period_limits, period.id),
                daily_usage=[],
                days_remaining=None,
                is_current=False,
            )
        )

    return previous_periods


@router.get("/dashboard", response_model=UsageDashboard)
async def get_usage_dashboard(
    period_id: Optional[UUID] = Query(None, description="Specific period to view"),
    db: AsyncSession = Depends(deps.get_db),
    ctx: ApiContext = Depends(deps.get_context),
) -> UsageDashboard:
    """Get comprehensive usage dashboard data.

    Returns current period by default, or specific period if requested.
    Includes historical data for comparison and trends.
    """
    ctx.logger.info(f"Fetching usage dashboard for organization period_id={period_id}")

    try:
        # Get target billing period
        target_period = await _get_target_period(db, period_id, ctx)
        if not target_period:
            return _create_default_dashboard()

        # Get usage and plan limits
        usage_record = await crud.usage.get_by_billing_period(
            db, billing_period_id=target_period.id
        )
        plan_limits = GuardRailService.PLAN_LIMITS.get(
            target_period.plan, GuardRailService.PLAN_LIMITS[BillingPlan.DEVELOPER]
        )

        # Create usage snapshot
        usage_snapshot = _create_usage_snapshot(usage_record, plan_limits, target_period.id)

        # Calculate period status
        now = datetime.utcnow()
        is_current = target_period.period_start <= now <= target_period.period_end
        days_remaining = (target_period.period_end - now).days if is_current else None

        # Get status and plan strings
        status_str, plan_str = _get_status_and_plan_strings(target_period)

        # Create current period usage
        current_period_usage = BillingPeriodUsage(
            period_id=target_period.id,
            period_start=target_period.period_start,
            period_end=target_period.period_end,
            status=status_str,
            plan=plan_str,
            usage=usage_snapshot,
            daily_usage=[],  # TODO: Implement daily snapshots if needed
            days_remaining=days_remaining,
            is_current=is_current,
        )

        # Get previous periods
        previous_periods = await _build_previous_periods(db, ctx.organization.id)

        # Calculate aggregate stats
        all_usage_records = await crud.usage.get_all_by_organization(
            db, organization_id=ctx.organization.id
        )
        total_entities_all_time = (
            sum(u.entities for u in all_usage_records) if all_usage_records else 0
        )
        total_queries_all_time = (
            sum(u.queries for u in all_usage_records) if all_usage_records else 0
        )

        # Calculate daily averages
        average_daily_entities = 0
        average_daily_queries = 0
        if is_current and days_remaining is not None:
            days_elapsed = (now - target_period.period_start).days + 1
            if days_elapsed > 0:
                average_daily_entities = usage_snapshot.entities // days_elapsed
                average_daily_queries = usage_snapshot.queries // days_elapsed

        # Calculate trends
        trends = []
        if previous_periods and usage_record:
            prev_usage = await crud.usage.get_by_billing_period(
                db, billing_period_id=previous_periods[0].period_id
            )
            trends = _calculate_trends(usage_snapshot, prev_usage)

        return UsageDashboard(
            current_period=current_period_usage,
            previous_periods=previous_periods,
            total_entities_all_time=total_entities_all_time,
            total_queries_all_time=total_queries_all_time,
            average_daily_entities=average_daily_entities,
            average_daily_queries=average_daily_queries,
            trends=trends,
        )

    except HTTPException:
        raise
    except Exception as e:
        ctx.logger.error(f"Failed to fetch usage dashboard: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Failed to fetch usage dashboard: {str(e)}"
        ) from e
