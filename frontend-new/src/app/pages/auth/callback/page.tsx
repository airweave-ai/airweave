import { AirweaveLoader } from '@/shared/components/airweave-loader';

type AuthCallbackPageProps = {
  organizationName?: string;
};

export function AuthCallbackPage({ organizationName }: AuthCallbackPageProps) {
  return (
    <AirweaveLoader className="min-h-screen">
      {organizationName ? 'Accepting invitation' : 'Finishing sign-in'}
    </AirweaveLoader>
  );
}
