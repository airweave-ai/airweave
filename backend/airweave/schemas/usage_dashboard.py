"""Usage dashboard schemas for comprehensive usage visualization."""

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class UsageSnapshot(BaseModel):
    """Point-in-time usage data with limits."""

    # Current values
    entities: int = Field(..., description="Total entities processed")
    queries: int = Field(..., description="Search queries executed")
    source_connections: int = Field(..., description="Source connections configured")
    team_members: int = Field(..., description="Team members in the organization")

    # Limits (None = unlimited)
    max_entities: Optional[int] = Field(None, description="Maximum entities allowed")
    max_queries: Optional[int] = Field(None, description="Maximum queries allowed")
    max_source_connections: Optional[int] = Field(
        None, description="Maximum source connections allowed"
    )
    max_team_members: Optional[int] = Field(None, description="Maximum team members allowed")

    # Metadata
    timestamp: datetime = Field(..., description="When this snapshot was taken")
    billing_period_id: UUID = Field(..., description="Associated billing period")

    model_config = ConfigDict(from_attributes=True)


class BillingPeriodUsage(BaseModel):
    """Complete usage data for a billing period."""

    period_id: UUID = Field(..., description="Billing period ID")
    period_start: datetime = Field(..., description="Period start date")
    period_end: datetime = Field(..., description="Period end date")
    status: str = Field(..., description="Period status (active, trial, ended, etc)")
    plan: str = Field(..., description="Subscription plan for this period")

    # Usage snapshot at period end (or current if active)
    usage: UsageSnapshot = Field(..., description="Current usage snapshot")

    # Daily usage trend (last 30 days or full period)
    daily_usage: List[UsageSnapshot] = Field(
        default_factory=list, description="Daily snapshots for trend visualization", max_length=30
    )

    # Computed fields
    days_remaining: Optional[int] = Field(None, description="Days left in period")
    is_current: bool = Field(False, description="Whether this is the current period")

    model_config = ConfigDict(from_attributes=True)


class UsageTrend(BaseModel):
    """Usage trend information."""

    metric: str = Field(..., description="Metric name (syncs, entities, etc)")
    direction: str = Field(..., description="Trend direction: up, down, or stable")
    percentage_change: float = Field(..., description="Percentage change from previous period")

    model_config = ConfigDict(from_attributes=True)


class UsageDashboard(BaseModel):
    """Complete dashboard data."""

    current_period: BillingPeriodUsage = Field(..., description="Current billing period usage")
    previous_periods: List[BillingPeriodUsage] = Field(
        default_factory=list,
        description="Historical billing periods",
        max_length=6,  # Last 6 periods
    )

    # Quick stats
    total_entities_all_time: int = Field(0, description="Total entities processed all time")
    total_queries_all_time: int = Field(0, description="Total queries executed all time")
    average_daily_entities: int = Field(0, description="Average entities per day (current period)")
    average_daily_queries: int = Field(0, description="Average queries per day (current period)")

    # Trends
    trends: List[UsageTrend] = Field(
        default_factory=list, description="Usage trends compared to previous period"
    )

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "examples": [
                {
                    "current_period": {
                        "period_id": "550e8400-e29b-41d4-a716-446655440000",
                        "period_start": "2024-01-01T00:00:00Z",
                        "period_end": "2024-01-31T23:59:59Z",
                        "status": "active",
                        "plan": "developer",
                        "usage": {
                            "entities": 45000,
                            "queries": 89,
                            "source_connections": 3,
                            "team_members": 2,
                            "max_entities": 100000,
                            "max_queries": 1000,
                            "max_source_connections": 10,
                            "max_team_members": 2,
                            "timestamp": "2024-01-15T12:00:00Z",
                            "billing_period_id": "550e8400-e29b-41d4-a716-446655440000",
                        },
                        "daily_usage": [],
                        "days_remaining": 16,
                        "is_current": True,
                    },
                    "previous_periods": [],
                    "total_entities_all_time": 150000,
                    "total_queries_all_time": 500,
                    "average_daily_entities": 3000,
                    "average_daily_queries": 6,
                    "trends": [
                        {"metric": "entities", "direction": "up", "percentage_change": 12.5}
                    ],
                }
            ]
        },
    )
