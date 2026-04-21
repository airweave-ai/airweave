import * as React from 'react';
import {
  MutationCache,
  QueryClient,
  QueryClientProvider as ReactQueryClientProvider,
} from '@tanstack/react-query';
import { toast } from 'sonner';
import { getApiErrorMessage } from './errors';
import { invalidateQueriesByTags } from './invalidate-queries-by-tags';

export const queryClient = new QueryClient({
  mutationCache: new MutationCache({
    onError: (error, _variables, _onMutateResult, mutation) => {
      if (mutation.meta?.errorToast === false) {
        return;
      }

      const message =
        typeof mutation.meta?.errorToast === 'string'
          ? mutation.meta.errorToast
          : (getApiErrorMessage(error, 'Something went wrong.') ??
            'Something went wrong.');

      toast.error(message);
    },
    onSuccess: async (
      _data,
      _variables,
      _onMutateResult,
      mutation,
      context,
    ) => {
      const tags = mutation.meta?.invalidateTags;

      if (!tags?.length) {
        return;
      }

      await invalidateQueriesByTags(context.client, tags);
    },
  }),
  defaultOptions: {
    queries: {
      staleTime: 300,
    },
  },
});

export function QueryClientProvider({ children }: React.PropsWithChildren) {
  return (
    <ReactQueryClientProvider client={queryClient}>
      {children}
    </ReactQueryClientProvider>
  );
}
