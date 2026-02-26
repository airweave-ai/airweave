// Streaming Search: TypeScript contracts for SSE events and UI aggregates
// These types mirror the backend event schema so we can render every event precisely.

export type ISODate = string;

// Base event fields shared across many events
export interface BaseEvent {
    type: string;
    ts?: ISODate;
    seq?: number; // global sequence across the whole request
    op?: string | null; // operator identifier, e.g. "query_interpretation"
    op_seq?: number | null; // per-operator sequence
    request_id?: string; // present on some events
}

// Connection & lifecycle
export interface ConnectedEvent extends BaseEvent {
    type: 'connected';
    request_id: string;
}

export interface StartEvent extends BaseEvent {
    type: 'start';
    query: string;
    limit: number;
    offset: number;
}

export interface DoneEvent extends BaseEvent {
    type: 'done';
}

export interface CancelledEvent extends BaseEvent {
    type: 'cancelled';
}

export interface ErrorEvent extends BaseEvent {
    type: 'error';
    message: string;
    operation?: string;
    transient?: boolean;
    detail?: string;
}

export interface HeartbeatEvent extends BaseEvent {
    type: 'heartbeat';
}

export interface SummaryEvent extends BaseEvent {
    type: 'summary';
    timings: Record<string, number>;
    errors: any[];
    total_time_ms: number;
}

// Operator boundaries
export interface OperatorStartEvent extends BaseEvent {
    type: 'operator_start';
    name: string;
}

export interface OperatorEndEvent extends BaseEvent {
    type: 'operator_end';
    name: string;
    ms: number;
}

// Query interpretation
export interface InterpretationStartEvent extends BaseEvent {
    type: 'interpretation_start';
    model: string;
    strategy?: string;
}

export interface InterpretationReasonDeltaEvent extends BaseEvent {
    type: 'interpretation_reason_delta';
    text: string;
}

export interface InterpretationDeltaEvent extends BaseEvent {
    type: 'interpretation_delta';
    parsed_snapshot: {
        filters: any[];
        confidence?: number;
        refined_query?: string;
    };
}

// Interpretation explicitly skipped due to low confidence
export interface InterpretationSkippedEvent extends BaseEvent {
    type: 'interpretation_skipped';
    reason: string;
    confidence?: number;
    threshold?: number;
}

export interface FilterAppliedEvent extends BaseEvent {
    type: 'filter_applied';
    filter: any | null;
    source?: string;
}

// Filter merge diagnostics (manual + interpretation)
export interface FilterMergeEvent extends BaseEvent {
    type: 'filter_merge';
    existing?: any; // interpretation filter (if any)
    user?: any;     // normalized manual filter
    merged: any;    // final merged filter
}

// Query expansion
export interface ExpansionStartEvent extends BaseEvent {
    type: 'expansion_start';
    model: string;
    strategy: string;
}

export interface ExpansionReasonDeltaEvent extends BaseEvent {
    type: 'expansion_reason_delta';
    text: string;
}

export interface ExpansionDeltaEvent extends BaseEvent {
    type: 'expansion_delta';
    alternatives_snapshot: string[];
}

export interface ExpansionDoneEvent extends BaseEvent {
    type: 'expansion_done';
    alternatives: string[];
}

// Recency
export interface RecencyStartEvent extends BaseEvent {
    type: 'recency_start';
    requested_weight: number;
}

export interface RecencySpanEvent extends BaseEvent {
    type: 'recency_span';
    field: string;
    oldest: string;
    newest: string;
    span_seconds: number;
}

export interface RecencySkippedEvent extends BaseEvent {
    type: 'recency_skipped';
    reason: 'weight_zero' | 'no_field' | string;
}

// Embedding
export interface EmbeddingStartEvent extends BaseEvent {
    type: 'embedding_start';
    search_method: 'hybrid' | 'neural' | 'keyword';
}

export interface EmbeddingDoneEvent extends BaseEvent {
    type: 'embedding_done';
    neural_count: number;
    dim: number;
    model: string;
    sparse_count: number | null;
    avg_nonzeros: number | null;
}

export interface EmbeddingFallbackEvent extends BaseEvent {
    type: 'embedding_fallback';
    reason?: string;
}

// Vector search
export interface VectorSearchStartEvent extends BaseEvent {
    type: 'vector_search_start';
    embeddings: number;
    method: 'hybrid' | 'neural' | 'keyword';
    limit: number;
    offset: number;
    threshold: number | null;
    has_sparse: boolean;
    has_filter: boolean;
    decay_weight?: number;
}

export interface VectorSearchBatchEvent extends BaseEvent {
    type: 'vector_search_batch';
    fetched: number;
    unique: number;
    dedup_dropped: number;
    top_scores?: number[];
}

export interface VectorSearchDoneEvent extends BaseEvent {
    type: 'vector_search_done';
    final_count: number;
    top_scores?: number[];
}

