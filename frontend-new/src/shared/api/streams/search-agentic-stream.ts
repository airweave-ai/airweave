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

const streamDiagnosticsSchema = z.record(z.string(), z.unknown());

export const searchAgenticStreamEventSchema = z.discriminatedUnion('type', [
  z.object({
    type: z.literal('started'),
    collection_readable_id: z.string(),
    request_id: z.string(),
    tier: z.string(),
  }),
  z.object({
    type: z.literal('thinking'),
    diagnostics: streamDiagnosticsSchema,
    duration_ms: z.number(),
    text: z.string().nullable().optional(),
    thinking: z.string().nullable().optional(),
  }),
  z.object({
    type: z.literal('tool_call'),
    diagnostics: streamDiagnosticsSchema,
    duration_ms: z.number(),
    tool_name: z.string(),
  }),
  z.object({
    type: z.literal('reranking'),
    diagnostics: streamDiagnosticsSchema,
    duration_ms: z.number(),
  }),
  z.object({
    type: z.literal('done'),
    diagnostics: streamDiagnosticsSchema.optional(),
    duration_ms: z.number(),
    results: searchResultsSchema,
  }),
  z.object({
    type: z.literal('error'),
    diagnostics: streamDiagnosticsSchema.optional(),
    duration_ms: z.number().optional(),
    message: z.string(),
    request_id: z.string().optional(),
  }),
]);

export type SearchAgenticStreamEvent = z.infer<
  typeof searchAgenticStreamEventSchema
>;
export type SearchAgenticDoneEvent = Extract<
  SearchAgenticStreamEvent,
  { type: 'done' }
>;
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
