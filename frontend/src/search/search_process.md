## Streaming Search – Product & Implementation Design (2025)

### Purpose
Deliver a silky‑smooth, live search experience that reveals the pipeline as it works: show operator progress (interpretation, expansion, vector search, reranking), stream the answer token‑by‑token, and surface results as soon as they’re ready. Keep the UI calm, modern, and legible under constant updates.

---

## UX Principles
- **Clarity over spectacle**: minimal chrome, strong typography, quiet motion, clear hierarchy.
- **Live, not jittery**: batch micro‑updates, avoid layout shifts, use subtle progress cues.
- **Separation of concerns**: a dedicated “Process” view for diagnostics; the primary result stays readable.
- **Interruptible**: a new query immediately cancels the prior stream and resets the UI.
- **Trustworthy**: explicit statuses (“searching…”, “answering…”, “finalized”), graceful error messaging.
- **Explicit control**: show a visible Cancel action during streaming; ESC as keyboard fallback.

### Statuses and Transitions (Why they exist)
- **searching**: we are retrieving and preparing data (operators run: interpretation → expansion → retrieval → reranking). UI shows progress ribbon and timeline.
- **answering**: completion has started (we received `completion_start` or first `completion_delta`). UI switches primary emphasis to the Answer tab and streams tokens in real time.
- **finalized**: terminal state after `done`. We freeze timers, keep Process panel visible for review, and present the final combined response.

Transition rules:
- start → searching
- first `completion_delta` → answering
- `done` or cancel → finalized (cancel yields partial response + cancelled note)

---

## Event Model (from Server)
SSE `data:` payloads are JSON objects with `type` and optional fields:
- connected: `{ type, request_id, ts }`
- start: `{ type, seq, query, limit, offset }`
- operator_*: `{ type: 'operator_start' | 'operator_end', op, op_seq, ms? }`
- interpretation_*: reason deltas and parsed snapshots
- filter_applied: `{ type: 'filter_applied', filter }` (may be null if no filter applied)
- expansion_*: reason deltas and alternatives snapshots
- recency_*: computed spans and weights
- embedding_*: embedding meta
- vector_search_*: batch stats and final counts
- reranking_*: reason deltas, ranking snapshots
- completion_*: `{ completion_delta | completion_done | completion_start }`
- results: `{ results: Entity[] }`
- summary: timings, errors
- heartbeat: keep‑alive
- error: `{ message }`
- done: terminal event

We preserve raw events for the process timeline while aggregating:
- `streamingCompletion`: concatenation of `completion_delta.text`
- `liveResults`: latest `results.results` array (replace, not append)

Additional notes:
- `seq` is a global monotonically increasing counter for the request; `op_seq` is per‑operator.
- `results` may arrive after `completion_done`. We should render tokens immediately and then update entities when `results` arrives.

---

## Component Architecture
- SearchBox (controller)
  - Initiates POST → SSE stream
  - Parses SSE frames and forwards each `completion_delta` immediately (do not coalesce) so tokens render one‑by‑one
  - Maintains a running completion string for convenience but emits each token to the parent as it arrives
  - Manages cancellation via AbortController and a sequence guard
  - Shows a Cancel button while streaming; on click, calls `abort()` and updates UI state

- CollectionNewView (state owner)
  - Owns all streaming state (events, completion, results, requestId, isSearching)
  - Controls Process panel visibility lifecycle
  - Passes state to:
    - SearchProcess (live timeline)
    - SearchResponseDisplay (answer + entities)

- SearchProcess (visualize pipeline)
  - Minimal, legible timeline with event chips, operator groups, and deltas
  - Non‑blocking; scrollable; no layout jumps
  - Visibility: hidden initially; becomes visible on first search; remains open after completion; empties on new search

- SearchResponseDisplay (result renderer)
  - Visibility: hidden on first page; opens on search start; clears content on new search
  - While streaming: displays growing completion; entities appear when `results` event arrives
  - After `done`: locks into the final response
  - Token rendering: receives per‑delta tokens and appends them directly to the visible answer text (no extra buffering)

---

## State Ownership & Shape
State lives in `CollectionNewView` (local React state). No global store required.

