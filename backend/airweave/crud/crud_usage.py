"""CRUD operations for Usage model."""

from typing import Dict, Optional
from uuid import UUID

from sqlalchemy import and_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from airweave.core.shared_models import ActionType
from airweave.crud._base_organization import CRUDBaseOrganization
from airweave.models.usage import Usage
from airweave.schemas.usage import UsageCreate, UsageUpdate


class CRUDUsage(CRUDBaseOrganization[Usage, UsageCreate, UsageUpdate]):
    """CRUD operations for Usage model."""

    async def get_by_billing_period(
        self,
        db: AsyncSession,
        *,
        billing_period_id: UUID,
    ) -> Optional[Usage]:
        """Get usage record by billing period ID.

        Args:
            db: Database session
            billing_period_id: Billing period ID

        Returns:
            Usage record for the billing period or None
        """
        query = select(self.model).where(self.model.billing_period_id == billing_period_id)
        result = await db.execute(query)
        return result.scalar_one_or_none()

    async def get_current_usage(
        self,
        db: AsyncSession,
        *,
        organization_id: UUID,
    ) -> Optional[Usage]:
        """Get usage for the current active billing period.

        Note: team_members field will be None as it's not stored in the database.
        The caller should populate it separately if needed.

        Args:
            db: Database session
            organization_id: Organization ID

        Returns:
            Current usage record or None if no active period
        """
        from datetime import datetime

        from airweave.core.logging import logger
        from airweave.models.billing_period import BillingPeriod
        from airweave.schemas.billing_period import BillingPeriodStatus

        now = datetime.utcnow()
        logger.info(
            f"[get_current_usage] Looking for usage record for org {organization_id} at {now}"
        )

        # First, let's check what billing periods exist for debugging
        debug_query = select(BillingPeriod).where(BillingPeriod.organization_id == organization_id)
        debug_result = await db.execute(debug_query)
        all_periods = debug_result.scalars().all()

        logger.info(f"[get_current_usage] Found {len(all_periods)} billing periods for org:")
        for period in all_periods:
            logger.info(
                f"  - Period {period.id}: status={period.status}, "
                f"start={period.period_start}, end={period.period_end}, "
                f"is_current={(period.period_start <= now <= period.period_end)}"
            )

        # Single query with join
        query = (
            select(self.model)
            .join(BillingPeriod, self.model.billing_period_id == BillingPeriod.id)
            .where(
                and_(
                    BillingPeriod.organization_id == organization_id,
                    BillingPeriod.period_start <= now,
                    BillingPeriod.period_end > now,
                    BillingPeriod.status.in_(
                        [
                            BillingPeriodStatus.ACTIVE,
                            BillingPeriodStatus.TRIAL,
                            BillingPeriodStatus.GRACE,
                        ]
                    ),
                )
            )
        )

        result = await db.execute(query)
        usage_record = result.scalar_one_or_none()

        if usage_record:
            logger.info(
                f"[get_current_usage] Found usage record {usage_record.id} "
                f"for billing_period_id={usage_record.billing_period_id}"
            )
        else:
            logger.warning(
                "[get_current_usage] No usage record found for current billing period. "
                "This could mean: 1) No active billing period at current time, "
                "2) Billing period exists but no usage record, "
                "3) Billing period has wrong status"
            )

        return usage_record

    async def increment_usage(
        self,
        db: AsyncSession,
        *,
        organization_id: UUID,
        increments: Dict[ActionType, int],
    ) -> Optional[Usage]:
        """Atomically increment usage counters for the current billing period.

        This method uses raw SQL to ensure atomic updates that add to existing
        values rather than overwriting them, which is crucial for concurrent access.

        Args:
            db: Database session
            organization_id: The organization ID to increment usage for
            increments: Dictionary mapping ActionType to increment amount

        Returns:
            The updated usage record after increment, or None if no active period
        """
        from airweave.core.logging import logger

        logger.info(
            f"[increment_usage] Called for org {organization_id} with increments: {increments}"
        )

        # Get current usage record
        current_usage = await self.get_current_usage(db, organization_id=organization_id)
        if not current_usage:
            logger.error(
                f"[increment_usage] No current usage record found for org {organization_id}. "
                f"Cannot increment usage without an active billing period with usage record."
            )
            return None

        # Store the ID before any operations that might invalidate the object
        usage_id = current_usage.id

        logger.info(
            f"[increment_usage] Found usage record {usage_id}, "
            f"current values: entities={current_usage.entities}, "
            f"queries={current_usage.queries}"
        )

        # Build the atomic UPDATE query
        update_parts = []
        params = {"usage_id": usage_id}

        for action_type, increment in increments.items():
            if increment != 0:  # Handle both positive and negative increments
                field = action_type.value
                update_parts.append(f"{field} = {field} + :{field}_inc")
                params[f"{field}_inc"] = increment

        if update_parts:
            # Execute atomic update
            query = text(
                f"""
                UPDATE usage
                SET {", ".join(update_parts)},
                    modified_at = NOW()
                WHERE id = :usage_id
                RETURNING id, organization_id, entities, queries,
                        billing_period_id, created_at, modified_at
            """
            )

            logger.info(f"[increment_usage] Executing SQL update with params: {params}")
            result = await db.execute(query, params)

            # Fetch the updated row BEFORE committing to avoid cursor invalidation
            updated_row = result.first()

            # Commit the transaction
            await db.commit()
            logger.info("[increment_usage] SQL update committed successfully")

            if updated_row:
                # Buffer values explicitly to decouple from the DB cursor
                updated_values = {
                    "id": updated_row.id,
                    "organization_id": updated_row.organization_id,
                    "entities": updated_row.entities,
                    "queries": updated_row.queries,
                    "billing_period_id": updated_row.billing_period_id,
                    "created_at": updated_row.created_at,
                    "modified_at": updated_row.modified_at,
                }

                # Create SQLAlchemy model first (without team_members or source_connections)
                updated_model = Usage(
                    id=updated_values["id"],
                    organization_id=updated_values["organization_id"],
                    entities=updated_values["entities"],
                    queries=updated_values["queries"],
                    billing_period_id=updated_values["billing_period_id"],
                    created_at=updated_values["created_at"],
                    modified_at=updated_values["modified_at"],
                )

                # Convert to Pydantic schema and add computed fields
                from airweave.schemas.usage import Usage as UsageSchema

                updated = UsageSchema.model_validate(updated_model)
                # Computed fields not stored in DB, populated separately by guard_rail
                updated.team_members = None
                updated.source_connections = None

                logger.info(
                    f"[increment_usage] Updated values: "
                    f"entities={updated.entities}, queries={updated.queries}"
                )
                return updated
            else:
                logger.error("[increment_usage] No row returned from UPDATE query")
                return None

        return current_usage

    async def get_all_by_organization(
        self,
        db: AsyncSession,
        *,
        organization_id: UUID,
    ) -> list[Usage]:
        """Get all usage records for an organization.

        Args:
            db: Database session
            organization_id: Organization ID

        Returns:
            List of all usage records for the organization
        """
        query = select(self.model).where(self.model.organization_id == organization_id)
        result = await db.execute(query)
        return result.scalars().all()

    async def get_current_usage_for_orgs(
        self,
        db: AsyncSession,
        *,
        organization_ids: list[UUID],
    ) -> dict[UUID, Usage]:
        """Get current usage for multiple organizations (admin use only).

        This method fetches the most recent usage record for each organization
        that has an active billing period. Returns a mapping of org_id -> Usage.

        Args:
            db: Database session
            organization_ids: List of organization IDs

        Returns:
            Dictionary mapping organization_id to current Usage record
        """
        from datetime import datetime

        from airweave.models.billing_period import BillingPeriod
        from airweave.schemas.billing_period import BillingPeriodStatus

        if not organization_ids:
            return {}

        now = datetime.utcnow()

        # Query for current usage records with active billing periods
        query = (
            select(self.model)
            .join(BillingPeriod, self.model.billing_period_id == BillingPeriod.id)
            .where(
                and_(
                    BillingPeriod.organization_id.in_(organization_ids),
                    BillingPeriod.period_start <= now,
                    BillingPeriod.period_end > now,
                    BillingPeriod.status.in_(
                        [
                            BillingPeriodStatus.ACTIVE,
                            BillingPeriodStatus.TRIAL,
                            BillingPeriodStatus.GRACE,
                        ]
                    ),
                )
            )
        )

        result = await db.execute(query)
        usage_records = result.scalars().all()

        # Return as a dictionary for easy lookup
        return {usage.organization_id: usage for usage in usage_records}


# Create instance
usage = CRUDUsage(Usage, track_user=False)
