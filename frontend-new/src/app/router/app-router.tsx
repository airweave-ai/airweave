import { RouterProvider } from '@tanstack/react-router';
import { router } from '@/app/router';
import { queryClient } from '@/shared/api';
import { useAuth } from '@/shared/auth';

export function AppRouter() {
  const auth = useAuth();

  if (auth.isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        Loading...
      </div>
    );
  }

  return <RouterProvider context={{ auth, queryClient }} router={router} />;
}