```ts
interface StreamingState {
  isSearching: boolean;
  showProcessPanel: boolean;     // initially false; set true on first search; persists
  showResponsePanel: boolean;    // initially false; set true on first search; may hide on cancel (no tokens/results)
  isCancelling?: boolean;        // optional: brief state while aborting
  requestId: string | null;
  events: any[];                 // raw SSE events for SearchProcess
  streamingCompletion: string;   // aggregated answer text
  liveResults: any[];            // latest results array
  responseType: 'raw' | 'completion';
  finalResponse: any | null;     // set at `done` or error
}
```

Why local state (not Zustand)?
- Scope is the search page only; no cross‑route reuse.
- Streams are ephemeral; persistence would be noise.
- Simpler lifecycle: parent owns child props, cancels on re‑query.

---

## Data Flow (Callbacks)
Parent → Child: configuration (query, toggles)
Child → Parent: updates via two callbacks
- `onStreamEvent(event)`: every parsed SSE event (for timeline)
- `onStreamUpdate(partial)`: aggregated deltas `{ requestId?, streamingCompletion?, results?, status? }`

This preserves raw fidelity (events) and ergonomic consumption (partial aggregates) without coupling components.

---

## Stream Lifecycle
1) Start
   - Abort any prior stream
   - Increment `searchSeq` guard
   - Set `isSearching=true`
   - Ensure `showProcessPanel=true` (if first time)
   - Ensure `showResponsePanel=true` (if first time)
   - Reset process state: `events=[]`, `streamingCompletion=''`, `liveResults=[]`, `requestId=null`

2) Receive events
   - Parse SSE frames, JSON‑decode `data:` lines
   - Accumulate `completion_delta`; replace `liveResults` on `results`
   - Emit raw+partial updates to parent
   - Defer non‑critical paints (microtask) to avoid thrash

3) Finalize
   - On `done`: compose final response from aggregates; set `finalResponse`
   - `isSearching=false`
   - Keep `showProcessPanel=true` and retain `events` so user can review

4) Cancel / Replace
   - User clicks Cancel button → `AbortController.abort()`; set `isCancelling` transiently (optional)
   - `AbortController.abort()` on new query or unmount
   - Sequence guard ignores late chunks from the prior stream
   - If cancelled and we never received tokens nor results, set `showResponsePanel=false` (close the response); keep Process panel for review

5) Error
   - Server `error` event → surface to process + fallback UI message
   - Network aborts are expected on cancel; ignore AbortError

---

## Parsing & Performance (Plain English)
How we read the stream:
- The response body is a byte stream. We read chunks and decode them to text.
- The server sends Server‑Sent Events (SSE). Each event ends with a blank line. We split the rolling text buffer on blank lines to separate events.
- Inside each event, we collect all lines that start with `data:` and join them; that string is JSON we can parse. If parsing fails (e.g., heartbeat), we skip it.

How we keep it smooth:
- Append tokens as soon as `completion_delta` arrives so users see the answer forming.
- Avoid layout jumps: fixed height containers with `overflow: auto` for both Process and Answer.
- If needed for very fast streams, we can batch non‑critical updates once per animation frame.

---

## Visual Design Notes
- SearchProcess
  - Compact, monospace seq column, soft chips for `type` and `op`
  - Color accents: operator_start/end, deltas, errors
  - Scroll region with sticky subtle header (“Pipeline”)
  - Persistent panel: stays visible post‑search; content resets on new search

- SearchResponseDisplay
  - Status ribbon at top (searching/success/warn/error)
  - Answer tab when `responseType==='completion'`: stream text with subtle caret
  - Entities tab: shows JSON viewer; appears progressively when `results` arrive

- Controls
  - Show a prominent "Cancel" control while streaming (same row as Send). Secondary style; press returns to idle state but keeps Process panel content for review
  - Clear “Stop” implicit behavior remains: a new search also cancels the prior stream
  - Keep send button deterministic (spinner → arrow)

Accessibility
- Live regions for streamed answer (`aria-live="polite"`)
- Focus remains in query; timeline is supplementary
- Cancel is reachable by keyboard; provide `Esc` shortcut to cancel

---

## API Contract (Client)
Use existing `apiClient` to preserve auth/org headers; stream the body:

```ts
const res = await apiClient.post(
  `/collections/${collectionId}/search/stream`,
  requestBody,
  { headers: { /* Accept may be omitted; FastAPI sets text/event-stream */ }, signal }
);
```

On non‑OK: read `text()` and surface error. On OK: `res.body.getReader()` and parse SSE.

---

