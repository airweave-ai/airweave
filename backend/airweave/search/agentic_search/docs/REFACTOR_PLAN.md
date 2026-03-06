# Agentic Search Refactor: Conversation + Tool Calling

## Overview

Replace the current pipeline architecture (separate planner → evaluator → composer LLM calls
with manually reconstructed history) with a single-conversation tool-calling architecture where
one model instance searches, evaluates, and composes in a continuous conversation.

### What changes

| Current | New |
|---------|-----|
| 3 separate LLM calls per iteration (planner, evaluator, composer) | 1 continuous conversation with tool calls |
| History manually reconstructed as markdown each call | Conversation naturally accumulates (messages array grows) |
| Planner outputs structured JSON plan (with `reasoning` field) | Model reasons in free text, then calls `search` tool with parameters |
| Evaluator outputs structured JSON evaluation | Model evaluates in its own reasoning (natural text between tool calls) |
| Composer outputs structured JSON answer | Model calls `submit_answer` tool with text + citations |
| Context managed by token budgets per call | Context managed by 3-layer pruning system |
| `AgenticSearchHistory` with strategy ledger + detailed iterations | Conversation messages array IS the history |

### What stays the same

- Vespa integration (compile_query, execute_query) — unchanged
- Embedder (dense + sparse) — unchanged, called inside the search tool execution
- Filter system (schemas, translator) — unchanged
- Search result schema — unchanged
- Request/Response schemas — unchanged (submit_answer produces the same shape)
- Services container — modified but same structure
- Fallback chain LLM — extended, not replaced
- API endpoints — same interface, internal changes only
- Config — same structure

---

## Phase 1: Define the Tools

The model gets two tools: `search` and `submit_answer`. When the model wants to search,
it writes its reasoning as free text and then calls the `search` tool with parameters.
When it's done, it calls `submit_answer` with the final answer.

### 1.1 `search` tool

Reuse the existing `AgenticSearchPlan` schema (minus `reasoning`) as the tool input.
The reasoning is now the model's natural text before the tool call — no need to duplicate
it in the tool parameters.

