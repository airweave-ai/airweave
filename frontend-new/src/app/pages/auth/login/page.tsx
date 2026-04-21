import { AirweaveLoader } from '@/shared/components/airweave-loader';

type LoginPageProps = {
  organizationName?: string;
};

export function LoginPage(props: LoginPageProps) {
  if (props.organizationName) {
    return (
      <AirweaveLoader className="min-h-screen">{`You've been invited to join ${props.organizationName}`}</AirweaveLoader>
    );
  }

  return (
    <AirweaveLoader className="min-h-screen">
      Redirecting to sign in
    </AirweaveLoader>
  );
}
