import { createFileRoute } from '@tanstack/react-router';
import { OnboardingPage } from '@/app/pages/onboarding';

export const Route = createFileRoute('/_authenticated/onboarding')({
  component: RouteComponent,
});

function RouteComponent() {
  return <OnboardingPage />;
}
