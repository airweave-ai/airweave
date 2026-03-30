import { Outlet, createFileRoute, redirect } from '@tanstack/react-router';
import { ensureCurrentUser } from '@/features/app-session';

export const Route = createFileRoute('/_authenticated')({
  beforeLoad: async ({ context, location }) => {
    const { auth } = context;

    if (!auth.isAuthenticated) {
      throw redirect({
        search: {
          redirect: location.href,
        },
        to: '/login',
      });
    }

    await ensureCurrentUser({
      authUser: auth.user,
      queryClient: context.queryClient,
    });
  },
  component: () => <Outlet />,
});
