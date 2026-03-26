import { Outlet, createFileRoute } from '@tanstack/react-router';
import { ensureCurrentUser } from '@/features/app-session';

export const Route = createFileRoute('/_authenticated')({
  beforeLoad: async ({ context, location }) => {
    const { auth } = context;

    if (!auth.isAuthenticated) {
      await context.auth.login(location.href);
      return;
    }

    await ensureCurrentUser({
      authUser: auth.user,
      queryClient: context.queryClient,
    });
  },
  component: () => <Outlet />,
});
