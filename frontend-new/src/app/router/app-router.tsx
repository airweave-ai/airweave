import { RouterProvider } from '@tanstack/react-router';
import { AuthErrorPage } from '@/app/pages/auth/error';
import { router } from '@/app/router';
import { queryClient } from '@/shared/api';
import { useAuth } from '@/shared/auth';
import { Spinner } from '@/shared/ui/spinner';

export function AppRouter() {
  const auth = useAuth();

  if (auth.status === 'loading') {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <Spinner className="size-8" />
      </div>
    );
  }

  if (auth.status === 'error') {
    return (
      <AuthErrorPage
        error={auth.error}
        onReload={() => window.location.replace('/login')}
      />
    );
  }

  return <RouterProvider context={{ auth, queryClient }} router={router} />;
}
