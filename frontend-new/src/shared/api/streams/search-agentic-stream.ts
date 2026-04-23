import * as z from 'zod';
import { streamAgenticSearchCollectionsReadableIdSearchAgenticStreamPostQueryKey } from '../generated/@tanstack/react-query.gen';
import { createStreamQueryOptions } from './create-stream-query-options';
import { createValidatedSseStream } from './create-validated-sse-stream';
import type { StreamConnectionStatus } from './stream-connection-status';
import type { Options } from '../generated/sdk.gen';
import type {
  SearchResult,
  StreamAgenticSearchCollectionsReadableIdSearchAgenticStreamPostData,
} from '../generated/types.gen';

const searchResultsSchema = z.custom<Array<SearchResult>>((value) =>
  Array.isArray(value),
);

const looseRecordSchema = z.looseObject({});

const entitySummarySchema = z.looseObject({
  entity_id: z.string().optional(),
  entity_type: z.string().optional(),
  name: z.string().optional(),
  relevance_score: z.number().nullable().optional(),
  source_name: z.string().optional(),
});

const filterConditionSchema = z.looseObject({
  field: z.string().optional(),
  operator: z.string().optional(),
  value: z.unknown().optional(),
});

const filterGroupSchema = z.looseObject({
  conditions: z.array(filterConditionSchema).optional().default([]),
});

const searchQuerySchema = z.looseObject({
  primary: z.string().optional(),
  variations: z.array(z.string()).optional().default([]),
});

const searchToolArgumentsSchema = z.looseObject({
  filter_groups: z.array(filterGroupSchema).optional().default([]),
  limit: z.number().optional(),
  offset: z.number().optional(),
  query: searchQuerySchema.optional(),
  retrieval_strategy: z.enum(['semantic', 'keyword', 'hybrid']).optional(),
});

const entityIdsArgumentsSchema = z.looseObject({
  entity_ids: z.array(z.string()).optional().default([]),
});

const countToolArgumentsSchema = z.looseObject({
  filter_groups: z.array(filterGroupSchema).optional().default([]),
});

const navigateToolArgumentsSchema = z.looseObject({
  entity_id: z.string().optional(),
  limit: z.number().optional(),
});

const emptyArgumentsSchema = z.looseObject({});

const searchToolStatsSchema = z.looseObject({
  first_results: z.array(entitySummarySchema).optional().default([]),
  new_results: z.number().optional(),
  result_count: z.number().optional(),
});

const readToolStatsSchema = z.looseObject({
  context_label: z.string().nullable().optional(),
  entities: z.array(entitySummarySchema).optional().default([]),
  found: z.number().optional(),
  not_found: z.number().optional(),
});

const collectToolStatsSchema = z.looseObject({
  added: z.number().optional(),
  already_collected: z.number().optional(),
  entities: z.array(entitySummarySchema).optional().default([]),
  not_found: z.number().optional(),
  total_collected: z.number().optional(),
});

const countToolStatsSchema = z.looseObject({
  count: z.number().optional(),
});

const navigateToolStatsSchema = z.looseObject({
  context_label: z.string().optional(),
  first_results: z.array(entitySummarySchema).optional().default([]),
  result_count: z.number().optional(),
});

const reviewToolStatsSchema = z.looseObject({
  entity_count: z.number().optional(),
  first_results: z.array(entitySummarySchema).optional().default([]),
  total_collected: z.number().optional(),
});

const finishToolStatsSchema = z.looseObject({
  accepted: z.boolean().optional(),
  total_collected: z.number().optional(),
  warning: z.string().nullable().optional(),
});

const thinkingDiagnosticsSchema = z.looseObject({
  completion_tokens: z.number().optional(),
  iteration: z.number().optional(),
  prompt_tokens: z.number().optional(),
});

const toolCallDiagnosticsSchema = z.looseObject({
  arguments: looseRecordSchema.optional().default({}),
  iteration: z.number().optional(),
  stats: looseRecordSchema.optional().default({}),
  tool_call_id: z.string().optional(),
});

const rerankingDiagnosticsSchema = z.looseObject({
  bottom_relevance_score: z.number().optional(),
  first_results: z.array(entitySummarySchema).optional().default([]),
  input_count: z.number().optional(),
  model: z.string().optional(),
  output_count: z.number().optional(),
  top_relevance_score: z.number().optional(),
});

