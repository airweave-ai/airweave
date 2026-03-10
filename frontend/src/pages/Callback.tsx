import { useAuth0 } from '@auth0/auth0-react';
import { useEffect, useRef, useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { Loader2, Mail } from 'lucide-react';
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
  const syncAttempted = useRef(false);
  const [emailVerificationRequired, setEmailVerificationRequired] = useState(false);

  const isLoading = auth0Loading || authContextLoading;

  const handleLogout = () => {
    logout();
  };

  // Create or update user in backend when authenticated
  useEffect(() => {
    const syncUser = async () => {
      if (isAuthenticated && user && !isLoading && !syncAttempted.current) {
        syncAttempted.current = true;

        try {
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
  }, [isAuthenticated, user, isLoading, navigate]);

  // Handle errors — detect email verification requirement
  useEffect(() => {
    if (error && !isLoading) {
      const errorObj = error as any;
      const fullMessage = [
        errorObj?.error_description,
        errorObj?.message,
        error.toString(),
      ].join(' ').toLowerCase();

      if (fullMessage.includes('verify') && fullMessage.includes('email')) {
        setEmailVerificationRequired(true);
        return;
      }
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

  if (emailVerificationRequired) {
    return (
      <div className="flex h-screen w-full items-center justify-center bg-background">
        <div className="max-w-md w-full mx-4 p-8 bg-card border border-border rounded-lg shadow-lg text-center">
          <div className="mx-auto mb-6 flex h-16 w-16 items-center justify-center rounded-full bg-primary/10">
            <Mail className="h-8 w-8 text-primary" />
          </div>

          <h1 className="text-xl font-semibold text-foreground mb-2">
            Check your email
          </h1>

          <p className="text-muted-foreground mb-6">
            We sent a verification link to your email address.
            Please click the link to verify your account, then sign in again.
          </p>

          <button
            onClick={handleLogout}
            className="w-full bg-primary text-primary-foreground px-4 py-2.5 rounded-md hover:bg-primary/90 transition-colors font-medium"
          >
            Back to sign in
          </button>
        </div>
      </div>
    );
  }

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
