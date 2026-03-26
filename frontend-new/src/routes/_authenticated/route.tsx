import { Outlet, createFileRoute } from '@tanstack/react-router';

export const Route = createFileRoute('/_authenticated')({
  beforeLoad: async ({ context, location }) => {
    const { auth } = context;

    if (!auth.isAuthenticated) {
      await context.auth.login(location.href);
      return;
    }
  },
  component: () => <Outlet />,
});