**Schema change to `AgenticSearchPlan`:**
- Remove the `reasoning` field (model's reasoning is now free text in the conversation)
- Keep everything else: `query`, `filter_groups`, `limit`, `offset`, `retrieval_strategy`
- The schema becomes the tool's `parameters` via `AgenticSearchPlan.model_json_schema()`

```python
# schemas/plan.py — updated
class AgenticSearchPlan(BaseModel):
    """Search tool input. The model calls this to search the vector database."""

    query: AgenticSearchQuery
    filter_groups: list[AgenticSearchFilterGroup] = Field(default_factory=list, ...)
    limit: int = Field(..., ge=1, le=200)
    offset: int = Field(..., ge=0)
    retrieval_strategy: AgenticSearchRetrievalStrategy = Field(...)
```

**Tool definition** (what gets sent to the LLM API):
```python
SEARCH_TOOL = {
    "type": "function",
    "function": {
        "name": "search",
        "description": "Search the vector database for relevant entities. "
                       "Use different retrieval strategies and filters to refine results.",
        "parameters": AgenticSearchPlan.model_json_schema(),
    }
}
```

**Tool execution** (what happens server-side when the model calls this):
1. Parse tool arguments into `AgenticSearchPlan`
2. Merge model's filter_groups with user's filter (same as current `CompletePlanBuilder`)
3. Call `AgenticSearchEmbedder.embed()` with query + strategy
4. Call `vector_db.compile_query()` with plan + embeddings + collection_id
5. Call `vector_db.execute_query()` with compiled query
6. Format results as text for the tool response
7. Emit `SearchingEvent` via SSE

**Tool output** (what the model sees as the tool result):
- Formatted search results (using `AgenticSearchResult.to_md()` for each result)
- Result count and relevance scores
- Truncated to fit within budget (drop lowest-ranked results, never truncate individual
  results mid-text)

### 1.2 `submit_answer` tool

Reuse the existing `AgenticSearchAnswer` schema directly as the tool input.
No new schema needed — it already has `text` and `citations`.

```python
SUBMIT_ANSWER_TOOL = {
    "type": "function",
    "function": {
        "name": "submit_answer",
        "description": "Submit the final answer with citations. Call this when you have "
                       "enough information to answer the user's query, or when further "
                       "searching would not improve the answer.",
        "parameters": AgenticSearchAnswer.model_json_schema(),
    }
}
```

**Tool execution:**
1. Parse tool arguments into `AgenticSearchAnswer`
2. Validate citations reference results seen in the conversation
3. Build `AgenticSearchResponse` with answer + final results
4. Emit `DoneEvent`
5. Signal the conversation loop to stop

### 1.3 Files to create/modify

- **Create:** `core/tools.py` — tool definitions, execution logic, result formatting
- **Modify:** `schemas/plan.py` — remove `reasoning` field, clean up `to_md()` (no longer
  needed for history, but keep for event/debugging)
- **Keep as-is:** `schemas/answer.py` — used directly as submit_answer input

---

## Phase 2: Merge Prompts into One System Prompt

### 2.1 New system prompt structure

Create a single `context/agent_task.md` that merges planner, evaluator, and composer guidance:

```markdown
## Your Task

You are an information retrieval agent. You search a vector database to find entities
that answer the user's query. You have two tools:

- `search`: Search the database with a query, filters, and retrieval strategy
- `submit_answer`: Submit your final answer with citations

### How You Work

1. Think about what to search for (write your reasoning as text)
2. Call the `search` tool with your query parameters
3. Review the results that come back
4. Either:
   a. Search again with refined parameters (write reasoning, then call `search`), OR
   b. Call `submit_answer` with your composed answer and citations

### Search Rules
[Content from planner_task.md: filter hierarchy, anti-patterns, query strategy,
 retrieval strategies, filter operators, etc.]

### When to Stop Searching
[Content from evaluator_task.md: directness criterion, stagnation detection]

- Stop when results DIRECTLY ANSWER the query — not just relate to the topic
- Stop when you've exhausted the search space (tried multiple strategies, queries, filters)
- Stop when repeating similar queries yields the same results
- If no progress after 2-3 attempts, submit the best answer you have
- Do NOT keep searching endlessly hoping for better results

### Answer Composition Rules
[Content from composer_task.md: synthesize don't list, lead with answer,
 handle gaps honestly, cite specific entities]
```

### 2.2 What goes in the system prompt vs user message

**System prompt** (static, identical every request — cacheable):
- `airweave_overview.md` — how Airweave works
- `agent_task.md` — merged task instructions

**First user message** (dynamic, per-request):
- User query
- User filter
- Mode (fast / thinking) with specific instructions
- Collection metadata (sources, entity types, counts)

### 2.3 Files to create/modify

- **Create:** `context/agent_task.md` — merged prompt
- **Delete (later):** `context/planner_task.md`, `context/evaluator_task.md`,
  `context/composer_task.md` — keep until new prompt is validated
- **Keep:** `context/airweave_overview.md` — unchanged

---

## Phase 3: New LLM Interface

### 3.1 Extend `AgenticSearchLLMInterface`

The current interface only has `structured_output()`. Add a method for tool-calling
conversations:

```python
class AgenticSearchLLMInterface(Protocol):
    @property
    def model_spec(self) -> LLMModelSpec: ...

    async def structured_output(self, prompt, schema, system_prompt) -> T: ...

    async def create_with_tools(
        self,
        messages: list[dict],
        tools: list[dict],
        system_prompt: str,
    ) -> LLMToolResponse: ...

    async def close(self) -> None: ...
```

### 3.2 New response type

```python
@dataclass
class LLMToolCall:
    """A tool call from the model."""
    id: str              # tool_use_id for pairing with tool_result
    name: str            # "search" or "submit_answer"
    arguments: dict      # parsed JSON arguments

@dataclass
class LLMToolResponse:
    """Response from create_with_tools."""
    text: str | None           # model's text output (reasoning before tool calls)
    tool_calls: list[LLMToolCall]  # tool calls (empty if end_turn)
    stop_reason: str           # "end_turn" or "tool_use" / "stop"
    usage: dict                # token usage for tracking
```

The `text` field contains the model's reasoning — this is what we emit as `ThinkingEvent`.
For example, the model might output:

```
text: "The first search found OAuth docs but nothing about SAML.
       Let me try a keyword search specifically for SAML configuration..."
tool_calls: [search({query: "SAML configuration", strategy: "keyword", ...})]
```

### 3.3 Implement for each provider

Two message format paths:

**OpenAI-compatible (Cerebras, Groq):**
- `tools` parameter in chat completions with `type: "function"`
- `tool_choice: "auto"` to let model decide, or `"required"` to force a tool call
- Tool results go as `role: "tool"` messages with `tool_call_id`
- Assistant messages with tool calls use `tool_calls` field
- Supports `strict: true` for schema validation (Cerebras)

**Anthropic:**
- `tools` parameter with `input_schema` per tool
- Tool calls come as `tool_use` content blocks in assistant messages
- Tool results go as `tool_result` content blocks in user messages
- `stop_reason: "tool_use"` indicates the model wants to call a tool

The provider implementations translate between our generic format and provider-specific
formats. The agent loop works with the generic `LLMToolResponse` format.

### 3.4 FallbackChainLLM

Extend `FallbackChainLLM` with `create_with_tools()` that chains through providers
the same way `structured_output()` does (circuit breaker, fallback, analytics).

### 3.5 Files to modify

- `external/llm/interface.py` — add `create_with_tools` to protocol
- `external/llm/providers/cerebras.py` — implement `create_with_tools`
- `external/llm/providers/groq.py` — implement `create_with_tools`
- `external/llm/providers/anthropic.py` — implement `create_with_tools`
- `external/llm/fallback.py` — extend FallbackChainLLM
- **Create:** `external/llm/tool_response.py` — LLMToolCall, LLMToolResponse types

---

## Phase 4: Context Management

### 4.1 Three-layer defense (inspired by OpenClaw)

All context management operates on the `messages` list before each API call.

#### Layer 1: Result truncation per tool response

When formatting search results for the tool response, drop lowest-ranked results
if the total exceeds a budget. Never truncate individual results — show them in full
or not at all.

```python
MAX_TOOL_RESULT_CONTEXT_SHARE = 0.3  # single tool result ≤ 30% of context
CHARS_PER_TOKEN = 4

def format_results_for_tool_response(
    results: AgenticSearchResults,
    context_window_tokens: int,
) -> tuple[str, int, int]:
    """Format results, dropping low-ranked ones if needed.

    Returns: (formatted_text, results_shown, results_total)
    """
    max_chars = int(context_window_tokens * MAX_TOOL_RESULT_CONTEXT_SHARE * CHARS_PER_TOKEN)
    # Add results by relevance until budget exhausted
    # Same logic as current AgenticSearchResults.to_md_with_budget()
    # but using char count instead of token count (faster, good enough)
```

This runs ONCE when building the tool response. The model never sees the dropped results.

#### Layer 2: Prune old tool results as context grows

Before each API call, check total context size. If approaching limits, compress old
tool results while keeping the model's reasoning about them intact.

```python
SOFT_TRIM_RATIO = 0.6   # start soft-trimming at 60% of context
HARD_CLEAR_RATIO = 0.8  # start hard-clearing at 80% of context
KEEP_LAST_N_RESULTS = 1 # always keep the most recent tool result intact

def prune_context(
    messages: list[dict],
    context_window_tokens: int,
) -> list[dict]:
    """Prune old tool results from the messages array.

    IMPORTANT: Only tool result messages are pruned. The model's own
    text/reasoning (assistant messages) is NEVER touched. This means
    the model retains its own analysis of what it saw, even after the
    raw search results are trimmed or removed.
    """
    total_chars = estimate_total_chars(messages)
    max_chars = context_window_tokens * CHARS_PER_TOKEN

    if total_chars < max_chars * SOFT_TRIM_RATIO:
        return messages  # under threshold, no pruning

    # Find tool_result messages (skip the most recent one)
    tool_result_indices = find_tool_result_indices(messages)
    if len(tool_result_indices) <= KEEP_LAST_N_RESULTS:
        return messages

    prunable = tool_result_indices[:-KEEP_LAST_N_RESULTS]

    # SOFT TRIM: keep head (first 2000 chars) + tail (last 500 chars)
    for idx in prunable:
        if total_chars < max_chars * SOFT_TRIM_RATIO:
            break
        messages[idx] = soft_trim_tool_result(messages[idx], head=2000, tail=500)
        total_chars = estimate_total_chars(messages)

    # HARD CLEAR: replace with placeholder if still over 80%
    if total_chars > max_chars * HARD_CLEAR_RATIO:
        for idx in prunable:
            if total_chars < max_chars * HARD_CLEAR_RATIO:
                break
            messages[idx] = replace_with_placeholder(messages[idx])
            total_chars = estimate_total_chars(messages)

    return messages
```

#### Layer 3: Compaction (overflow recovery)

If the API returns a context overflow error despite pruning, summarize the old
conversation with a separate LLM call.

```python
async def compact_conversation(
    messages: list[dict],
    llm: AgenticSearchLLMInterface,
    keep_last_n_exchanges: int = 2,
) -> list[dict]:
    """Summarize old messages, keep recent exchanges."""
    # Split into old (to summarize) and recent (to keep)
    split_point = find_split_point(messages, keep_last_n_exchanges)
    old = messages[:split_point]
    recent = messages[split_point:]

    # Summarize old conversation
    summary = await llm.structured_output(
        prompt=format_for_summary(old),
        schema=ConversationSummary,
        system_prompt="Summarize this search conversation. Include: queries tried, "
                      "what was found per source, which sources were exhausted, "
                      "what's still missing. Be concise.",
    )

    # Replace old messages with summary
    return [
        {"role": "user", "content": f"[Previous search history summary]\n\n{summary.text}"},
        {"role": "assistant", "content": "Understood, continuing the search."},
        *recent,
    ]
```

### 4.2 Files to create

- **Create:** `core/context_manager.py` — all 3 layers: result formatting, pruning, compaction

---

## Phase 5: Rewrite the Agent Loop

### 5.1 New `agent.py`

The core loop becomes much simpler:

```python
class AgenticSearchAgent:
    # Safety cap — should never be reached in normal operation.
    # The prompt instructs the model to stop when no progress is made.
    SAFETY_MAX_ITERATIONS = 20

    async def _run(self, collection_readable_id, request, is_streaming):
        # Build collection metadata (same as before)
        collection_metadata = await self._build_metadata(collection_readable_id)

        # Build system prompt (static)
        system_prompt = self._build_system_prompt()

        # Build initial user message (dynamic)
        initial_message = self._build_initial_message(
            query=request.query,
            user_filter=request.filter,
            mode=request.mode,
            collection_metadata=collection_metadata,
        )

        # Initialize conversation
        messages = [{"role": "user", "content": initial_message}]

        # Tools
        tools = [SEARCH_TOOL, SUBMIT_ANSWER_TOOL]

        # Track all results seen (for final response)
        all_results: list[AgenticSearchResult] = []
        iteration = 0

        # FAST mode: tell the model to do exactly one search
        max_iterations = 1 if request.mode == AgenticSearchMode.FAST else self.SAFETY_MAX_ITERATIONS

        while iteration < max_iterations:
            # Layer 2: Prune old results if context is growing
            messages = prune_context(messages, self._context_window_tokens)

            # API call
            try:
                response = await self.services.llm.create_with_tools(
                    messages=messages,
                    tools=tools,
                    system_prompt=system_prompt,
                )
            except ContextOverflowError:
                # Layer 3: Compact and retry
                messages = await compact_conversation(messages, self.services.llm)
                response = await self.services.llm.create_with_tools(
                    messages=messages,
                    tools=tools,
                    system_prompt=system_prompt,
                )

            # Append assistant message to conversation
            messages.append(build_assistant_message(response))

            # Emit thinking event if model produced reasoning text
            if response.text:
                await self.emitter.emit(AgenticSearchThinkingEvent(
                    iteration=iteration,
                    text=response.text,
                ))

            # No tool calls = model ended turn without calling a tool.
            # Shouldn't happen normally (model should call submit_answer),
            # but handle gracefully by treating text as the answer.
            if not response.tool_calls:
                break

            # Process tool calls
            for tool_call in response.tool_calls:
                if tool_call.name == "search":
                    result_text, results = await self._execute_search(
                        tool_call, collection_metadata, request
                    )
                    all_results = results  # keep latest result set
                    messages.append(build_tool_result_message(
                        tool_call.id, result_text
                    ))
                    await self.emitter.emit(AgenticSearchSearchingEvent(
                        iteration=iteration,
                        query_primary=tool_call.arguments["query"]["primary"],
                        retrieval_strategy=tool_call.arguments["retrieval_strategy"],
                        result_count=len(results),
                        duration_ms=...,
                    ))
                    iteration += 1

                elif tool_call.name == "submit_answer":
                    answer = AgenticSearchAnswer(**tool_call.arguments)
                    final_results = all_results[:request.limit] if request.limit else all_results
                    resp = AgenticSearchResponse(results=final_results, answer=answer)
                    await self.emitter.emit(AgenticSearchDoneEvent(response=resp))
                    return resp

        # Safety cap reached or model ended turn without tool call.
        # Force a final answer by giving the model only submit_answer.
        return await self._force_final_answer(messages, all_results, request)
```

### 5.2 FAST mode handling

For FAST mode, two mechanisms:

1. **Prompt-based:** The initial user message includes:
   ```
   Mode: fast — perform exactly ONE search, then immediately call submit_answer.
   ```

2. **Hard cap:** `max_iterations = 1`. After 1 search, if the model tries to search again,
   the loop exits and `_force_final_answer` kicks in.

### 5.3 Stopping: prompt-based with safety cap

The model decides when to stop based on the prompt instructions ("stop when no progress").
The `SAFETY_MAX_ITERATIONS = 20` is a circuit breaker that should never fire in normal
operation — it's there to prevent runaway conversations from burning tokens endlessly.

No dynamic formula. No `_calculate_max_iterations`. Just:
- FAST: 1
- THINKING: 20 (safety cap, prompt handles the real stopping logic)

### 5.4 Force final answer (safety net)

If the model hits the safety cap or ends its turn without calling submit_answer:

```python
async def _force_final_answer(self, messages, all_results, request):
    """Force the model to submit an answer."""
    messages.append({
        "role": "user",
        "content": "You must now call submit_answer with the best answer you can "
                   "compose from what you've found so far. If no direct answer was "
                   "found, say so honestly."
    })

    response = await self.services.llm.create_with_tools(
        messages=messages,
        tools=[SUBMIT_ANSWER_TOOL],  # only submit_answer available
        system_prompt=self._build_system_prompt(),
    )

    # Extract answer from tool call
    for tool_call in response.tool_calls:
        if tool_call.name == "submit_answer":
            answer = AgenticSearchAnswer(**tool_call.arguments)
            final_results = all_results[:request.limit] if request.limit else all_results
            resp = AgenticSearchResponse(results=final_results, answer=answer)
            await self.emitter.emit(AgenticSearchDoneEvent(response=resp))
            return resp

    # Absolute fallback — model still didn't call submit_answer
    answer = AgenticSearchAnswer(
        text=response.text or "The search was unable to produce a conclusive answer.",
        citations=[],
    )
    return AgenticSearchResponse(results=all_results, answer=answer)
```

### 5.5 Files to modify

- `core/agent.py` — complete rewrite of the loop

---

## Phase 6: New Event Schema

### 6.1 New events (breaking change)

```python
class AgenticSearchThinkingEvent(BaseModel):
    """Emitted when the model produces reasoning text.

    This is the model's actual text output BEFORE calling a tool.
    For example: "The previous results were about OAuth but the user
    asked about SAML. Let me try a keyword search for SAML..."

    This replaces the old PlanningEvent's reasoning field with the
    model's natural free-form thinking.
    """
    type: Literal["thinking"] = "thinking"
    iteration: int
    text: str  # model's text output (response.text from LLMToolResponse)

class AgenticSearchSearchingEvent(BaseModel):
    """Emitted when a search is executed."""
    type: Literal["searching"] = "searching"
    iteration: int
    query_primary: str          # what was searched
    retrieval_strategy: str
    result_count: int
    duration_ms: int

class AgenticSearchDoneEvent(BaseModel):
    """Emitted when the search is complete."""
    type: Literal["done"] = "done"
    response: AgenticSearchResponse

class AgenticSearchErrorEvent(BaseModel):
    """Emitted when an error occurs."""
    type: Literal["error"] = "error"
    message: str
```

### 6.2 Where does the reasoning come from?

The reasoning (`ThinkingEvent.text`) comes directly from the model's API response.
When a model makes a tool call, most providers return both:

1. **Text content** — free-form reasoning the model wrote before deciding to call a tool
2. **Tool calls** — the structured function call(s)

Both arrive in the same API response. Our `LLMToolResponse.text` captures item 1,
and `LLMToolResponse.tool_calls` captures item 2. We emit the text as a `ThinkingEvent`.

### 6.3 Removed events

- `AgenticSearchPlanningEvent` — replaced by `ThinkingEvent` (the model's reasoning)
  + `SearchingEvent` (the tool call parameters)
- `AgenticSearchEvaluatingEvent` — the model's evaluation is now part of its reasoning
  text between tool calls (captured in `ThinkingEvent`)

### 6.4 Files to modify

- `schemas/events.py` — new event types

---

## Phase 7: Message Construction Helpers

### 7.1 Provider-specific message formats

The message format differs between providers. The helpers abstract this:

**For OpenAI-compatible (Cerebras, Groq):**
```python
# Assistant message with tool call
{"role": "assistant", "content": "reasoning text...", "tool_calls": [
    {"id": "call_123", "type": "function", "function": {"name": "search", "arguments": "{...}"}}
]}

# Tool result
{"role": "tool", "tool_call_id": "call_123", "content": "search results..."}
```

**For Anthropic:**
```python
# Assistant message with tool call
{"role": "assistant", "content": [
    {"type": "text", "text": "reasoning text..."},
    {"type": "tool_use", "id": "toolu_123", "name": "search", "input": {...}}
]}

# Tool result
{"role": "user", "content": [
    {"type": "tool_result", "tool_use_id": "toolu_123", "content": "search results..."}
]}
```

The provider implementations handle this translation. The agent loop works with a
generic format that each provider converts to/from.

### 7.2 Files to create

- `core/messages.py` — generic message construction helpers
- Provider-specific translation happens inside each provider's `create_with_tools()`

---

## Phase 8: Cleanup

### 8.1 Files to delete

After the new implementation is validated:

- `core/planner.py` — replaced by model + search tool
- `core/evaluator.py` — replaced by model's natural reasoning
- `core/composer.py` — replaced by model + submit_answer tool
- `schemas/history.py` — conversation IS the history (no more strategy ledger,
  no more manual history reconstruction, no more budget-aware history rendering)
- `schemas/state.py` — state is now just the messages array
- `schemas/evaluation.py` — no more separate evaluation schema
- `builders/state_builder.py` — no more explicit state
- `builders/result_brief_builder.py` — no more result briefs
- `builders/complete_plan_builder.py` — filter merging moves into tool execution
- `context/planner_task.md` — merged into agent_task.md
- `context/evaluator_task.md` — merged into agent_task.md
- `context/composer_task.md` — merged into agent_task.md

### 8.2 Files to keep (unchanged or minor edits)

- `core/embedder.py` — unchanged, called inside search tool
- `external/vector_database/` — all files unchanged
- `external/tokenizer/` — unchanged
- `external/dense_embedder/` — unchanged
- `external/sparse_embedder/` — unchanged
- `schemas/search_result.py` — unchanged
- `schemas/filter.py` — unchanged
- `schemas/request.py` — unchanged
- `schemas/response.py` — unchanged
- `schemas/answer.py` — unchanged (also used as submit_answer tool input)
- `schemas/plan.py` — `reasoning` field removed, rest unchanged (used as search tool input)
- `schemas/retrieval_strategy.py` — unchanged
- `config.py` — unchanged
- `services.py` — minor: no changes to service creation
- `emitter.py` — unchanged interface, implementations stay
- `__init__.py` — update exports

### 8.3 API endpoint changes

`api/v1/endpoints/agentic_search.py` — no changes needed.
The endpoint creates `AgenticSearchAgent` and calls `agent.run()` which returns
`AgenticSearchResponse`. The internal implementation changes but the API contract
stays the same.

---

## Implementation Order

### Step 1: LLM interface extension
- Add `create_with_tools()` to interface protocol
- Create `LLMToolResponse` / `LLMToolCall` types
- Implement for Cerebras (OpenAI-compatible), Groq (OpenAI-compatible), Anthropic (native)
- Extend FallbackChainLLM
- **Test:** Verify tool calling works with each provider independently

### Step 2: Tool definitions and execution
- Create `core/tools.py` with search + submit_answer tools
- Reuse `AgenticSearchPlan` (minus reasoning) as search tool schema
- Reuse `AgenticSearchAnswer` as submit_answer tool schema
- Implement search execution (reuse embedder + vector_db)
- Implement result formatting with budget (Layer 1 context management)
- **Test:** Verify search tool produces correct results

### Step 3: Context management
- Create `core/context_manager.py` with Layers 2 and 3
- Implement context pruning (soft trim + hard clear of old tool results)
- Implement compaction (overflow recovery via summarization)
- **Test:** Verify pruning works correctly — old results trimmed, assistant messages preserved

### Step 4: System prompt
- Create `context/agent_task.md` — merge planner + evaluator + composer prompts
- Keep all existing search rules and anti-patterns
- Add tool-specific instructions and stopping guidance
- **Test:** Review prompt for completeness, no missing guidance

### Step 5: Message helpers
- Create `core/messages.py` — generic message construction
- Provider-specific translation inside provider implementations
- **Test:** Verify message format is correct for each provider

### Step 6: New agent loop
- Rewrite `core/agent.py` with conversation loop
- FAST mode: prompt-based (1 search) + hard cap (max_iterations=1)
- THINKING mode: prompt-based stopping + safety cap (20 iterations)
- force_final_answer fallback
- **Test:** End-to-end test with real queries

### Step 7: Events
- Update `schemas/events.py` with new event types
- ThinkingEvent gets `response.text` from LLMToolResponse (model's free-form reasoning)
- SearchingEvent gets tool call parameters
- DoneEvent unchanged, ErrorEvent unchanged
- **Test:** Verify SSE stream produces correct events

### Step 8: Cleanup
- Modify `schemas/plan.py`: remove `reasoning` field
- Delete old files (planner, evaluator, composer, history, state, evaluation, builders, old prompts)
- Update `__init__.py` exports
- Update any imports in the broader codebase
- **Test:** Full regression test

---

## Risks and Mitigations

### Risk 1: Model doesn't follow tool-calling patterns well with Cerebras/Groq
**Mitigation:** The fallback chain will fall through to Anthropic which has excellent
tool use. Monitor fallback rate — if primary providers struggle, consider making
Anthropic the primary for the tool-calling path.

### Risk 2: Context grows too fast with many searches
**Mitigation:** The 3-layer context management system. Layer 1 caps each result at 30%
of context. Layer 2 prunes old results at 60%. Layer 3 compacts at overflow.
Safety cap prevents unbounded growth.

### Risk 3: Model doesn't stop when it should (keeps searching endlessly)
**Mitigation:** Prompt instructs the model to stop when no progress is made after 2-3
attempts. Safety cap of 20 iterations as circuit breaker. `force_final_answer` removes
the search tool and forces submit_answer if cap is hit.

### Risk 4: Model produces poor structured output via submit_answer
**Mitigation:** The submit_answer tool has a simple schema (AgenticSearchAnswer: text +
list of citations). This is much simpler than the current structured output schemas.
If the model produces invalid output, the tool execution can catch and retry once.

### Risk 5: "Not in data" detection degrades
**Mitigation:** The system prompt includes explicit guidance about when the search is
exhausted and the model should report "not found". The model's free-form reasoning
naturally includes evaluation of results. Monitor this metric closely during testing.

### Risk 6: Loss of observability
**Mitigation:** `ThinkingEvent` captures the model's reasoning (replaces PlanningEvent
reasoning + EvaluatingEvent reasoning). `SearchingEvent` captures what was searched.
Together they provide equivalent or better observability since the model's reasoning
is now unconstrained natural text rather than a forced JSON field.
