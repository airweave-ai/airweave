"""Agentic search evaluator.

The evaluator assesses search results and decides whether to continue searching
or stop. It is a pure decision-maker — it does not generate summaries or advice.

It sees full search history (plans, result briefs, its own previous reasoning)
so it can judge whether the search space is exhausted.
"""

from pathlib import Path

from airweave.core.logging import ContextualLogger
from airweave.search.agentic_search.external.llm.interface import AgenticSearchLLMInterface
from airweave.search.agentic_search.external.tokenizer.interface import (
    AgenticSearchTokenizerInterface,
)
from airweave.search.agentic_search.schemas.evaluation import AgenticSearchEvaluation
from airweave.search.agentic_search.schemas.filter import format_filter_groups_md
from airweave.search.agentic_search.schemas.history import AgenticSearchHistory
from airweave.search.agentic_search.schemas.search_result import AgenticSearchResults
from airweave.search.agentic_search.schemas.state import AgenticSearchState


class AgenticSearchEvaluator:
    """Evaluates search results and decides whether to continue searching.

    The evaluator:
    1. Analyzes the current search results against the user query
    2. Decides whether to continue searching or stop
    3. Provides reasoning referencing specific results by name

    It sees full history (strategy ledger + detailed iterations with plans,
    result briefs, and its own previous reasoning). History iterations are
    compact (~500 tokens each) so they fit alongside results.
    """

    # Path to context markdown files (relative to this module)
    CONTEXT_DIR = Path(__file__).parent.parent / "context"

    # Reserve this fraction of context_window for reasoning (CoT)
    REASONING_BUFFER_FRACTION = 0.15

    # Budget split: favor results over history (evaluator must see the results)
    RESULTS_BUDGET_FRACTION = 0.75

    def __init__(
        self,
        llm: AgenticSearchLLMInterface,
        tokenizer: AgenticSearchTokenizerInterface,
        logger: ContextualLogger,
    ) -> None:
        """Initialize the evaluator.

        Args:
            llm: LLM interface for generating evaluations.
            tokenizer: Tokenizer for counting tokens.
            logger: Logger for debugging.
        """
        self._llm = llm
        self._tokenizer = tokenizer
        self._logger = logger

        # Track how many results/history fit (set during prompt building)
        self._results_shown: int = 0
        self._results_total: int = 0
        self._history_shown: int = 0
        self._history_total: int = 0

        # Load static context files once
        self._airweave_overview = self._load_context_file("airweave_overview.md")
        self._evaluator_task = self._load_context_file("evaluator_task.md")

    def _load_context_file(self, filename: str) -> str:
        """Load a context markdown file.

        Args:
            filename: Name of the file in the context directory.

        Returns:
            Contents of the file.

        Raises:
            FileNotFoundError: If the file doesn't exist.
        """
        filepath = self.CONTEXT_DIR / filename
        return filepath.read_text()

    @property
    def results_shown(self) -> int:
        """Number of results included in the evaluator prompt."""
        return self._results_shown

    @property
    def results_total(self) -> int:
        """Total number of results returned by the search engine."""
        return self._results_total

    @property
    def history_shown(self) -> int:
        """Number of detailed history iterations included in the evaluator prompt."""
        return self._history_shown

    @property
    def history_total(self) -> int:
        """Total number of past iterations."""
        return self._history_total

    async def evaluate(self, state: AgenticSearchState) -> AgenticSearchEvaluation:
        """Evaluate search results and decide whether to continue searching.

        Args:
            state: The current agentic_search state with populated search results.

        Returns:
            An evaluation with reasoning and continue/stop decision.
        """
        system_prompt = self._build_system_prompt()
        user_prompt = self._build_user_prompt(state)

        system_tokens = self._tokenizer.count_tokens(system_prompt)
        user_tokens = self._tokenizer.count_tokens(user_prompt)
        self._logger.debug(
            f"[Evaluator] Prompt tokens: system={system_tokens:,}, user={user_tokens:,}, "
            f"total={system_tokens + user_tokens:,}"
        )
        self._logger.debug(
            f"[Evaluator] === SYSTEM PROMPT ===\n{system_prompt}\n"
            f"[Evaluator] === USER PROMPT ===\n{user_prompt}\n"
            f"[Evaluator] === END PROMPTS ==="
        )

        evaluation = await self._llm.structured_output(
            user_prompt, AgenticSearchEvaluation, system_prompt=system_prompt
        )

        # Log the evaluation
        self._log_evaluation(evaluation)

        return evaluation

    def _log_evaluation(self, evaluation: AgenticSearchEvaluation) -> None:
        """Log the evaluation result."""
        decision = "CONTINUE" if evaluation.should_continue else "STOP"
        self._logger.debug(
            f"[Evaluator] Decision: {decision}\n  - Reasoning: {evaluation.reasoning}"
        )

    @staticmethod
    def _format_search_error(search_error: str | None) -> str:
        """Format search error notice for the evaluator prompt."""
        if not search_error:
            return ""
        return (
            f"\n**⚠ SEARCH ERROR:** {search_error}\n"
            "The 0 results below are NOT because nothing matched, but because the "
            "search itself broke. The plan likely has an issue (e.g., invalid filters, "
            "limit too high). Continue and tell the planner to fix it.\n"
        )

    def _build_system_prompt(self) -> str:
        """Build the system prompt (static instructions).

        Contains the airweave overview and evaluator task description.
        These are the rules and guidelines the model should follow.

        Returns:
            The system prompt string.
        """
        return f"""# Airweave Overview

{self._airweave_overview}

---

{self._evaluator_task}"""

    def _build_user_prompt(self, state: AgenticSearchState) -> str:
        """Build the user prompt (dynamic context + results + history).

        Contains collection metadata, user query, plan, search results,
        and full history (plans, result briefs, previous evaluations).

        Args:
            state: The current agentic_search state.

        Returns:
            The user prompt string.
        """
        # Validate required fields
        ci = state.current_iteration
        if ci.plan is None:
            raise ValueError("Evaluator requires plan in current_iteration")
        if ci.search_results is None:
            raise ValueError("Evaluator requires search_results in current_iteration")

        # Build context part
        context_prompt = f"""## Context for This Evaluation

### User Request

User query: {state.user_query}
User filter: {format_filter_groups_md(state.user_filter)}
Mode: {state.mode.value}

### Collection Information

{state.collection_metadata.to_md()}

### Current Iteration ({state.iteration_number})

**Plan:**
{ci.plan.to_md()}
{self._format_search_error(ci.search_error)}
"""
        # Calculate budgets (accounting for system prompt too)
        system_tokens = self._tokenizer.count_tokens(self._build_system_prompt())
        context_tokens = self._tokenizer.count_tokens(context_prompt)
        results_budget, history_budget = self._calculate_dynamic_budgets(
            system_tokens + context_tokens
        )

        # Build dynamic sections
        results_info = AgenticSearchResults.build_results_section(
            ci.search_results, self._tokenizer, results_budget
        )
        self._results_shown = results_info.results_shown
        self._results_total = results_info.results_total

        history_info = AgenticSearchHistory.render_md(
            state.history, self._tokenizer, history_budget
        )
        self._history_shown = history_info.iterations_shown
        self._history_total = history_info.iterations_total

        return f"""{context_prompt}

### Search Results

{results_info.markdown}

---

## Search History

{history_info.markdown}
"""

    def _calculate_dynamic_budgets(self, static_tokens: int) -> tuple[int, int]:
        """Calculate token budgets for results and history.

        Budget is split 75/25 favoring results. The evaluator's primary job
        is to assess the CURRENT results — it needs to see as many as possible.
        History (strategy ledger + recent iterations) gets the remainder.
        With the simplified history format (~500 tokens/iteration), more
        iterations fit in the 25% budget than before.

        Args:
            static_tokens: Tokens used by the static prompt.

        Returns:
            Tuple of (results_budget, history_budget).
        """
        model_spec = self._llm.model_spec

        # Total available for input = context_window - output - reasoning_buffer
        reasoning_buffer = int(model_spec.context_window * self.REASONING_BUFFER_FRACTION)
        max_input_tokens = (
            model_spec.context_window - model_spec.max_output_tokens - reasoning_buffer
        )

        # Reserve space for both truncation notices
        results_truncation_reserve = AgenticSearchResults.get_truncation_reserve_tokens(
            self._tokenizer
        )
        history_truncation_reserve = AgenticSearchHistory.get_truncation_reserve_tokens(
            self._tokenizer
        )
        total_truncation_reserve = results_truncation_reserve + history_truncation_reserve

        # Total dynamic budget = input budget - static prompt - truncation reserves
        total_dynamic_budget = max_input_tokens - static_tokens - total_truncation_reserve

        # Split: 75% results, 25% history
        results_budget = max(0, int(total_dynamic_budget * self.RESULTS_BUDGET_FRACTION))
        history_budget = max(0, total_dynamic_budget - results_budget)

        return results_budget, history_budget
