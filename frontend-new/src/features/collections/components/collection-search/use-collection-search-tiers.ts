import * as React from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import {
  agenticCollectionSearchStreamQueryOptions,
  classicCollectionSearchQueryOptions,
  instantCollectionSearchQueryOptions,
} from '../../api';
import {
  getDefaultCollectionSearchRequest,
  isCollectionSearchRequestEqual,
} from '../../lib/collection-search-request';
import type { QueryKey } from '@tanstack/react-query';
import type { CollectionSearchTierName } from '../../lib/collection-search-model';
import type { CollectionSearchRequest } from '../../lib/collection-search-request';
import type {
  SearchAgenticDoneEvent,
  SearchAgenticStreamEvent,
  SearchV2Response,
} from '@/shared/api';
import { getApiErrorMessage } from '@/shared/api';
import { useCurrentOrganizationId } from '@/shared/session';

type JsonCollectionSearchQueryOptions = ReturnType<
  | typeof classicCollectionSearchQueryOptions
  | typeof instantCollectionSearchQueryOptions
>;

type JsonCollectionSearchRequest = Extract<
  CollectionSearchRequest,
  { tier: 'classic' | 'instant' }
>;

type CollectionSearchTierRequest<TTier extends CollectionSearchTierName> =
  Extract<CollectionSearchRequest, { tier: TTier }>;

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

export type CollectionSearchTierController<
  TRequest extends CollectionSearchRequest = CollectionSearchRequest,
> = {
  cancel: () => void;
  refetch: () => void;
  state: CollectionSearchTierState;
  submit: (request: TRequest) => void;
};

export type CollectionSearchTiers = {
  agentic: CollectionSearchTierController<
    CollectionSearchTierRequest<'agentic'>
  >;
  classic: CollectionSearchTierController<
    CollectionSearchTierRequest<'classic'>
  >;
  instant: CollectionSearchTierController<
    CollectionSearchTierRequest<'instant'>
  >;
};

export function useCollectionSearchTiers({
  collectionId,
}: {
  collectionId: string;
}): CollectionSearchTiers {
  const organizationId = useCurrentOrganizationId();

  const instant = useJsonCollectionSearchTier({
    buildQueryOptions: instantCollectionSearchQueryOptions,
    collectionId,
    errorMessage: 'Instant search failed. Try again.',
    organizationId,
    tier: 'instant',
  });
  const classic = useJsonCollectionSearchTier({
    buildQueryOptions: classicCollectionSearchQueryOptions,
    collectionId,
    errorMessage: 'Search failed. Try again.',
    organizationId,
    tier: 'classic',
  });
  const agentic = useAgenticCollectionSearchTier({
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

function useJsonCollectionSearchTier<
  TRequest extends JsonCollectionSearchRequest,
>({
  buildQueryOptions,
  collectionId,
  errorMessage,
  organizationId,
  tier,
}: {
  buildQueryOptions: (
    organizationId: string,
    request: TRequest,
  ) => JsonCollectionSearchQueryOptions;
  collectionId: string;
  errorMessage: string;
  organizationId: string;
  tier: TRequest['tier'];
}): CollectionSearchTierController<TRequest> {
  const queryClient = useQueryClient();
  const defaultRequest = React.useMemo(
    () => getDefaultCollectionSearchRequest(collectionId, tier) as TRequest,
    [collectionId, tier],
  );
  const [submittedRequest, setSubmittedRequest] =
    React.useState<TRequest | null>(null);
  const activeRequest = React.useMemo(
    () =>
      submittedRequest?.collectionId === collectionId ? submittedRequest : null,
    [collectionId, submittedRequest],
  );
  const queryOptions = React.useMemo(
    () => buildQueryOptions(organizationId, activeRequest ?? defaultRequest),
    [activeRequest, buildQueryOptions, defaultRequest, organizationId],
  );
  const query = useQuery({
    ...queryOptions,
    enabled: activeRequest !== null,
  });

  const submit = React.useCallback(
    (request: TRequest) => {
      if (isCollectionSearchRequestEqual(activeRequest, request)) {
        void query.refetch();
        return;
      }

      setSubmittedRequest(request);
    },
    [activeRequest, query],
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
}: {
  collectionId: string;
  organizationId: string;
}): CollectionSearchTierController<CollectionSearchTierRequest<'agentic'>> {
  const queryClient = useQueryClient();
  const defaultRequest = React.useMemo(
    () =>
      getDefaultCollectionSearchRequest(
        collectionId,
        'agentic',
      ) as CollectionSearchTierRequest<'agentic'>,
    [collectionId],
  );
  const [submittedRequest, setSubmittedRequest] =
    React.useState<CollectionSearchTierRequest<'agentic'> | null>(null);
  const activeRequest = React.useMemo(
    () =>
      submittedRequest?.collectionId === collectionId ? submittedRequest : null,
    [collectionId, submittedRequest],
  );
  const queryOptions = React.useMemo(
    () =>
      agenticCollectionSearchStreamQueryOptions(
        organizationId,
        activeRequest ?? defaultRequest,
      ),
    [activeRequest, defaultRequest, organizationId],
  );
  const query = useQuery({
    ...queryOptions,
    enabled: activeRequest !== null,
  });

  const submit = React.useCallback(
    (request: CollectionSearchTierRequest<'agentic'>) => {
      if (isCollectionSearchRequestEqual(activeRequest, request)) {
        void query.refetch();
        return;
      }

      setSubmittedRequest(request);
    },
    [activeRequest, query],
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