const doneDiagnosticsSchema = z.looseObject({
  all_collected_entity_ids: z.array(z.string()).optional().default([]),
  all_read_entity_ids: z.array(z.string()).optional().default([]),
  all_seen_entity_ids: z.array(z.string()).optional().default([]),
  cache_creation_input_tokens: z.number().optional(),
  cache_read_input_tokens: z.number().optional(),
  completion_tokens: z.number().optional(),
  max_iterations_hit: z.boolean().optional(),
  prompt_tokens: z.number().optional(),
  stagnation_nudges_sent: z.number().optional(),
  total_iterations: z.number().optional(),
  total_llm_retries: z.number().optional(),
});

const rawSearchAgenticStreamEventSchema = z.discriminatedUnion('type', [
  z.object({
    type: z.literal('started'),
    collection_readable_id: z.string(),
    request_id: z.string(),
    tier: z.string(),
  }),
  z.object({
    type: z.literal('thinking'),
    diagnostics: z.unknown(),
    duration_ms: z.number(),
    text: z.string().nullable().optional(),
    thinking: z.string().nullable().optional(),
  }),
  z.object({
    type: z.literal('tool_call'),
    diagnostics: z.unknown(),
    duration_ms: z.number(),
    tool_name: z.string(),
  }),
  z.object({
    type: z.literal('reranking'),
    diagnostics: z.unknown(),
    duration_ms: z.number(),
  }),
  z.object({
    type: z.literal('done'),
    diagnostics: z.unknown().optional(),
    duration_ms: z.number(),
    results: searchResultsSchema,
  }),
  z.object({
    type: z.literal('error'),
    diagnostics: z.unknown().optional(),
    duration_ms: z.number().optional(),
    message: z.string(),
    request_id: z.string().optional(),
  }),
]);

const defaultSearchToolArguments = searchToolArgumentsSchema.parse({});
const defaultEntityIdsArguments = entityIdsArgumentsSchema.parse({});
const defaultCountToolArguments = countToolArgumentsSchema.parse({});
const defaultNavigateToolArguments = navigateToolArgumentsSchema.parse({});
const defaultEmptyArguments = emptyArgumentsSchema.parse({});
const defaultSearchToolStats = searchToolStatsSchema.parse({});
const defaultReadToolStats = readToolStatsSchema.parse({});
const defaultCollectToolStats = collectToolStatsSchema.parse({});
const defaultCountToolStats = countToolStatsSchema.parse({});
const defaultNavigateToolStats = navigateToolStatsSchema.parse({});
const defaultReviewToolStats = reviewToolStatsSchema.parse({});
const defaultFinishToolStats = finishToolStatsSchema.parse({});
const defaultThinkingDiagnostics = thinkingDiagnosticsSchema.parse({});
const defaultToolCallDiagnostics = toolCallDiagnosticsSchema.parse({});
const defaultRerankingDiagnostics = rerankingDiagnosticsSchema.parse({});
const defaultDoneDiagnostics = doneDiagnosticsSchema.parse({});

type RawSearchAgenticStreamEvent = z.infer<
  typeof rawSearchAgenticStreamEventSchema
>;
type RawSearchAgenticToolCallEvent = Extract<
  RawSearchAgenticStreamEvent,
  { type: 'tool_call' }
>;

type SearchAgenticRecord = Record<string, unknown>;

export type SearchAgenticEntitySummary = z.infer<typeof entitySummarySchema>;
export type SearchAgenticFilterCondition = z.infer<typeof filterConditionSchema>;
export type SearchAgenticFilterGroup = z.infer<typeof filterGroupSchema>;
export type SearchAgenticSearchQuery = z.infer<typeof searchQuerySchema>;
export type SearchAgenticSearchToolArguments = z.infer<
  typeof searchToolArgumentsSchema
>;
export type SearchAgenticEntityIdsArguments = z.infer<
  typeof entityIdsArgumentsSchema
>;
export type SearchAgenticCountToolArguments = z.infer<
  typeof countToolArgumentsSchema
>;
export type SearchAgenticNavigateToolArguments = z.infer<
  typeof navigateToolArgumentsSchema
>;
export type SearchAgenticEmptyArguments = z.infer<typeof emptyArgumentsSchema>;
export type SearchAgenticSearchToolStats = z.infer<typeof searchToolStatsSchema>;
export type SearchAgenticReadToolStats = z.infer<typeof readToolStatsSchema>;
export type SearchAgenticCollectToolStats = z.infer<typeof collectToolStatsSchema>;
export type SearchAgenticCountToolStats = z.infer<typeof countToolStatsSchema>;
export type SearchAgenticNavigateToolStats = z.infer<
  typeof navigateToolStatsSchema
