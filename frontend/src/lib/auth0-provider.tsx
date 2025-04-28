import { Auth0Provider } from '@auth0/auth0-react';
import { useNavigate } from 'react-router-dom';
import { ReactNode } from 'react';
import authConfig from '../config/auth';

interface Auth0ProviderWithNavigationProps {
  children: ReactNode;
}

export const Auth0ProviderWithNavigation = ({ children }: Auth0ProviderWithNavigationProps) => {
  const navigate = useNavigate();

  const onRedirectCallback = (appState: any) => {
    navigate(appState?.returnTo || window.location.pathname);
  };

  // Don't render the Auth0Provider if auth is disabled or config is invalid
  if (!authConfig.authEnabled || !authConfig.isConfigValid()) {
    return <>{children}</>;
  }

  console.log('Auth0 Configuration:', {
    domain: authConfig.auth0.domain,
    clientId: authConfig.auth0.clientId,
    callbackUrl: window.location.origin + '/callback'
  });

  return (
    <Auth0Provider
      domain={authConfig.auth0.domain}
      clientId={authConfig.auth0.clientId}
      authorizationParams={{
        redirect_uri: window.location.origin + '/callback',
        audience: authConfig.auth0.audience,
        scope: "openid profile email"
      }}
      onRedirectCallback={onRedirectCallback}
      cacheLocation="localstorage"
    >
      {children}
    </Auth0Provider>
  );
};
