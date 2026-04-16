import * as React from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import {
  agenticCollectionSearchStreamQueryOptions,
  classicCollectionSearchQueryOptions,
  instantCollectionSearchQueryOptions,
} from '../../api';
import type { QueryKey } from '@tanstack/react-query';
import type {
  SearchAgenticDoneEvent,
  SearchAgenticStreamEvent,
  SearchV2Response,
} from '@/shared/api';
import { getApiErrorMessage } from '@/shared/api';
import { useCurrentOrganizationId } from '@/shared/session';

export const collectionSearchTierNames = [
  'instant',
  'classic',
  'agentic',
] as const;

export type CollectionSearchTierName =
  (typeof collectionSearchTierNames)[number];

export const collectionSearchTierLabels: Record<
  CollectionSearchTierName,
  string
> = {
  instant: 'Instant',
  classic: 'Classic',
  agentic: 'Agentic',
};

type CollectionSearchRequest = {
  collectionId: string;
  query: string;
};

type JsonCollectionSearchQueryOptions = ReturnType<
  | typeof classicCollectionSearchQueryOptions
  | typeof instantCollectionSearchQueryOptions
>;

export type CollectionSearchReasoningEvent = Extract<
  SearchAgenticStreamEvent,
  {
    type: 'thinking' | 'tool_call' | 'reranking';
  }
>;

export type CollectionSearchTierState = {
  status: 'idle' | 'loading' | 'success' | 'error';
  data?: SearchV2Response;
  error?: string;
  reasoningEvents?: Array<CollectionSearchReasoningEvent>;
  rawFinalEvent?: SearchAgenticDoneEvent;
};

export type CollectionSearchTierController = {
  cancel: () => void;
  refetch: () => void;
  state: CollectionSearchTierState;
  submit: (query: string) => void;
};

export type CollectionSearchTiers = Record<
  CollectionSearchTierName,
  CollectionSearchTierController
>;

export function useCollectionSearchTiers({
  agenticThinking = true,
  collectionId,
}: {
  agenticThinking?: boolean;
  collectionId: string;
}): CollectionSearchTiers {
  const organizationId = useCurrentOrganizationId();

  const instant = useJsonCollectionSearchTier({
    buildQueryOptions: instantCollectionSearchQueryOptions,
    collectionId,
    errorMessage: 'Instant search failed. Try again.',
    organizationId,
  });
  const classic = useJsonCollectionSearchTier({
    buildQueryOptions: classicCollectionSearchQueryOptions,
    collectionId,
    errorMessage: 'Search failed. Try again.',
    organizationId,
  });
  const agentic = useAgenticCollectionSearchTier({
    thinking: agenticThinking,
    collectionId,
    organizationId,
  });

  return React.useMemo(
    () => ({
      agentic,
      classic,
      instant,
    }),
    [agentic, classic, instant],
  );
}

function useJsonCollectionSearchTier({
  buildQueryOptions,
  collectionId,
  errorMessage,
  organizationId,
}: {
  buildQueryOptions: (
    organizationId: string,
    request: CollectionSearchRequest,
  ) => JsonCollectionSearchQueryOptions;
  collectionId: string;
  errorMessage: string;
  organizationId: string;
}): CollectionSearchTierController {
  const queryClient = useQueryClient();
  const [submittedRequest, setSubmittedRequest] =
    React.useState<CollectionSearchRequest | null>(null);
  const activeRequest = React.useMemo(
    () =>
      submittedRequest?.collectionId === collectionId ? submittedRequest : null,
    [collectionId, submittedRequest],
  );
  const queryOptions = React.useMemo(
    () =>
      buildQueryOptions(organizationId, {
        collectionId: activeRequest?.collectionId ?? collectionId,
        query: activeRequest?.query ?? '',
      }),
    [
      activeRequest?.collectionId,
      activeRequest?.query,
      buildQueryOptions,
      collectionId,
      organizationId,
    ],
  );
  const query = useQuery({
    ...queryOptions,
    enabled: activeRequest !== null,
  });

  const submit = React.useCallback(
    (queryText: string) => {
      if (activeRequest?.query === queryText) {
        void query.refetch();
        return;
      }

      setSubmittedRequest({
        collectionId,
        query: queryText,
      });
    },
    [activeRequest?.query, collectionId, query],
  );

  const cancel = React.useCallback(() => {
    if (activeRequest === null) {
      return;
    }

    void queryClient.cancelQueries({
      exact: true,
      queryKey: queryOptions.queryKey,
    });
  }, [activeRequest, queryClient, queryOptions.queryKey]);

  const refetch = React.useCallback(() => {
    if (activeRequest === null) {
      return;
    }

    void query.refetch();
  }, [activeRequest, query]);

  const state = React.useMemo<CollectionSearchTierState>(() => {
    if (activeRequest === null) {
      return { status: 'idle' };
    }

    if (query.isFetching) {
      return {
        data: query.data,
        status: 'loading',
      };
    }

    if (query.isError) {
      return {
        error: getApiErrorMessage(query.error, errorMessage),
        status: 'error',
      };
    }

    if (query.data) {
      return {
        data: query.data,
        status: 'success',
      };
    }

    return { status: 'idle' };
  }, [
    activeRequest,
    errorMessage,
    query.data,
    query.error,
    query.isError,
    query.isFetching,
  ]);

  return React.useMemo(
    () => ({
      cancel,
      refetch,
      state,
      submit,
    }),
    [cancel, refetch, state, submit],
  );
}

