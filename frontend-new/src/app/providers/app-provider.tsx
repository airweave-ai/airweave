import type { PropsWithChildren } from 'react';
import { router } from '@/app/router';
import { QueryClientProvider } from '@/shared/api';
import { AuthProvider } from '@/shared/auth';
import { TooltipProvider } from '@/shared/ui/tooltip';

function navigateAfterAuth(returnTo: string) {
  router.history.push(returnTo);
}

export function AppProvider({ children }: PropsWithChildren) {
  return (
    <TooltipProvider>
      <QueryClientProvider>
        <AuthProvider
          callbackPath="/callback"
          defaultReturnTo="/"
          onRedirect={navigateAfterAuth}
        >
          {children}
        </AuthProvider>
      </QueryClientProvider>
    </TooltipProvider>
  );
}
