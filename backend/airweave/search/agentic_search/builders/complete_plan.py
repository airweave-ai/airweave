"""Builder for the complete search plan.

Combines the LLM-generated plan with user-supplied deterministic filters.
"""

from typing import List

from airweave.search.agentic_search.schemas.filter import AgenticSearchFilterGroup
from airweave.search.agentic_search.schemas.plan import AgenticSearchPlan


class AgenticSearchCompletePlanBuilder:
    """Builds the complete plan by combining LLM-generated filters with user filters.

    The planner generates a plan with its own filters. The complete plan appends
    user-supplied deterministic filters on top. The original plan stays clean
    (LLM filters only) for history and evaluator context, while the complete plan
    is what gets compiled and executed against the vector database.
    """

    @staticmethod
    def build(
        plan: AgenticSearchPlan,
        user_filter: List[AgenticSearchFilterGroup],
    ) -> AgenticSearchPlan:
        """Build the complete plan by merging planner and user filters.

        If user filters exist, creates a deep copy of the plan and appends them.
        If no user filters, returns the original plan unchanged (no copy overhead).

        Args:
            plan: The LLM-generated search plan.
            user_filter: User-supplied deterministic filter groups (may be empty).

        Returns:
            The complete plan with combined filters.
        """
        if not user_filter:
            return plan

        complete_plan = plan.model_copy(deep=True)
        complete_plan.filter_groups.extend(user_filter)
        return complete_plan
