import { useAuth0 } from '@auth0/auth0-react';
import { useEffect, useRef } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { Loader2 } from 'lucide-react';
import { apiClient } from '@/lib/api';
import { useAuth } from '@/lib/auth-context';

const Callback = () => {
  const {
    isLoading: auth0Loading,
    isAuthenticated,
    error,
    user,
    logout,
  } = useAuth0();
  const { getToken, isLoading: authContextLoading } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  const organizationName = location.state?.appState?.organizationName;

  // Track if we've already attempted to sync to prevent duplicates
  const syncAttempted = useRef(false);

  // Combine both loading states
  const isLoading = auth0Loading || authContextLoading;

  // Function to handle logout - just log out, don't specify returnTo
  const handleLogout = () => {
    logout();
  };

  // Create or update user in backend when authenticated
  useEffect(() => {
    const syncUser = async () => {
      // Only attempt if authenticated, have user data, not loading, and haven't already attempted
      if (isAuthenticated && user && !isLoading && !syncAttempted.current) {
        syncAttempted.current = true; // Mark as attempted to prevent duplicates

        try {
          // Token is now managed by auth context
          const token = await getToken();

          if (!token) {
            console.error("No token available for API call");
            navigate('/');
            return;
          }

          const userData = {
            email: user.email,
            full_name: user.name,
            picture: user.picture,
            auth0_id: user.sub,
            email_verified: user.email_verified,
          };

          const response = await apiClient.post('/users/create_or_update', userData);

          if (response.ok) {
            console.log("✅ User created/updated in backend");
          } else {
            console.error("❌ Failed to create/update user:", response.status);
          }

          navigate('/');
        } catch (err) {
          console.error("❌ Error syncing user with backend:", err);
          navigate('/');
        }
      }
    };

    syncUser();
  }, [isAuthenticated, user, isLoading, navigate]); // Removed getToken from dependencies

  // Auto-redirect to login if there's an error (and log out first)
  useEffect(() => {
    if (error && !isLoading) {
      handleLogout();
    }
  }, [error, isLoading]);

  // Non-authenticated state - auto redirect after a short delay
  useEffect(() => {
    if (!isAuthenticated && !isLoading && !error) {
      const timer = setTimeout(() => navigate('/login'), 1000);
      return () => clearTimeout(timer);
    }
  }, [isAuthenticated, isLoading, error, navigate]);

  // Loading state is the only visible UI for normal flow
  return (
    <div className="flex h-screen w-full items-center justify-center bg-background">
      <div className="flex flex-col items-center justify-center space-y-4">
        <Loader2 className="h-10 w-10 animate-spin text-primary" />
        {organizationName ? (
          <p className="text-muted-foreground">
            Finalizing your membership for {organizationName}...
          </p>
        ) : (
          <p className="text-muted-foreground">Finalizing authentication...</p>
        )}
      </div>
    </div>
  );
};

export default Callback;
