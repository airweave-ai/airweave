import { createFileRoute } from '@tanstack/react-router';
import { LoginPage, loginSearchSchema } from '@/app/pages/login';

export const Route = createFileRoute('/login')({
  component: LoginRouteComponent,
  validateSearch: (search) => loginSearchSchema.parse(search),
});

function LoginRouteComponent() {
  const { redirect } = Route.useSearch();

  return <LoginPage redirect={redirect} />;
}
