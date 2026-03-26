import { createFileRoute } from '@tanstack/react-router';
import { AuthCallbackPage } from '@/app/pages/auth-callback';

export const Route = createFileRoute('/auth/callback')({
  component: CallbackRouteComponent,
});

function CallbackRouteComponent() {
  return <AuthCallbackPage />;
}
