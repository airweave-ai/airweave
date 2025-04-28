import { useAuth0 } from '@auth0/auth0-react';
import { LogOut } from 'lucide-react';
import { apiClient } from '@/lib/api';

export function LogoutButton() {
  const { logout } = useAuth0();

  const handleLogout = () => {
    // Clear token from localStorage
    apiClient.clearToken();

    logout({
      logoutParams: {
        returnTo: window.location.origin
      }
    });
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
