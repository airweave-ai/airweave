import { Auth0Provider } from '@auth0/auth0-react';
import { useNavigate } from 'react-router-dom';
import { ReactNode } from 'react';
import authConfig from '../config/auth';

// Returns 'memory' for custom Auth0 domains, 'localstorage' for standard
// *.auth0.com tenants.
//
// Custom domains (e.g. "auth.example.com") share the app's eTLD+1, so the
// Auth0 session cookie is first-party and iframe-based silent auth works
// in all browsers. Tokens stay in memory only (no XSS surface).
//
// Standard tenants (e.g. "tenant.auth0.com") use a third-party cookie for
// the session, which Safari ITP / Firefox strict / Chrome incognito block.
// Tokens must be persisted in localStorage so refreshes don't force
// re-login.
export function getCacheLocation(domain: string): 'memory' | 'localstorage' {
  const isCustomDomain = !domain.endsWith('.auth0.com');
  return isCustomDomain ? 'memory' : 'localstorage';
}

const cacheLocation = getCacheLocation(authConfig.auth0.domain);

// TODO: Remove this IIFE once all active users have loaded the app at
// least once after this deploy (the legacy keys will already be gone).
//
// Module-level: runs exactly once when the module is first imported.
// Always purges the legacy Zustand auth-store key. Only purges Auth0 SDK
// cache keys (@@auth0spajs@@) when using memory caching — in the
// localstorage path those keys are the live token cache.
(function purgeLegacyAuthKeys() {
  const toRemove: string[] = [];
  for (let i = 0; i < localStorage.length; i++) {
    const key = localStorage.key(i);
    if (!key) continue;
    if (key === 'auth-storage') toRemove.push(key);
    if (cacheLocation === 'memory' && key.startsWith('@@auth0spajs@@')) {
      toRemove.push(key);
    }
  }
  toRemove.forEach((k) => localStorage.removeItem(k));
})();

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

  // We are on a third-party OAuth callback path, so we should skip the redirect callback
  const isThirdPartyCallback = window.location.pathname.startsWith('/auth/callback/');

  if (import.meta.env.DEV) {
    console.log('Auth0 Configuration:', {
      domain: authConfig.auth0.domain,
      clientId: authConfig.auth0.clientId,
      callbackUrl: window.location.origin + '/callback',
      cacheLocation,
    });
  }

  return (
    <Auth0Provider
      domain={authConfig.auth0.domain}
      clientId={authConfig.auth0.clientId}
      authorizationParams={{
        redirect_uri: window.location.origin + '/callback',
        audience: authConfig.auth0.audience,
        scope: 'openid profile email',
      }}
      onRedirectCallback={onRedirectCallback}
      cacheLocation={cacheLocation}
      useRefreshTokens={true}
      useRefreshTokensFallback={true}
      skipRedirectCallback={isThirdPartyCallback}
    >
      {children}
    </Auth0Provider>
  );
};