>;
export type SearchAgenticReviewToolStats = z.infer<typeof reviewToolStatsSchema>;
export type SearchAgenticFinishToolStats = z.infer<typeof finishToolStatsSchema>;
export type SearchAgenticThinkingDiagnostics = z.infer<
  typeof thinkingDiagnosticsSchema
>;
export type SearchAgenticToolCallDiagnostics<
  TArguments extends SearchAgenticRecord = SearchAgenticRecord,
  TStats extends SearchAgenticRecord = SearchAgenticRecord,
> = Omit<z.infer<typeof toolCallDiagnosticsSchema>, 'arguments' | 'stats'> & {
  arguments: TArguments;
  stats: TStats;
};
export type SearchAgenticRerankingDiagnostics = z.infer<
  typeof rerankingDiagnosticsSchema
>;
export type SearchAgenticDoneDiagnostics = z.infer<typeof doneDiagnosticsSchema>;
export type SearchAgenticToolKind =
  | 'add_to_results'
  | 'count'
  | 'get_children'
  | 'get_parent'
  | 'get_siblings'
  | 'hybrid_search'
  | 'keyword_search'
  | 'read'
  | 'remove_from_results'
  | 'review_results'
  | 'return_results_to_user'
  | 'semantic_search'
  | 'unknown';

export interface SearchAgenticStartedEvent {
  type: 'started';
  collection_readable_id: string;
  request_id: string;
  tier: string;
}

export interface SearchAgenticThinkingEvent {
  type: 'thinking';
  diagnostics: SearchAgenticThinkingDiagnostics;
  duration_ms: number;
  text?: string | null;
  thinking?: string | null;
}

interface SearchAgenticBaseToolCallEvent<
  TToolName extends string,
  TToolKind extends SearchAgenticToolKind,
  TArguments extends SearchAgenticRecord,
  TStats extends SearchAgenticRecord,
> {
  type: 'tool_call';
  diagnostics: SearchAgenticToolCallDiagnostics<TArguments, TStats>;
  duration_ms: number;
  tool_kind: TToolKind;
  tool_name: TToolName;
}

export type SearchAgenticSemanticSearchToolCallEvent =
  SearchAgenticBaseToolCallEvent<
    'search',
    'semantic_search',
    SearchAgenticSearchToolArguments & { retrieval_strategy: 'semantic' },
    SearchAgenticSearchToolStats
  >;

export type SearchAgenticKeywordSearchToolCallEvent =
  SearchAgenticBaseToolCallEvent<
    'search',
    'keyword_search',
    SearchAgenticSearchToolArguments & { retrieval_strategy: 'keyword' },
    SearchAgenticSearchToolStats
  >;

export type SearchAgenticHybridSearchToolCallEvent =
  SearchAgenticBaseToolCallEvent<
    'search',
    'hybrid_search',
    SearchAgenticSearchToolArguments & { retrieval_strategy: 'hybrid' },
    SearchAgenticSearchToolStats
  >;

export type SearchAgenticReadToolCallEvent = SearchAgenticBaseToolCallEvent<
  'read',
  'read',
  SearchAgenticEntityIdsArguments,
  SearchAgenticReadToolStats
>;

export type SearchAgenticAddToResultsToolCallEvent =
  SearchAgenticBaseToolCallEvent<
    'add_to_results',
    'add_to_results',
    SearchAgenticEntityIdsArguments,
    SearchAgenticCollectToolStats
  >;

export type SearchAgenticRemoveFromResultsToolCallEvent =
  SearchAgenticBaseToolCallEvent<
    'remove_from_results',
    'remove_from_results',
    SearchAgenticEntityIdsArguments,
    SearchAgenticCollectToolStats
  >;

export type SearchAgenticCountToolCallEvent = SearchAgenticBaseToolCallEvent<
  'count',
  'count',
  SearchAgenticCountToolArguments,
  SearchAgenticCountToolStats
>;

export type SearchAgenticGetChildrenToolCallEvent =
  SearchAgenticBaseToolCallEvent<
    'get_children',
    'get_children',
    SearchAgenticNavigateToolArguments,
    SearchAgenticNavigateToolStats
  >;

export type SearchAgenticGetSiblingsToolCallEvent =
  SearchAgenticBaseToolCallEvent<
    'get_siblings',
    'get_siblings',
    SearchAgenticNavigateToolArguments,
    SearchAgenticNavigateToolStats
  >;

