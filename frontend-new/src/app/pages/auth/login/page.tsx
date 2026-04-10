import { Loader } from '@/shared/components/loader';

type LoginPageProps = {
  organizationName?: string;
};

export function LoginPage(props: LoginPageProps) {
  if (props.organizationName) {
    return (
      <Loader className="min-h-screen">{`You've been invited to join ${props.organizationName}`}</Loader>
    );
  }

  return <Loader className="min-h-screen">Redirecting to sign in</Loader>;
}
