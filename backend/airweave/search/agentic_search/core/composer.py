"""AgenticSearch answer composer.

The composer synthesizes search results into a clear, well-cited answer.
"""

from pathlib import Path

from airweave.core.logging import ContextualLogger
from airweave.search.agentic_search.external.llm.interface import AgenticSearchLLMInterface
from airweave.search.agentic_search.external.tokenizer.interface import (
    AgenticSearchTokenizerInterface,
)
from airweave.search.agentic_search.schemas.answer import AgenticSearchAnswer
from airweave.search.agentic_search.schemas.evaluation import AgenticSearchEvaluation
from airweave.search.agentic_search.schemas.filter import format_filter_groups_md
from airweave.search.agentic_search.schemas.history import AgenticSearchHistory
from airweave.search.agentic_search.schemas.request import AgenticSearchMode
from airweave.search.agentic_search.schemas.search_result import AgenticSearchResults
from airweave.search.agentic_search.schemas.state import AgenticSearchState


class AgenticSearchComposer:
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
        llm: AgenticSearchLLMInterface,
        tokenizer: AgenticSearchTokenizerInterface,
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

    async def compose(self, state: AgenticSearchState) -> AgenticSearchAnswer:
        """Compose the final answer from search results.

        Args:
            state: The final agentic_search state with search results and evaluation.

        Returns:
            A AgenticSearchAnswer with text and citations.
        """
        system_prompt = self._build_system_prompt()
        user_prompt = self._build_user_prompt(state)

        system_tokens = self._tokenizer.count_tokens(system_prompt)
        user_tokens = self._tokenizer.count_tokens(user_prompt)
        self._logger.debug(
            f"[Composer] Prompt tokens: system={system_tokens:,}, user={user_tokens:,}, "
            f"total={system_tokens + user_tokens:,}"
        )
        self._logger.debug(
            f"[Composer] === SYSTEM PROMPT ===\n{system_prompt}\n"
            f"[Composer] === USER PROMPT ===\n{user_prompt}\n"
            f"[Composer] === END PROMPTS ==="
        )

        answer = await self._llm.structured_output(
            user_prompt, AgenticSearchAnswer, system_prompt=system_prompt
        )

        # Log the answer
        self._log_answer(answer)

        return answer

    def _log_answer(self, answer: AgenticSearchAnswer) -> None:
        """Log the composed answer."""
        text_preview = answer.text[:200] + "..." if len(answer.text) > 200 else answer.text
        self._logger.debug(
            f"[Composer] Answer composed:\n"
            f"  - Text length: {len(answer.text)} chars\n"
            f"  - Citations: {len(answer.citations)}\n"
            f"  - Preview: {text_preview}"
        )

    def _build_system_prompt(self) -> str:
        """Build the system prompt (static instructions).

        Contains the airweave overview and composer task description.

        Returns:
            The system prompt string.
        """
        return f"""# Airweave Overview

{self._airweave_overview}

---

{self._composer_task}"""

    def _build_user_prompt(self, state: AgenticSearchState) -> str:
        """Build the user prompt (dynamic context + results + history).

        Contains collection metadata, user query, plan, evaluation, search results,
        and history. Token budget is managed to fit results and history.

        Args:
            state: The current agentic_search state.

        Returns:
            The user prompt string.
        """
        # Validate required fields
        ci = state.current_iteration
        if ci.plan is None:
            raise ValueError("Composer requires plan in current_iteration")
        # compiled_query may be None if filter translation failed (e.g., invalid
        # timestamp format). The template already handles this with a fallback.
        if ci.search_results is None:
            raise ValueError("Composer requires search_results in current_iteration")
        # Evaluation is only available in normal agentic iterations
        # (fast mode and consolidation pass skip evaluation)
        is_fast = state.mode == AgenticSearchMode.FAST
        if ci.evaluation is None and not is_fast and not state.is_consolidation:
            raise ValueError("Composer requires evaluation in current_iteration for thinking mode")

        # Build context part
        context_prompt = f"""## Context for This Answer

### User Request

User query: {state.user_query}
User filter: {format_filter_groups_md(state.user_filter)}
Mode: {state.mode.value}

### Collection Information

{state.collection_metadata.to_md()}

### Iteration Number

This is iteration **{state.iteration_number}** (final).
{
            ""
            if not state.is_consolidation
            else '''
**⚠ CONSOLIDATION PASS:** The search loop ended WITHOUT finding a direct answer to the
user's query. This final iteration was a targeted consolidation search to surface the
most relevant content found across all iterations. The results below are the BEST
AVAILABLE material, not a direct answer. Your response should acknowledge that no direct
answer was found and present what IS available as the most relevant information.
'''
        }
---

## Current Iteration (Final)

### Plan

{ci.plan.to_md()}

### Compiled Query

{ci.compiled_query.to_md() if ci.compiled_query else "*(No compiled query available.)*"}

### Evaluation

{AgenticSearchEvaluation.render_md(ci.evaluation)}
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
        history_info = AgenticSearchHistory.render_md(
            state.history, self._tokenizer, history_budget
        )

        return f"""{context_prompt}

### Search Results

{results_info.markdown}

---

## Search History

{history_info.markdown}
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
