// SSE event types from the new agentic search backend (domains/search/)
// These mirror the events emitted by SearchStreamRelay.

export interface BaseSSEEvent {
    type: string;
}

export interface StartedEvent extends BaseSSEEvent {
    type: 'started';
    request_id: string;
    tier: string;
    collection_readable_id: string;
}

export interface ThinkingEvent extends BaseSSEEvent {
    type: 'thinking';
    thinking: string | null;
    text: string | null;
    duration_ms: number;
    diagnostics: {
        iteration: number;
    };
}

export interface ToolCallEvent extends BaseSSEEvent {
    type: 'tool_call';
    tool_name: string;
    duration_ms: number;
    diagnostics: {
        iteration: number;
        tool_call_id: string;
        arguments: Record<string, any>;
        stats: Record<string, any>;
    };
}

export interface RerankingEvent extends BaseSSEEvent {
    type: 'reranking';
    duration_ms: number;
    diagnostics: {
        input_count: number;
        output_count: number;
        model: string;
        top_relevance_score: number;
        bottom_relevance_score: number;
    };
}

export interface DoneEvent extends BaseSSEEvent {
    type: 'done';
    results: any[];
    duration_ms: number;
    diagnostics?: {
        total_iterations: number;
        all_seen_entity_ids: string[];
        all_read_entity_ids: string[];
        all_collected_entity_ids: string[];
        max_iterations_hit: boolean;
        total_llm_retries: number;
        stagnation_nudges_sent: number;
        prompt_tokens: number;
        completion_tokens: number;
        cache_creation_input_tokens: number;
        cache_read_input_tokens: number;
    };
}

export interface ErrorEvent extends BaseSSEEvent {
    type: 'error';
    message: string;
    duration_ms?: number;
}

export type SearchEvent =
    | StartedEvent
    | ThinkingEvent
    | ToolCallEvent
    | RerankingEvent
    | DoneEvent
    | ErrorEvent;

// Stream phase for UI state
export type StreamPhase = 'searching' | 'finalized' | 'cancelled';

// Aggregated update emitted alongside raw events
export interface PartialStreamUpdate {
    requestId?: string | null;
    results?: any[];
    status?: StreamPhase;
}