export interface VectorSearchNoResultsEvent extends BaseEvent {
    type: 'vector_search_no_results';
    reason: string;
    has_filter: boolean;
}

// Reranking
export interface RerankingStartEvent extends BaseEvent {
    type: 'reranking_start';
    model: string;
    strategy: string;
    k: number;
}

export interface RerankingReasonDeltaEvent extends BaseEvent {
    type: 'reranking_reason_delta';
    text: string;
}

export interface RerankingDeltaEvent extends BaseEvent {
    type: 'reranking_delta';
    rankings_snapshot: Array<{ index: number; relevance_score: number }>;
}

export interface RankingsEvent extends BaseEvent {
    type: 'rankings';
    rankings: Array<{ index: number; relevance_score: number }>;
}

export interface RerankingDoneEvent extends BaseEvent {
    type: 'reranking_done';
    rankings: Array<{ index: number; relevance_score: number }>;
    applied: boolean;
}

// Completion (answer generation)
export interface AnswerContextBudgetEvent extends BaseEvent {
    type: 'answer_context_budget';
    total_results: number;
    results_in_context: number;
    excluded: number;
}

export interface CompletionDoneEvent extends BaseEvent {
    type: 'completion_done';
    text: string; // final assembled answer (not streamed, sent once when complete)
}

// Results
export interface ResultsEvent extends BaseEvent {
    type: 'results';
    results: any[]; // keep as any to match backend payload
}

// Union of all known events
export type SearchEvent =
    | ConnectedEvent
    | StartEvent
    | OperatorStartEvent
    | OperatorEndEvent
    | InterpretationStartEvent
    | InterpretationReasonDeltaEvent
    | InterpretationDeltaEvent
    | InterpretationSkippedEvent
    | FilterAppliedEvent
    | FilterMergeEvent
    | ExpansionStartEvent
    | ExpansionReasonDeltaEvent
    | ExpansionDeltaEvent
    | ExpansionDoneEvent
    | RecencyStartEvent
    | RecencySpanEvent
    | RecencySkippedEvent
    | EmbeddingStartEvent
    | EmbeddingDoneEvent
    | EmbeddingFallbackEvent
    | VectorSearchStartEvent
    | VectorSearchBatchEvent
    | VectorSearchDoneEvent
    | VectorSearchNoResultsEvent
    | RerankingStartEvent
    | RerankingReasonDeltaEvent
    | RerankingDeltaEvent
    | RankingsEvent
    | RerankingDoneEvent
    | AnswerContextBudgetEvent
    | CompletionDoneEvent
    | ResultsEvent
    | SummaryEvent
    | HeartbeatEvent
    | ErrorEvent
    | DoneEvent
    | CancelledEvent;

// Stream phase for higher-level UI state
export type StreamPhase = 'searching' | 'answering' | 'finalized' | 'cancelled';

// Aggregated UI update emitted along raw events
export interface PartialStreamUpdate {
    requestId?: string | null;
    results?: any[]; // latest snapshot
    status?: StreamPhase;
}

// ─── Agentic Search Types ─────────────────────────────────────────────────────
// These mirror the backend schemas in agentic_search/schemas/

export type AgenticSearchModeType = "fast" | "thinking";

export interface AgenticSearchPlanData {
    reasoning: string;
    query: {
        primary: string;
        variations: string[];
    };
    filter_groups: any[];
    limit: number;
    offset: number;
    retrieval_strategy: "semantic" | "keyword" | "hybrid";
}

export interface AgenticSearchEvaluationData {
    reasoning: string;
    should_continue: boolean;
    answer_found: boolean;
}

export interface AgenticSearchCitationData {
    entity_id: string;
}

export interface AgenticSearchAnswerData {
    text: string;
    citations: AgenticSearchCitationData[];
}

// Agentic SSE events

export interface AgenticPlanningEvent extends BaseEvent {
    type: 'planning';
    iteration: number;
    plan: AgenticSearchPlanData;
    is_consolidation: boolean;
    history_shown: number;
    history_total: number;
}

export interface AgenticSearchingEvent extends BaseEvent {
    type: 'searching';
    iteration: number;
    result_count: number;
    duration_ms: number;
}

export interface AgenticEvaluatingEvent extends BaseEvent {
    type: 'evaluating';
    iteration: number;
    evaluation: AgenticSearchEvaluationData;
    results_shown: number;
    results_total: number;
    history_shown: number;
    history_total: number;
}

export interface AgenticDoneEvent extends BaseEvent {
    type: 'done';
    response: {
        results: any[];
        answer: AgenticSearchAnswerData;
    };
}

export interface AgenticErrorEvent extends BaseEvent {
    type: 'error';
    message: string;
}

export type AgenticSearchEvent =
    | AgenticPlanningEvent
    | AgenticSearchingEvent
    | AgenticEvaluatingEvent
    | AgenticDoneEvent
    | AgenticErrorEvent;
