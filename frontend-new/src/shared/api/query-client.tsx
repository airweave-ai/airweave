import * as React from 'react';
import {
  QueryClient,
  QueryClientProvider as ReactQueryClientProvider,
} from '@tanstack/react-query';

export const queryClient = new QueryClient();

export function QueryClientProvider({ children }: React.PropsWithChildren) {
  return (
    <ReactQueryClientProvider client={queryClient}>
      {children}
    </ReactQueryClientProvider>
  );
}
