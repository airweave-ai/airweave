import { useAuth0 } from '@auth0/auth0-react';
import { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Loader2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { apiClient } from '@/lib/api';
import { useAuth } from '@/lib/auth-context';

export const CallbackPage = () => {
  const { isLoading: auth0Loading, isAuthenticated, error, user } = useAuth0();
  const { getToken, isLoading: authContextLoading } = useAuth();
  const navigate = useNavigate();

  // Combine both loading states
  const isLoading = auth0Loading || authContextLoading;

  // Create or update user in backend when authenticated
  useEffect(() => {
    const syncUser = async () => {
      // Only attempt if authenticated, have user data, and not loading
      if (isAuthenticated && user && !isLoading) {
        try {
          // Token is now managed by auth context
          const token = await getToken();

          if (!token) {
            console.error("No token available for API call");
            // Still redirect to home even if token isn't available
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

          // Call backend API to create or update user
          const response = await apiClient.post('/users/create_or_update', userData);

          if (response.ok) {
            console.log("✅ User created/updated in backend");
          } else {
            const errorText = await response.text();
            console.error("❌ Failed to create/update user:", errorText);
          }

          // Redirect to home regardless of sync result
          navigate('/');
        } catch (err) {
          console.error("❌ Error syncing user with backend:", err);
          // Redirect to home even if there was an error
          navigate('/');
        }
      }
    };

    syncUser();
  }, [isAuthenticated, user, isLoading, getToken, navigate]);

  // Auto-redirect to login if there's an error
  useEffect(() => {
    if (error && !isLoading) {
      navigate('/login');
    }
  }, [error, isLoading, navigate]);

  // Non-authenticated state - auto redirect after a short delay
  useEffect(() => {
    if (!isAuthenticated && !isLoading && !error) {
      const timer = setTimeout(() => navigate('/login'), 1000);
      return () => clearTimeout(timer);
    }
  }, [isAuthenticated, isLoading, error, navigate]);

  // Loading state is the only visible UI now
  return (
    <div className="flex h-screen w-full flex-col items-center justify-center">
      <Loader2 className="h-8 w-8 animate-spin text-primary" />
      <p className="mt-4">Loading...</p>
    </div>
  );
};
