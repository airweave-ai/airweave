import { useAuth0 } from '@auth0/auth0-react';
import { LogOut } from 'lucide-react';
import { apiClient } from '@/lib/api';
import { useAuth } from '@/lib/auth-context';
import authConfig from '@/config/auth';

export function LogoutButton() {
  // Use our custom auth context instead of direct Auth0 hook
  const auth = useAuth();

  const handleLogout = () => {
    // Clear token from localStorage
    apiClient.clearToken();

    // Use the logout from our auth context which handles both Auth0 and non-Auth0 cases
    auth.logout();
  };

  return (
    <button
      onClick={handleLogout}
      className="flex items-center px-3 py-2 text-sm font-medium rounded-md text-muted-foreground hover:bg-accent hover:text-accent-foreground transition-all duration-200 ease-in-out w-full"
    >
      <LogOut className="mr-3 h-5 w-5" />
      Logout
    </button>
  );
}
