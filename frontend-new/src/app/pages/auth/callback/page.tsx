import { Loader } from '@/shared/components/loader';

type AuthCallbackPageProps = {
  organizationName?: string;
};

export function AuthCallbackPage({ organizationName }: AuthCallbackPageProps) {
  return (
    <Loader className="min-h-screen">
      {organizationName ? 'Accepting invitation' : 'Finishing sign-in'}
    </Loader>
  );
}
