"""Spotlight search evaluator.

The evaluator assesses search results and decides whether to continue searching
or stop. It provides result summaries that become part of search history.
"""

from pathlib import Path

from airweave.core.logging import ContextualLogger
from airweave.search.spotlight.external.llm.interface import SpotlightLLMInterface
from airweave.search.spotlight.external.tokenizer.interface import SpotlightTokenizerInterface
from airweave.search.spotlight.schemas.evaluation import SpotlightEvaluation
from airweave.search.spotlight.schemas.filter import format_filter_groups_md
from airweave.search.spotlight.schemas.history import SpotlightHistory
from airweave.search.spotlight.schemas.search_result import SpotlightSearchResults
from airweave.search.spotlight.schemas.state import SpotlightState


class SpotlightEvaluator:
    """Evaluates search results and decides whether to continue searching.

    The evaluator:
    1. Analyzes the current search results against the user query
    2. Creates summaries of each result for history
    3. Decides whether to continue searching or stop
    4. Provides advice for the planner if continuing
    """

    # Path to context markdown files (relative to this module)
    CONTEXT_DIR = Path(__file__).parent.parent / "context"

    # Reserve this fraction of context_window for reasoning (CoT)
    REASONING_BUFFER_FRACTION = 0.15

    def __init__(
        self,
        llm: SpotlightLLMInterface,
        tokenizer: SpotlightTokenizerInterface,
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

    async def evaluate(self, state: SpotlightState) -> SpotlightEvaluation:
        """Evaluate search results and decide whether to continue searching.

        Args:
            state: The current spotlight state with populated search results.

        Returns:
            An evaluation with result summaries and continue/stop decision.
        """
        prompt = self._build_prompt(state)

        # Log dynamic context
        self._log_dynamic_context(state)

        prompt_tokens = self._tokenizer.count_tokens(prompt)
        self._logger.debug(f"[Evaluator] Total prompt: {prompt_tokens:,} tokens")

        evaluation = await self._llm.structured_output(prompt, SpotlightEvaluation)

        # Log the evaluation
        self._log_evaluation(evaluation)

        return evaluation

    def _log_dynamic_context(self, state: SpotlightState) -> None:
        """Log the dynamic parts of the prompt context."""
        results = state.current_iteration.search_results
        result_count = len(results) if results else 0
        history_count = len(state.history.iterations) if state.history else 0

        self._logger.debug(
            f"[Evaluator] Evaluating iteration {state.iteration_number}:\n"
            f"  - Query: {state.user_query}\n"
            f"  - Results to evaluate: {result_count}\n"
            f"  - History iterations: {history_count}"
        )

    def _log_evaluation(self, evaluation: SpotlightEvaluation) -> None:
        """Log the evaluation result."""
        decision = "CONTINUE" if evaluation.should_continue else "STOP"
        self._logger.info(
            f"[Evaluator] Decision: {decision}\n"
            f"  - Reasoning: {evaluation.reasoning}\n"
            f"  - Results summarized: {len(evaluation.result_summaries)}"
            + (f"\n  - Advice: {evaluation.advice}" if evaluation.advice else "")
        )

    def _build_prompt(self, state: SpotlightState) -> str:
        """Build the full prompt for the LLM.

        Budget is split equally between search results and history.

        Args:
            state: The current spotlight state.

        Returns:
            The complete prompt string.
        """
        # Validate required fields
        ci = state.current_iteration
        if ci.plan is None:
            raise ValueError("Evaluator requires plan in current_iteration")
        if ci.compiled_query is None:
            raise ValueError("Evaluator requires compiled_query in current_iteration")
        if ci.search_results is None:
            raise ValueError("Evaluator requires search_results in current_iteration")

        # Build static part (without results and history)
        static_prompt = self._build_static_prompt(state)
        static_tokens = self._tokenizer.count_tokens(static_prompt)

        # Calculate dynamic budget and split between results and history
        results_budget, history_budget = self._calculate_dynamic_budgets(static_tokens)

        # Build dynamic sections
        results_section = SpotlightSearchResults.build_results_section(
            ci.search_results, self._tokenizer, results_budget
        )
        history_section = SpotlightHistory.render_md(state.history, self._tokenizer, history_budget)

        return f"""{static_prompt}

### Search Results

{results_section}

---

## Search History

{history_section}
"""

    def _build_static_prompt(self, state: SpotlightState) -> str:
        """Build the static part of the prompt (without results and history).

        Includes plan and compiled query, but not the search results (those are
        added with budget management).

        Args:
            state: The current spotlight state.

        Returns:
            The static prompt string.
        """
        ci = state.current_iteration

        return f"""# Airweave Overview

{self._airweave_overview}

---

{self._evaluator_task}

---

## Context for This Evaluation

### User Request

User query: {state.user_query}
User filter: {format_filter_groups_md(state.user_filter)}
Mode: {state.mode.value}

### Collection Information

{state.collection_metadata.to_md()}

### Current Iteration ({state.iteration_number})

**Plan:**
{ci.plan.to_md()}

**Compiled Query:**
{ci.compiled_query.to_md()}
"""

    def _calculate_dynamic_budgets(self, static_tokens: int) -> tuple[int, int]:
        """Calculate token budgets for results and history.

        Budget is split equally between results and history. Each section
        also reserves space for its truncation notice.

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
        results_truncation_reserve = SpotlightSearchResults.get_truncation_reserve_tokens(
            self._tokenizer
        )
        history_truncation_reserve = SpotlightHistory.get_truncation_reserve_tokens(self._tokenizer)
        total_truncation_reserve = results_truncation_reserve + history_truncation_reserve

        # Total dynamic budget = input budget - static prompt - truncation reserves
        total_dynamic_budget = max_input_tokens - static_tokens - total_truncation_reserve

        # Split equally between results and history
        half_budget = max(0, total_dynamic_budget // 2)

        return half_budget, half_budget
