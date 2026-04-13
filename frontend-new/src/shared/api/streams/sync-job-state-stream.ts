import * as z from 'zod';
import { subscribeEntityStateSyncJobJobIdSubscribeStateGetQueryKey } from '../generated/@tanstack/react-query.gen';
import { createStreamQueryOptions } from './create-stream-query-options';
import { createValidatedSseStream } from './create-validated-sse-stream';
import type { Options } from '../generated/sdk.gen';
import type {
  SubscribeEntityStateSyncJobJobIdSubscribeStateGetData,
  SyncJobStatus,
} from '../generated/types.gen';

const syncJobStatusSchema = z.enum([
  'created',
  'pending',
  'running',
  'completed',
  'failed',
  'cancelling',
  'cancelled',
]);

const terminalSyncJobStatusSchema = z.enum([
  'completed',
  'failed',
  'cancelled',
]);

export const syncJobStateStreamEventSchema = z.discriminatedUnion('type', [
  z.object({
    type: z.literal('connected'),
    job_id: z.uuid(),
  }),
  z.object({
    type: z.literal('heartbeat'),
  }),
  z.object({
    type: z.literal('entity_state'),
    job_id: z.uuid(),
    sync_id: z.uuid(),
    entity_counts: z.record(z.string(), z.number()),
    total_entities: z.number(),
    timestamp: z.string(),
    job_status: syncJobStatusSchema,
  }),
  z.object({
    type: z.literal('sync_complete'),
    job_id: z.uuid(),
    sync_id: z.uuid(),
    is_complete: z.boolean(),
    is_failed: z.boolean(),
    final_counts: z.record(z.string(), z.number()),
    total_entities: z.number(),
    total_operations: z.number(),
    timestamp: z.string(),
    final_status: terminalSyncJobStatusSchema,
    error: z.string().nullable().optional(),
  }),
  z.object({
    type: z.literal('error'),
    message: z.string(),
  }),
]);

export type SyncJobStateStreamEvent = z.infer<
  typeof syncJobStateStreamEventSchema
>;
export type SyncJobStateStreamConnectionStatus =
  | 'connecting'
  | 'streaming'
  | 'closed'
  | 'error';
export type TerminalSyncJobStatus = z.infer<typeof terminalSyncJobStatusSchema>;

export interface SyncJobStateStreamState {
  connectionStatus: SyncJobStateStreamConnectionStatus;
  entityCounts: Record<string, number>;
  error?: string;
  finalStatus?: TerminalSyncJobStatus;
  isComplete?: boolean;
  isFailed?: boolean;
  jobId?: string;
  jobStatus?: SyncJobStatus;
  lastEventAt?: string;
  syncId?: string;
  totalEntities: number;
  totalOperations?: number;
}

export type SubscribeSyncJobStateStreamOptions =
  Options<SubscribeEntityStateSyncJobJobIdSubscribeStateGetData>;

const initialSyncJobStateStreamState: SyncJobStateStreamState = {
  connectionStatus: 'connecting',
  entityCounts: {},
  totalEntities: 0,
};

function isTerminalSyncJobStateStreamEvent(event: SyncJobStateStreamEvent) {
  return event.type === 'sync_complete' || event.type === 'error';
}

function reduceSyncJobStateStreamState(
  state: SyncJobStateStreamState,
  event: SyncJobStateStreamEvent,
): SyncJobStateStreamState {
  switch (event.type) {
    case 'connected':
      return {
        ...state,
        connectionStatus: 'streaming',
        jobId: event.job_id,
      };

    case 'heartbeat':
      return state;

    case 'entity_state':
      return {
        ...state,
        connectionStatus: 'streaming',
        entityCounts: event.entity_counts,
        jobId: event.job_id,
        jobStatus: event.job_status,
        lastEventAt: event.timestamp,
        syncId: event.sync_id,
        totalEntities: event.total_entities,
      };

    case 'sync_complete':
      return {
        ...state,
        connectionStatus: 'closed',
        entityCounts: event.final_counts,
        error: event.error ?? undefined,
        finalStatus: event.final_status,
        isComplete: event.is_complete,
        isFailed: event.is_failed,
        jobId: event.job_id,
        jobStatus: event.final_status,
        lastEventAt: event.timestamp,
        syncId: event.sync_id,
        totalEntities: event.total_entities,
        totalOperations: event.total_operations,
      };

    case 'error':
      return {
        ...state,
        connectionStatus: 'error',
        error: event.message,
      };
  }
}

export function subscribeSyncJobStateStream(
  options: SubscribeSyncJobStateStreamOptions,
): Promise<AsyncIterable<SyncJobStateStreamEvent>> {
  return createValidatedSseStream({
    defaultSecurity: [{ scheme: 'bearer', type: 'http' }],
    isTerminal: isTerminalSyncJobStateStreamEvent,
    options,
    schema: syncJobStateStreamEventSchema,
    url: '/sync/job/{job_id}/subscribe-state',
  });
}

export function subscribeSyncJobStateStreamOptions(
  options: SubscribeSyncJobStateStreamOptions,
) {
  const queryKey =
    subscribeEntityStateSyncJobJobIdSubscribeStateGetQueryKey(options);

  return createStreamQueryOptions<
    SyncJobStateStreamEvent,
    SyncJobStateStreamState,
    typeof queryKey
  >({
    initialValue: initialSyncJobStateStreamState,
    queryKey,
    reducer: reduceSyncJobStateStreamState,
    streamFn: ({ signal }) =>
      subscribeSyncJobStateStream({
        ...options,
        signal,
      }),
  });
}
