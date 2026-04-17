import { experimental_streamedQuery } from '@tanstack/query-core';
import { queryOptions } from '@tanstack/react-query';
import type { QueryFunctionContext } from '@tanstack/query-core';
import type { StaleTime } from '@tanstack/react-query';

interface CreateStreamQueryOptionsParams<
  TEvent,
  TData,
  TQueryKey extends ReadonlyArray<unknown>,
> {
  initialValue: TData;
  queryKey: TQueryKey;
  reducer: (state: TData, event: TEvent) => TData;
  refetchMode?: 'append' | 'reset' | 'replace';
  staleTime?: StaleTime;
  streamFn: (
    context: QueryFunctionContext<TQueryKey>,
  ) => AsyncIterable<TEvent> | Promise<AsyncIterable<TEvent>>;
}

export function createStreamQueryOptions<
  TEvent,
  TData,
  TQueryKey extends ReadonlyArray<unknown>,
>({
  initialValue,
  queryKey,
  reducer,
  refetchMode = 'reset',
  staleTime = 0,
  streamFn,
}: CreateStreamQueryOptionsParams<TEvent, TData, TQueryKey>) {
  return queryOptions<TData, Error, TData, TQueryKey>({
    queryFn: experimental_streamedQuery<TEvent, TData, TQueryKey>({
      initialValue,
      reducer,
      refetchMode,
      streamFn,
    }),
    queryKey,
    retry: false,
    staleTime,
  });
}