export type SearchAgenticGetParentToolCallEvent =
  SearchAgenticBaseToolCallEvent<
    'get_parent',
    'get_parent',
    SearchAgenticNavigateToolArguments,
    SearchAgenticReadToolStats
  >;

export type SearchAgenticReviewResultsToolCallEvent =
  SearchAgenticBaseToolCallEvent<
    'review_results',
    'review_results',
    SearchAgenticEmptyArguments,
    SearchAgenticReviewToolStats
  >;

export type SearchAgenticReturnResultsToolCallEvent =
  SearchAgenticBaseToolCallEvent<
    'return_results_to_user',
    'return_results_to_user',
    SearchAgenticEmptyArguments,
    SearchAgenticFinishToolStats
  >;

export type SearchAgenticUnknownToolCallEvent = SearchAgenticBaseToolCallEvent<
  string,
  'unknown',
  SearchAgenticRecord,
  SearchAgenticRecord
>;

export type SearchAgenticToolCallEvent =
  | SearchAgenticAddToResultsToolCallEvent
  | SearchAgenticCountToolCallEvent
  | SearchAgenticGetChildrenToolCallEvent
  | SearchAgenticGetParentToolCallEvent
  | SearchAgenticGetSiblingsToolCallEvent
  | SearchAgenticHybridSearchToolCallEvent
  | SearchAgenticKeywordSearchToolCallEvent
  | SearchAgenticReadToolCallEvent
  | SearchAgenticRemoveFromResultsToolCallEvent
  | SearchAgenticReturnResultsToolCallEvent
  | SearchAgenticReviewResultsToolCallEvent
  | SearchAgenticSemanticSearchToolCallEvent
  | SearchAgenticUnknownToolCallEvent;

export interface SearchAgenticRerankingEvent {
  type: 'reranking';
  diagnostics: SearchAgenticRerankingDiagnostics;
  duration_ms: number;
}

export interface SearchAgenticDoneEvent {
  type: 'done';
  diagnostics?: SearchAgenticDoneDiagnostics;
  duration_ms: number;
  results: Array<SearchResult>;
}

export interface SearchAgenticErrorEvent {
  type: 'error';
  diagnostics?: SearchAgenticRecord;
  duration_ms?: number;
  message: string;
  request_id?: string;
}

export type SearchAgenticStreamEvent =
  | SearchAgenticStartedEvent
  | SearchAgenticThinkingEvent
  | SearchAgenticToolCallEvent
  | SearchAgenticRerankingEvent
  | SearchAgenticDoneEvent
  | SearchAgenticErrorEvent;
export type SearchAgenticStreamConnectionStatus = StreamConnectionStatus;

export interface SearchAgenticStreamState {
  connectionStatus: SearchAgenticStreamConnectionStatus;
  error?: string;
  events: Array<SearchAgenticStreamEvent>;
  finalEvent?: SearchAgenticDoneEvent;
}

export type SubscribeSearchAgenticStreamOptions =
  Options<StreamAgenticSearchCollectionsReadableIdSearchAgenticStreamPostData>;

const initialSearchAgenticStreamState: SearchAgenticStreamState = {
  connectionStatus: 'connecting',
  events: [],
};

export const searchAgenticStreamEventSchema =
  rawSearchAgenticStreamEventSchema.transform(
    (event): SearchAgenticStreamEvent => normalizeSearchAgenticStreamEvent(event),
  );

function isTerminalSearchAgenticStreamEvent(event: SearchAgenticStreamEvent) {
  return event.type === 'done' || event.type === 'error';
}

function appendEvent(
  state: SearchAgenticStreamState,
  event: SearchAgenticStreamEvent,
) {
  return [...state.events, event];
}

function reduceSearchAgenticStreamState(
  state: SearchAgenticStreamState,
  event: SearchAgenticStreamEvent,
): SearchAgenticStreamState {
  switch (event.type) {
    case 'started':
    case 'thinking':
    case 'tool_call':
    case 'reranking':
      return {
        ...state,
        connectionStatus: 'streaming',
        events: appendEvent(state, event),
      };

    case 'done':
      return {
        ...state,
        connectionStatus: 'closed',
        error: undefined,
        events: appendEvent(state, event),
        finalEvent: event,
      };

    case 'error':
      return {
        ...state,
        connectionStatus: 'error',
        error: event.message,
        events: appendEvent(state, event),
      };
  }
}

