/**
 * Search types - TypeScript contracts for SSE events and UI state
 */

export type ISODate = string;

// Base event fields shared across events
export interface BaseEvent {
  type: string;
  ts?: ISODate;
  seq?: number;
  op?: string | null;
  op_seq?: number | null;
  request_id?: string;
}

// Connection & lifecycle events
export interface ConnectedEvent extends BaseEvent {
  type: "connected";
  request_id: string;
}

export interface StartEvent extends BaseEvent {
  type: "start";
  query: string;
  limit: number;
  offset: number;
}

export interface DoneEvent extends BaseEvent {
  type: "done";
}

export interface CancelledEvent extends BaseEvent {
  type: "cancelled";
}

export interface ErrorEvent extends BaseEvent {
  type: "error";
  message: string;
  operation?: string;
  transient?: boolean;
  detail?: string;
}

export interface HeartbeatEvent extends BaseEvent {
  type: "heartbeat";
}

// Results events
export interface ResultsEvent extends BaseEvent {
  type: "results";
  results: unknown[];
}

// Operation lifecycle events
export interface QueryExpansionStartedEvent extends BaseEvent {
  type: "query_expansion_started";
}

export interface QueryExpansionDoneEvent extends BaseEvent {
  type: "query_expansion_done";
  expanded_queries?: string[];
  duration_ms?: number;
}

export interface FilterInterpretationStartedEvent extends BaseEvent {
  type: "filter_interpretation_started";
}

export interface FilterInterpretationDoneEvent extends BaseEvent {
  type: "filter_interpretation_done";
  interpreted_filter?: unknown;
  duration_ms?: number;
}

export interface RetrievalStartedEvent extends BaseEvent {
  type: "retrieval_started";
}

export interface RetrievalDoneEvent extends BaseEvent {
  type: "retrieval_done";
  duration_ms?: number;
}

export interface RerankingStartedEvent extends BaseEvent {
  type: "reranking_started";
}

export interface RerankingDoneEvent extends BaseEvent {
  type: "reranking_done";
  duration_ms?: number;
}

// Completion events
export interface CompletionStartedEvent extends BaseEvent {
  type: "completion_started";
}

export interface CompletionChunkEvent extends BaseEvent {
  type: "completion_chunk";
  text?: string;
}

export interface CompletionDoneEvent extends BaseEvent {
  type: "completion_done";
  text: string;
  duration_ms?: number;
}

// Union of all known events
export type SearchEvent =
  | ConnectedEvent
  | StartEvent
  | ResultsEvent
  | QueryExpansionStartedEvent
  | QueryExpansionDoneEvent
  | FilterInterpretationStartedEvent
  | FilterInterpretationDoneEvent
  | RetrievalStartedEvent
  | RetrievalDoneEvent
  | RerankingStartedEvent
  | RerankingDoneEvent
  | CompletionStartedEvent
  | CompletionChunkEvent
  | CompletionDoneEvent
  | ErrorEvent
  | DoneEvent
  | CancelledEvent
  | HeartbeatEvent;

// Stream phase for UI state
export type StreamPhase = "searching" | "answering" | "finalized" | "cancelled";

// Aggregated UI update
export interface PartialStreamUpdate {
  requestId?: string | null;
  results?: unknown[];
  status?: StreamPhase;
}

// Search method types
export type SearchMethod = "hybrid" | "neural" | "keyword";

// Search toggle state
export interface SearchToggles {
  queryExpansion: boolean;
  filter: boolean;
  queryInterpretation: boolean;
  recencyBias: boolean;
  reRanking: boolean;
  answer: boolean;
}

// Search configuration for API code generation
export interface SearchConfig {
  search_method: SearchMethod;
  expansion_strategy: "auto" | "no_expansion";
  enable_query_interpretation: boolean;
  recency_bias: number | null;
  enable_reranking: boolean;
  response_type: "completion" | "raw";
  filter?: unknown;
}

// Usage check response
export interface UsageCheckResponse {
  allowed: boolean;
  reason?: "usage_limit_exceeded" | "payment_required" | string;
}

// Search response
export interface SearchResponse {
  results: unknown[];
  completion?: string | null;
  responseTime?: number;
  error?: string;
  errorIsTransient?: boolean;
}
