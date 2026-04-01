import { useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
import { Loader2 } from 'lucide-react';
import { useAuth } from '@/lib/auth-context';
import { useAuth0 } from '@auth0/auth0-react';
import authConfig from '@/config/auth';

const Login = () => {
  const { login, isAuthenticated } = useAuth();
  const { loginWithRedirect } = useAuth0();
  const [searchParams] = useSearchParams();

  const invitation = searchParams.get('invitation');
  const organization = searchParams.get('organization');
  const organizationName = searchParams.get('organization_name');

  useEffect(() => {
    if (!isAuthenticated && authConfig.authEnabled) {
      if (invitation && organization) {
        const redirectOptions = {
          authorizationParams: {
            invitation,
            organization,
          },
          appState: {
            organizationName: organizationName || undefined,
          },
        };


        loginWithRedirect(redirectOptions);
      } else {
        login();
      }
    } else if (!isAuthenticated) {
      login();
    }
  }, [
    isAuthenticated,
    login,
    loginWithRedirect,
    invitation,
    organization,
    organizationName,
  ]);

  return (
    <div className="flex h-screen w-full items-center justify-center bg-background">
      <div className="flex flex-col items-center justify-center space-y-4 text-center">
        <Loader2 className="h-10 w-10 animate-spin text-primary" />
        {organizationName ? (
          <>
            <p className="text-lg font-semibold">
              You've been invited to join {organizationName}
            </p>
            <p className="text-muted-foreground">
              Please log in or sign up to accept the invitation. Redirecting
              you...
            </p>
          </>
        ) : (
          <p className="text-muted-foreground">Redirecting to login...</p>
        )}
      </div>
    </div>
  );
};

export default Login;