export function subscribeSearchAgenticStream(
  options: SubscribeSearchAgenticStreamOptions,
): Promise<AsyncIterable<SearchAgenticStreamEvent>> {
  return createValidatedSseStream({
    defaultSecurity: [{ scheme: 'bearer', type: 'http' }],
    isTerminal: isTerminalSearchAgenticStreamEvent,
    method: 'post',
    options,
    schema: searchAgenticStreamEventSchema,
    url: '/collections/{readable_id}/search/agentic/stream',
  });
}

export function subscribeSearchAgenticStreamOptions(
  options: SubscribeSearchAgenticStreamOptions,
) {
  const queryKey =
    streamAgenticSearchCollectionsReadableIdSearchAgenticStreamPostQueryKey(
      options,
    );

  return createStreamQueryOptions<
    SearchAgenticStreamEvent,
    SearchAgenticStreamState,
    typeof queryKey
  >({
    initialValue: initialSearchAgenticStreamState,
    queryKey,
    reducer: reduceSearchAgenticStreamState,
    staleTime: 'static',
    streamFn: ({ signal }) =>
      subscribeSearchAgenticStream({
        ...options,
        signal,
      }),
  });
}

function normalizeSearchAgenticStreamEvent(
  event: RawSearchAgenticStreamEvent,
): SearchAgenticStreamEvent {
  switch (event.type) {
    case 'started':
      return event;

    case 'thinking':
      return {
        ...event,
        diagnostics: parseObject(
          thinkingDiagnosticsSchema,
          event.diagnostics,
          defaultThinkingDiagnostics,
        ),
      };

    case 'tool_call':
      return normalizeToolCallEvent(event);

    case 'reranking':
      return {
        ...event,
        diagnostics: parseObject(
          rerankingDiagnosticsSchema,
          event.diagnostics,
          defaultRerankingDiagnostics,
        ),
      };

    case 'done':
      return {
        ...event,
        diagnostics:
          event.diagnostics === undefined
            ? undefined
            : parseObject(
                doneDiagnosticsSchema,
                event.diagnostics,
                defaultDoneDiagnostics,
              ),
      };

    case 'error':
      return {
        ...event,
        diagnostics:
          event.diagnostics === undefined
            ? undefined
            : parseObject(looseRecordSchema, event.diagnostics, {}),
      };
  }
}

function normalizeToolCallEvent(
  event: RawSearchAgenticToolCallEvent,
): SearchAgenticToolCallEvent {
  switch (event.tool_name) {
    case 'search': {
      const diagnostics = parseToolCallDiagnostics(
        event.diagnostics,
        searchToolArgumentsSchema,
        searchToolStatsSchema,
        defaultSearchToolArguments,
        defaultSearchToolStats,
      );
      const retrievalStrategy = diagnostics.arguments.retrieval_strategy ?? 'hybrid';

      if (retrievalStrategy === 'semantic') {
        return buildToolCallEvent(
          'search',
          'semantic_search',
          event.duration_ms,
          withSearchRetrievalStrategy(diagnostics, 'semantic'),
        );
      }

      if (retrievalStrategy === 'keyword') {
        return buildToolCallEvent(
          'search',
          'keyword_search',
          event.duration_ms,
          withSearchRetrievalStrategy(diagnostics, 'keyword'),
        );
      }

      return buildToolCallEvent(
        'search',
        'hybrid_search',
        event.duration_ms,
        withSearchRetrievalStrategy(diagnostics, 'hybrid'),
      );
    }

    case 'read':
      return buildToolCallEvent(
        'read',
        'read',
        event.duration_ms,
        parseToolCallDiagnostics(
          event.diagnostics,
          entityIdsArgumentsSchema,
          readToolStatsSchema,
          defaultEntityIdsArguments,
          defaultReadToolStats,
        ),
      );

    case 'add_to_results':
      return buildToolCallEvent(
        'add_to_results',
        'add_to_results',
        event.duration_ms,
        parseToolCallDiagnostics(
          event.diagnostics,
          entityIdsArgumentsSchema,
          collectToolStatsSchema,
          defaultEntityIdsArguments,
          defaultCollectToolStats,
        ),
      );

    case 'remove_from_results':
      return buildToolCallEvent(
        'remove_from_results',
        'remove_from_results',
        event.duration_ms,
        parseToolCallDiagnostics(
          event.diagnostics,
          entityIdsArgumentsSchema,
          collectToolStatsSchema,
          defaultEntityIdsArguments,
          defaultCollectToolStats,
        ),
      );

    case 'count':
      return buildToolCallEvent(
        'count',
        'count',
        event.duration_ms,
        parseToolCallDiagnostics(
          event.diagnostics,
          countToolArgumentsSchema,
          countToolStatsSchema,
          defaultCountToolArguments,
          defaultCountToolStats,
        ),
      );

    case 'get_children':
      return buildToolCallEvent(
        'get_children',
        'get_children',
        event.duration_ms,
        parseToolCallDiagnostics(
          event.diagnostics,
          navigateToolArgumentsSchema,
          navigateToolStatsSchema,
          defaultNavigateToolArguments,
          defaultNavigateToolStats,
        ),
      );

    case 'get_siblings':
      return buildToolCallEvent(
        'get_siblings',
        'get_siblings',
        event.duration_ms,
        parseToolCallDiagnostics(
          event.diagnostics,
          navigateToolArgumentsSchema,
          navigateToolStatsSchema,
          defaultNavigateToolArguments,
          defaultNavigateToolStats,
        ),
      );

    case 'get_parent':
      return buildToolCallEvent(
        'get_parent',
        'get_parent',
        event.duration_ms,
        parseToolCallDiagnostics(
          event.diagnostics,
          navigateToolArgumentsSchema,
          readToolStatsSchema,
          defaultNavigateToolArguments,
          defaultReadToolStats,
        ),
      );

    case 'review_results':
      return buildToolCallEvent(
        'review_results',
        'review_results',
        event.duration_ms,
        parseToolCallDiagnostics(
          event.diagnostics,
          emptyArgumentsSchema,
          reviewToolStatsSchema,
          defaultEmptyArguments,
          defaultReviewToolStats,
        ),
      );

    case 'return_results_to_user':
      return buildToolCallEvent(
        'return_results_to_user',
        'return_results_to_user',
        event.duration_ms,
        parseToolCallDiagnostics(
          event.diagnostics,
          emptyArgumentsSchema,
          finishToolStatsSchema,
          defaultEmptyArguments,
          defaultFinishToolStats,
        ),
      );

    default:
      return buildToolCallEvent(
        event.tool_name,
        'unknown',
        event.duration_ms,
        parseToolCallDiagnostics(
          event.diagnostics,
          looseRecordSchema,
          looseRecordSchema,
          {},
          {},
        ),
      );
  }
}

