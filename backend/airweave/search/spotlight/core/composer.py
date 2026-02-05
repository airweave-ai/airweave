"""Spotlight answer composer.

The composer synthesizes search results into a clear, well-cited answer.
"""

from pathlib import Path

from airweave.core.logging import ContextualLogger
from airweave.search.spotlight.external.llm.interface import SpotlightLLMInterface
from airweave.search.spotlight.external.tokenizer.interface import SpotlightTokenizerInterface
from airweave.search.spotlight.schemas.answer import SpotlightAnswer
from airweave.search.spotlight.schemas.history import SpotlightHistory
from airweave.search.spotlight.schemas.search_result import SpotlightSearchResults
from airweave.search.spotlight.schemas.state import SpotlightState


class SpotlightComposer:
    """Composes the final answer from search results.

    The composer:
    1. Takes the final state with plan, query, results, and evaluation
    2. Synthesizes a clear, concise answer
    3. Lists sources used in the answer
    """

    # Path to context markdown files (relative to this module)
    CONTEXT_DIR = Path(__file__).parent.parent / "context"

    # Reserve this fraction of context_window for reasoning (CoT)
    REASONING_BUFFER_FRACTION = 0.15

    # Budget split: favor results over history (results are the source material)
    RESULTS_BUDGET_FRACTION = 0.75

    def __init__(
        self,
        llm: SpotlightLLMInterface,
        tokenizer: SpotlightTokenizerInterface,
        logger: ContextualLogger,
    ) -> None:
        """Initialize the composer.

        Args:
            llm: LLM interface for generating answers.
            tokenizer: Tokenizer for counting tokens.
            logger: Logger for debugging.
        """
        self._llm = llm
        self._tokenizer = tokenizer
        self._logger = logger

        # Load static context files once
        self._airweave_overview = self._load_context_file("airweave_overview.md")
        self._composer_task = self._load_context_file("composer_task.md")

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

    async def compose(self, state: SpotlightState) -> SpotlightAnswer:
        """Compose the final answer from search results.

        Args:
            state: The final spotlight state with search results and evaluation.

        Returns:
            A SpotlightAnswer with text and citations.
        """
        prompt = self._build_prompt(state)

        # Log context info
        self._log_context(state)

        prompt_tokens = self._tokenizer.count_tokens(prompt)
        self._logger.debug(f"[Composer] Total prompt: {prompt_tokens:,} tokens")

        # Log full prompt for debugging
        self._logger.debug(f"[Composer] Full prompt:\n{prompt}")

        answer = await self._llm.structured_output(prompt, SpotlightAnswer)

        # Log the answer
        self._log_answer(answer)

        return answer

    def _log_context(self, state: SpotlightState) -> None:
        """Log the context being used for composition."""
        results = state.current_iteration.search_results
        result_count = len(results) if results else 0
        history_count = len(state.history.iterations) if state.history else 0

        self._logger.debug(
            f"[Composer] Composing answer:\n"
            f"  - Query: {state.user_query}\n"
            f"  - Iteration: {state.iteration_number}\n"
            f"  - Results available: {result_count}\n"
            f"  - History iterations: {history_count}"
        )

    def _log_answer(self, answer: SpotlightAnswer) -> None:
        """Log the composed answer."""
        text_preview = answer.text[:200] + "..." if len(answer.text) > 200 else answer.text
        self._logger.info(
            f"[Composer] Answer composed:\n"
            f"  - Text length: {len(answer.text)} chars\n"
            f"  - Citations: {len(answer.citations)}\n"
            f"  - Preview: {text_preview}"
        )

    def _build_prompt(self, state: SpotlightState) -> str:
        """Build the full prompt for the LLM.

        Budget is split 75/25 between results and history.

        Args:
            state: The current spotlight state.

        Returns:
            The complete prompt string.
        """
        # Validate required fields
        ci = state.current_iteration
        if ci.plan is None:
            raise ValueError("Composer requires plan in current_iteration")
        if ci.compiled_query is None:
            raise ValueError("Composer requires compiled_query in current_iteration")
        if ci.search_results is None:
            raise ValueError("Composer requires search_results in current_iteration")
        if ci.evaluation is None:
            raise ValueError("Composer requires evaluation in current_iteration")

        # Build static part (without results and history)
        static_prompt = self._build_static_prompt(state)
        static_tokens = self._tokenizer.count_tokens(static_prompt)

        # Calculate dynamic budgets (75% results, 25% history)
        results_budget, history_budget = self._calculate_dynamic_budgets(static_tokens)

        # Build dynamic sections
        results_section = SpotlightSearchResults.build_results_section(
            ci.search_results, self._tokenizer, results_budget
        )
        history_section = SpotlightHistory.build_history_section(
            state.history, self._tokenizer, history_budget
        )

        return f"""{static_prompt}

### Search Results

{results_section}

---

## Search History

{history_section}
"""

    def _build_static_prompt(self, state: SpotlightState) -> str:
        """Build the static part of the prompt.

        Includes everything except results and history (which are budget-constrained).

        Args:
            state: The current spotlight state.

        Returns:
            The static prompt string.
        """
        ci = state.current_iteration
        return f"""# Airweave Overview

{self._airweave_overview}

---

{self._composer_task}

---

## Context for This Answer

### User Query

{state.user_query}

### Collection Information

{state.collection_metadata.to_md()}

### Iteration Number

This is iteration **{state.iteration_number}** (final).

---

## Current Iteration (Final)

### Plan

{ci.plan.to_md()}

### Compiled Query

{ci.compiled_query.to_md()}

### Evaluation

{ci.evaluation.to_md()}
"""

    def _calculate_dynamic_budgets(self, static_tokens: int) -> tuple[int, int]:
        """Calculate token budgets for results and history.

        Budget is split 75/25 favoring results (the source material for answers).

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

        # Split: 75% results, 25% history
        results_budget = max(0, int(total_dynamic_budget * self.RESULTS_BUDGET_FRACTION))
        history_budget = max(0, total_dynamic_budget - results_budget)

        return results_budget, history_budget
