import React, { createContext, useContext, useEffect, useState } from 'react';
import { useAuth0 } from '@auth0/auth0-react';
import authConfig from '../config/auth';

interface AuthContextType {
  isAuthenticated: boolean;
  isLoading: boolean;
  user: any;
  login: () => void;
  logout: () => void;
  getToken: () => Promise<string | null>;
  clearToken: () => void;
  token: string | null;
  tokenInitialized: boolean;
  isReady: () => boolean;
}

const AuthContext = createContext<AuthContextType>({
  isAuthenticated: false,
  isLoading: true,
  user: null,
  login: () => {},
  logout: () => {},
  getToken: async () => null,
  clearToken: () => {},
  token: null,
  tokenInitialized: false,
  isReady: () => false,
});

export const useAuth = () => useContext(AuthContext);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [token, setToken] = useState<string | null>(null);
  const [tokenInitialized, setTokenInitialized] = useState(false);

  // Use Auth0 hooks if enabled, otherwise simulate with local state
  const {
    isAuthenticated: auth0IsAuthenticated,
    isLoading: auth0IsLoading,
    user: auth0User,
    loginWithRedirect,
    logout: auth0Logout,
    getAccessTokenSilently,
  } = useAuth0();

  // Default to Auth0 values, but override if auth is disabled
  const isAuthenticated = authConfig.authEnabled ? auth0IsAuthenticated : true;
  const isLoading = authConfig.authEnabled ? (auth0IsLoading || !tokenInitialized) : false;
  const user = authConfig.authEnabled ? auth0User : { name: 'Developer', email: 'dev@example.com' };

  // Get the token when authenticated
  useEffect(() => {
    const getAccessToken = async () => {
      if (authConfig.authEnabled && auth0IsAuthenticated) {
        try {
          const accessToken = await getAccessTokenSilently();
          setToken(accessToken);
          setTokenInitialized(true);
          console.log('Auth initialization complete');

          // Log the token for debugging
          console.log('Auth0 token received:', accessToken);
          console.log('Token length:', accessToken.length);
          // Print first and last 10 characters of token
          console.log('Token preview:', accessToken.substring(0, 10) + '...' + accessToken.substring(accessToken.length - 10));
        } catch (error) {
          console.error('Error getting access token', error);
          setToken(null);
          setTokenInitialized(true); // Mark as initialized even on error
          console.log('Auth initialization complete (with error)');
        }
      } else {
        // For non-auth cases, mark as initialized immediately
        setTokenInitialized(true);
        console.log('Auth initialization complete (non-auth mode)');
      }
    };

    getAccessToken();
  }, [auth0IsAuthenticated, getAccessTokenSilently]);

  // Login function
  const login = () => {
    if (authConfig.authEnabled) {
      loginWithRedirect();
    }
  };

  // Logout function
  const logout = () => {
    // Clear the token when logging out
    setToken(null);

    if (authConfig.authEnabled) {
      auth0Logout({
        logoutParams: {
          returnTo: window.location.origin
        }
      });
    }
  };

  // Clear token function
  const clearToken = () => {
    console.log('Clearing token in auth context');
    setToken(null);
  };

  // Get token function
  const getToken = async (): Promise<string | null> => {
    if (!authConfig.authEnabled) {
      return "dev-mode-token";
    }

    if (token) {
      return token;
    }

    if (auth0IsAuthenticated) {
      try {
        const newToken = await getAccessTokenSilently();
        setToken(newToken);
        return newToken;
      } catch (error) {
        console.error('Error refreshing token', error);
        return null;
      }
    }

    return null;
  };

  // Check if auth is ready
  const isReady = (): boolean => {
    if (!authConfig.authEnabled) {
      return true;
    }
    return tokenInitialized && !auth0IsLoading;
  };

  return (
    <AuthContext.Provider
      value={{
        isAuthenticated,
        isLoading,
        user,
        login,
        logout,
        getToken,
        clearToken,
        token,
        tokenInitialized,
        isReady,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};