function buildToolCallEvent<
  TToolName extends string,
  TToolKind extends SearchAgenticToolKind,
  TArguments extends SearchAgenticRecord,
  TStats extends SearchAgenticRecord,
>(
  toolName: TToolName,
  toolKind: TToolKind,
  durationMs: number,
  diagnostics: SearchAgenticToolCallDiagnostics<TArguments, TStats>,
): SearchAgenticBaseToolCallEvent<TToolName, TToolKind, TArguments, TStats> {
  return {
    type: 'tool_call',
    diagnostics,
    duration_ms: durationMs,
    tool_kind: toolKind,
    tool_name: toolName,
  };
}

function withSearchRetrievalStrategy<
  TRetrievalStrategy extends 'semantic' | 'keyword' | 'hybrid',
>(
  diagnostics: SearchAgenticToolCallDiagnostics<
    SearchAgenticSearchToolArguments,
    SearchAgenticSearchToolStats
  >,
  retrievalStrategy: TRetrievalStrategy,
): SearchAgenticToolCallDiagnostics<
  SearchAgenticSearchToolArguments & { retrieval_strategy: TRetrievalStrategy },
  SearchAgenticSearchToolStats
> {
  return {
    ...diagnostics,
    arguments: {
      ...diagnostics.arguments,
      retrieval_strategy: retrievalStrategy,
    },
  };
}

function parseToolCallDiagnostics<
  TArguments extends SearchAgenticRecord,
  TStats extends SearchAgenticRecord,
>(
  value: unknown,
  argumentsSchema: z.ZodType<TArguments>,
  statsSchema: z.ZodType<TStats>,
  defaultArguments: TArguments,
  defaultStats: TStats,
): SearchAgenticToolCallDiagnostics<TArguments, TStats> {
  const diagnostics = parseObject(
    toolCallDiagnosticsSchema,
    value,
    defaultToolCallDiagnostics,
  );

  return {
    ...diagnostics,
    arguments: parseObject(argumentsSchema, diagnostics.arguments, defaultArguments),
    stats: parseObject(statsSchema, diagnostics.stats, defaultStats),
  };
}

function parseObject<T extends SearchAgenticRecord>(
  schema: z.ZodType<T>,
  value: unknown,
  fallback: T,
) {
  const result = schema.safeParse(value);

  return result.success ? result.data : fallback;
}
