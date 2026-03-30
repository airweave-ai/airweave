import { AuthStatusScreen } from '../components/status-screen';

type LoginPageProps = {
  organizationName?: string;
};

export function LoginPage(props: LoginPageProps) {
  if (props.organizationName) {
    return (
      <AuthStatusScreen
        description="Please sign in or create an account to accept this invitation. Redirecting you now."
        title={`You've been invited to join ${props.organizationName}`}
      />
    );
  }

  return (
    <AuthStatusScreen
      description="You will be redirected to the Airweave sign-in page in a moment."
      title="Redirecting to sign in"
    />
  );
}
