import { useAuth0 } from '@auth0/auth0-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card';
import { Loader2 } from 'lucide-react';
import authConfig from '../config/auth';
import { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';

export const LoginPage = () => {
  const { loginWithRedirect, isAuthenticated, isLoading, error } = useAuth0();
  const navigate = useNavigate();

  // Log any errors
  useEffect(() => {
    if (error) {
      console.error('Auth0 login error:', error);
    }
  }, [error]);

  useEffect(() => {
    // If auth is disabled or user is authenticated, redirect to home
    if (!authConfig.authEnabled || isAuthenticated) {
      navigate('/');
    }
  }, [isAuthenticated, navigate]);

  // If auth is disabled, don't show the login page
  if (!authConfig.authEnabled) {
    return <div>Redirecting...</div>;
  }

  const handleLogin = () => {
    console.log('Initiating login redirect...');
    // Use explicit config to ensure correct values are used
    loginWithRedirect({
      authorizationParams: {
        redirect_uri: window.location.origin + '/callback',
        audience: authConfig.auth0.audience,
        scope: "openid profile email"
      }
    });
  };

  return (
    <div className="flex h-screen w-full items-center justify-center bg-gray-50 dark:bg-gray-900">
      <Card className="w-[350px]">
        <CardHeader>
          <CardTitle>Welcome to Airweave</CardTitle>
          <CardDescription>Sign in to access your account</CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col items-center justify-center gap-4">
          {isLoading ? (
            <Loader2 className="h-6 w-6 animate-spin" />
          ) : (
            <Button
              onClick={handleLogin}
              className="px-6"
            >
              Sign in
            </Button>
          )}
          {error && (
            <p className="text-sm text-red-500 mt-2">
              {error.message || 'An error occurred during login'}
            </p>
          )}
        </CardContent>
      </Card>
    </div>
  );
};
