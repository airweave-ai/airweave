import { AuthStatusScreen } from '../components/status-screen';

type AuthCallbackPageProps = {
  organizationName?: string;
};

export function AuthCallbackPage({ organizationName }: AuthCallbackPageProps) {
  return (
    <AuthStatusScreen
      description={
        organizationName
          ? `Finalizing your membership for ${organizationName}.`
          : 'You will be redirected back to the app in a moment.'
      }
      title={organizationName ? 'Accepting invitation' : 'Finishing sign-in'}
    />
  );
}
