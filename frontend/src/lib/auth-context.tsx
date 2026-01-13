import React, { createContext, useContext, useEffect, useState, useCallback } from 'react';
import { useAuth0 } from '@auth0/auth0-react';
import authConfig from '../config/auth';
import { apiClient } from './api';

// Dev mode admin flag - defaults to true for local development convenience
const DEV_IS_ADMIN = import.meta.env.VITE_DEV_IS_ADMIN !== 'false';
console.log('[Auth] DEV_IS_ADMIN:', DEV_IS_ADMIN, 'env value:', import.meta.env.VITE_DEV_IS_ADMIN);

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
  login: () => { },
  logout: () => { },
  getToken: async () => null,
  clearToken: () => { },
  token: null,
  tokenInitialized: false,
  isReady: () => false,
});

export const useAuth = () => useContext(AuthContext);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [token, setToken] = useState<string | null>(null);
  const [tokenInitialized, setTokenInitialized] = useState(false);
  const [enrichedUser, setEnrichedUser] = useState<any>(null);
  const [userProfileLoading, setUserProfileLoading] = useState(false);

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
  const isLoading = authConfig.authEnabled ? (auth0IsLoading || !tokenInitialized || userProfileLoading) : false;
  const user = authConfig.authEnabled ? (enrichedUser || auth0User) : (enrichedUser || { name: 'Developer', email: 'dev@example.com', is_admin: DEV_IS_ADMIN });

  // Debug logging
  console.log('[Auth] authEnabled:', authConfig.authEnabled, 'enrichedUser:', enrichedUser, 'user.is_admin:', user?.is_admin);

  // Get the token when authenticated
  useEffect(() => {
    const getAccessToken = async () => {
      if (authConfig.authEnabled && auth0IsAuthenticated) {
        try {
          const accessToken = await getAccessTokenSilently();
          setToken(accessToken);
          setTokenInitialized(true);
          console.log('Auth initialization complete');

          // Log token acquisition for debugging (without exposing token content)
          console.log('🔑 Access token acquired successfully, length:', accessToken.length);
        } catch (error) {
          console.error('Error getting access token', error);
          setToken(null);
          setTokenInitialized(true); // Mark as initialized even on error
          console.log('Auth initialization complete (with error)');
        }
      } else if (authConfig.authEnabled && auth0IsLoading) {
        // Auth is enabled but Auth0 is still loading - do nothing, wait for it to finish
        console.log('Waiting for Auth0 to finish loading...');
      } else if (authConfig.authEnabled && !auth0IsAuthenticated && !auth0IsLoading) {
        // Auth is enabled, Auth0 has finished loading, but user is not authenticated
        setTokenInitialized(true);
        console.log('Auth initialization complete (user not authenticated)');
      } else if (!authConfig.authEnabled) {
        // For non-auth cases, mark as initialized immediately
        setTokenInitialized(true);
        console.log('Auth initialization complete (non-auth mode)');
      }
    };

    getAccessToken();
  }, [auth0IsAuthenticated, auth0IsLoading, getAccessTokenSilently]);

  // Fetch user profile from backend after auth is complete
  useEffect(() => {
    const fetchUserProfile = async () => {
      if (authConfig.authEnabled && auth0IsAuthenticated && tokenInitialized && auth0User && !enrichedUser) {
        try {
          setUserProfileLoading(true);
          const response = await apiClient.get('/users/');

          if (response.ok) {
            const backendUser = await response.json();
            // Merge Auth0 user with backend user data
            setEnrichedUser({
              ...auth0User,
              is_admin: backendUser.is_admin || false,
              id: backendUser.id,
              // Add any other backend fields you want to include
            });
            console.log('User profile enriched with backend data', { is_admin: backendUser.is_admin });
          } else {
            console.error('Failed to fetch user profile from backend:', response.status);
            // Fallback to Auth0 user without backend data
            setEnrichedUser({
              ...auth0User,
              is_admin: false,
            });
          }
        } catch (error) {
          console.error('Error fetching user profile:', error);
          // Fallback to Auth0 user without backend data
          setEnrichedUser({
            ...auth0User,
            is_admin: false,
          });
        } finally {
          setUserProfileLoading(false);
        }
      } else if (!authConfig.authEnabled) {
        // For dev mode, set a mock user with admin rights (controlled by VITE_DEV_IS_ADMIN)
        setEnrichedUser({ name: 'Developer', email: 'dev@example.com', is_admin: DEV_IS_ADMIN });
      }
    };

    fetchUserProfile();
  }, [auth0IsAuthenticated, tokenInitialized, auth0User]);

  // Login function
  const login = () => {
    if (authConfig.authEnabled) {
      loginWithRedirect();
    }
  };

  // Logout function
  const logout = () => {
    // Clear the token and enriched user when logging out
    setToken(null);
    setEnrichedUser(null);

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
  const getToken = useCallback(async (): Promise<string | null> => {
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
  }, [authConfig.authEnabled, token, auth0IsAuthenticated, getAccessTokenSilently]);

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