function useAgenticCollectionSearchTier({
  collectionId,
  organizationId,
  thinking,
}: {
  collectionId: string;
  organizationId: string;
  thinking?: boolean;
}): CollectionSearchTierController {
  const queryClient = useQueryClient();
  const [submittedRequest, setSubmittedRequest] =
    React.useState<CollectionSearchRequest | null>(null);
  const activeRequest = React.useMemo(
    () =>
      submittedRequest?.collectionId === collectionId ? submittedRequest : null,
    [collectionId, submittedRequest],
  );
  const queryOptions = React.useMemo(
    () =>
      agenticCollectionSearchStreamQueryOptions(organizationId, {
        collectionId: activeRequest?.collectionId ?? collectionId,
        query: activeRequest?.query ?? '',
        thinking,
      }),
    [
      activeRequest?.collectionId,
      activeRequest?.query,
      collectionId,
      organizationId,
      thinking,
    ],
  );
  const query = useQuery({
    ...queryOptions,
    enabled: activeRequest !== null,
  });

  const submit = React.useCallback(
    (queryText: string) => {
      if (activeRequest?.query === queryText) {
        void query.refetch();
        return;
      }

      setSubmittedRequest({
        collectionId,
        query: queryText,
      });
    },
    [activeRequest?.query, collectionId, query],
  );

  const cancel = React.useCallback(() => {
    if (activeRequest === null) {
      return;
    }

    void queryClient.cancelQueries({
      exact: true,
      queryKey: queryOptions.queryKey as QueryKey,
    });
  }, [activeRequest, queryClient, queryOptions.queryKey]);

  const refetch = React.useCallback(() => {
    if (activeRequest === null) {
      return;
    }

    void query.refetch();
  }, [activeRequest, query]);

  const state = React.useMemo<CollectionSearchTierState>(() => {
    if (activeRequest === null) {
      return { status: 'idle' };
    }

    const streamState = query.data;
    const reasoningEvents = getReasoningEvents(streamState?.events ?? []);
    const rawFinalEvent = streamState?.finalEvent;
    const data = rawFinalEvent
      ? {
          results: rawFinalEvent.results,
        }
      : undefined;

    if (query.isFetching) {
      return {
        data,
        rawFinalEvent,
        reasoningEvents,
        status: 'loading',
      };
    }

    if (query.isError) {
      return {
        error: getApiErrorMessage(query.error, 'Search failed. Try again.'),
        reasoningEvents,
        status: 'error',
      };
    }

    if (streamState?.error) {
      return {
        error: streamState.error,
        reasoningEvents,
        status: 'error',
      };
    }

    if (data) {
      return {
        data,
        rawFinalEvent,
        reasoningEvents,
        status: 'success',
      };
    }

    return { status: 'idle' };
  }, [activeRequest, query.data, query.error, query.isError, query.isFetching]);

  return React.useMemo(
    () => ({
      cancel,
      refetch,
      state,
      submit,
    }),
    [cancel, refetch, state, submit],
  );
}

function getReasoningEvents(events: Array<SearchAgenticStreamEvent>) {
  const reasoningEvents = events.filter(isReasoningEvent);

  return reasoningEvents.length > 0 ? reasoningEvents : undefined;
}

function isReasoningEvent(
  event: SearchAgenticStreamEvent,
): event is CollectionSearchReasoningEvent {
  return (
    event.type === 'thinking' ||
    event.type === 'tool_call' ||
    event.type === 'reranking'
  );
}
