import { RouterProvider } from '@tanstack/react-router';
import { router } from './router';
import { AuthErrorPage } from '@/app/pages/auth/error';
import { queryClient } from '@/shared/api';
import { useAuth } from '@/shared/auth';
import { Loader } from '@/shared/components/loader';

export function AppRouter() {
  const auth = useAuth();

  if (auth.status === 'loading') {
    return <Loader className="min-h-screen" />;
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