## Cancellation Semantics
- Client `abort()` closes the HTTP stream; reader loop exits with AbortError
- Server already handles disconnect: cancels background task, closes Redis pubsub, cleans up
- We guard UI with `searchSeq` to drop late chunks

---

## Testing Strategy
Functional
- Stream happy path: verify operator order, completion aggregation, results render, final state
- Cancel mid‑stream: start new search, ensure old stream stops, no mixed events
- Error path: inject server `error`, ensure message is surfaced and UI resets
- Heartbeat stability: long‑running ops with periodic heartbeat; no UI regressions

Performance
- Large completion: verify smooth typing and scrolling during token flow
- High event volume: cap timeline length; ensure no memory bloat

Accessibility
- Screen reader reads streamed completion; no focus traps

---

## Telemetry (Optional, Phase 2)
- Per‑operator timings vs server `summary.timings` (diff %)
- Cancel rate, error rate, avg TTFB (connected→first delta), avg TTFR (first results)

---

## Implementation Order (Milestones)
1) CollectionNewView State (start here)
   - Add local state: `showProcessPanel` (default `false`), `showResponsePanel` (default `false`), `events`, `streamingCompletion`, `liveResults`, `requestId`, `isSearching`, `responseType`, optional `isCancelling`
   - Implement `onSearchStart`, `onSearchEnd`, `onSearch`, `onStreamEvent`, `onStreamUpdate` handlers
   - Visibility: on first search set `showProcessPanel=true` and `showResponsePanel=true`; keep both open; clear content on new search start; on cancel with no tokens/results, hide `showResponsePanel`

2) Contracts & Types
   - Define `SearchEvent` and `PartialStreamUpdate` TS interfaces shared by SearchBox and parent

3) Streaming Fetch in SearchBox
   - Replace JSON POST with SSE parsing; forward each `completion_delta` immediately via callbacks
   - Handle `results`, `summary`, `done`, `error`; implement `AbortController` + `searchSeq` guard
   - Render Cancel button while `isSearching`; on click abort stream

4) SearchProcess Component
   - Render event list with chips, scrollable container, requestId header; cap list length

5) SearchResponseDisplay Integration
   - Token‑by‑token rendering: append delta text directly to the visible answer
   - Show `liveResults` when present; after `done` render final response

6) Polish & Error UX
   - Subtle caret while streaming, more precise statuses (e.g., “reranking…”) from events
   - Friendly error box with retry

7) Performance Hardening
   - Optional batching for non‑critical updates; memory caps for events

---

## Acceptance Criteria
- New queries immediately stop previous streams; no stale events leak
- Live “Process” view reflects ordered pipeline events without jank
- Completion streams smoothly; results appear when provided; final response matches non‑streaming endpoint output
- Process panel appears on first search, stays open after completion, and clears content on new search
- Visible Cancel button appears during streaming; clicking it stops the stream quickly and leaves the Process panel contents intact
- Errors are visible and actionable; empty states look intentional

---

## Risks & Mitigations
- High event volume → cap list, batch updates
- Partial JSON frames → robust buffer handling, ignore malformed lines
- Scroll thrash in timeline → fixed height, overflow scroll, minimal DOM per row
- Backend changes to event schema → tolerant parser, feature‑flag stringly types

---

## Quick Reference – Minimal SSE Loop (Client)

```ts
const ctrl = new AbortController();
const res = await apiClient.post(url, body, { headers: { Accept: 'text/event-stream' }, signal: ctrl.signal });
const reader = res.body!.getReader();
const decoder = new TextDecoder();
let buffer = '', completion = '';

for (;;) {
  const { value, done } = await reader.read();
  if (done) break;
  buffer += decoder.decode(value, { stream: true });
  const frames = buffer.split('\n\n');
  buffer = frames.pop() || '';
  for (const frame of frames) {
    const data = frame.split('\n').filter(l => l.startsWith('data:')).map(l => l.slice(5).trim()).join('\n');
    try {
      const e = JSON.parse(data);
      if (e.type === 'completion_delta') completion += e.text || '';
      // emit onStreamEvent(e); onStreamUpdate({ streamingCompletion: completion, ... });
      if (e.type === 'done') break;
    } catch {}
  }
}
```

---

## Rollout
- Phase 1: behind a dev flag; verify locally with long‑running queries
- Phase 2: enable by default; keep non‑streaming fallback path for 1 release
- Phase 3: remove fallback after confidence builds
