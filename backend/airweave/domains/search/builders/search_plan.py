"""Builder for the complete search plan.

Combines the LLM-generated plan with user-supplied deterministic filters.
User filters are AND'd into every LLM filter group — they are constraints
that must always be satisfied, not optional additions.
"""

from typing import List

from airweave.domains.search.types.filters import FilterGroup
from airweave.domains.search.types.plan import SearchPlan


class SearchPlanBuilder:
    """Builds the complete plan by AND'ing user filters into LLM filters.

    User filters are leading — they restrict all results. If the user
    filters on source_name="github", no results from other sources can
    ever be returned, regardless of what the LLM generates.

    Merge logic:
    - If the LLM has filter groups: inject user filter conditions into
      each LLM group (AND'd together within each group).
    - If the LLM has no filter groups: create a single group from the
      user filter conditions.
    - If no user filters: return the plan unchanged.
    """

    @staticmethod
    def build(
        plan: SearchPlan,
        user_filter: List[FilterGroup],
    ) -> SearchPlan:
        """Build the complete plan by AND'ing user filters into LLM filters.

        Args:
            plan: The LLM-generated search plan.
            user_filter: User-supplied deterministic filter groups.
                Each group's conditions are AND'd into every LLM filter group.

        Returns:
            The complete plan with user filters AND'd in.
        """
        if not user_filter:
            return plan

        # Collect all user filter conditions (flattened from all user groups)
        user_conditions = []
        for uf_group in user_filter:
            user_conditions.extend(uf_group.conditions)

        if not user_conditions:
            return plan

        complete_plan = plan.model_copy(deep=True)

        if complete_plan.filter_groups:
            # AND user conditions into each existing LLM group
            for group in complete_plan.filter_groups:
                group.conditions.extend(user_conditions)
        else:
            # No LLM groups — create one from user conditions alone
            complete_plan.filter_groups = [
                FilterGroup(conditions=list(user_conditions))
            ]

        return complete_plan
