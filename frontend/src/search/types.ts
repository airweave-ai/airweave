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

export interface RerankingDoneEvent extends BaseEvent {
    type: 'reranking_done';
    rankings: Array<{ index: number; relevance_score: number }>;
    applied: boolean;
}

// Completion (answer streaming)
export interface CompletionStartEvent extends BaseEvent {
    type: 'completion_start';
    model: string;
}

export interface CompletionDeltaEvent extends BaseEvent {
    type: 'completion_delta';
    text: string; // token fragment
}

export interface CompletionDoneEvent extends BaseEvent {
    type: 'completion_done';
    text: string; // final assembled answer
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
    | RerankingStartEvent
    | RerankingReasonDeltaEvent
    | RerankingDeltaEvent
    | RerankingDoneEvent
    | CompletionStartEvent
    | CompletionDeltaEvent
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
    streamingCompletion?: string;
    results?: any[]; // latest snapshot
    status?: StreamPhase;
}
