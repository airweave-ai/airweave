import { useState, useEffect } from 'react';
import { useAuth } from '@/lib/auth-context';
import { Link } from 'react-router-dom';
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuSeparator, DropdownMenuTrigger } from '@/components/ui/dropdown-menu';
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar';
import { ExternalLink, MoreVertical } from 'lucide-react';
import { apiClient } from '@/lib/api';

export function UserProfileDropdown() {
  const { user, logout } = useAuth();
  const [firstName, setFirstName] = useState<string>('');
  const [lastName, setLastName] = useState<string>('');

  useEffect(() => {
    if (user?.name) {
      const nameParts = user.name.split(' ');
      setFirstName(nameParts[0] || '');
      setLastName(nameParts.slice(1).join(' ') || '');
    }
  }, [user]);

  const handleLogout = () => {
    apiClient.clearToken();
    logout();
  };

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button className="flex items-center justify-between px-1 py-2  text-sm font-medium rounded-md text-muted-foreground hover:bg-accent hover:text-accent-foreground transition-all duration-200 ease-in-out w-full">
          <div className="flex items-center">
            <Avatar className="h-8 w-8 mr-3">
              <AvatarImage src={user?.picture} alt={user?.name || "User"} />
              <AvatarFallback className="bg-primary/0 border  text-primary text-xs">
                {firstName
                  ? firstName[0]
                  : user?.email?.substring(0, 1).toUpperCase() || 'U'}
              </AvatarFallback>
            </Avatar>
            {user?.name || "User"}
          </div>
          <MoreVertical className="h-4 w-4 opacity-70" />
        </button>
      </DropdownMenuTrigger>

      <DropdownMenuContent className="ml-2 w-[240px] p-0 rounded-md" align="end" side="top" sideOffset={4}>
        <div className="py-2 px-3 border-b border-border/10">
          <p className="text-sm text-muted-foreground truncate">
            {user?.email}
          </p>
        </div>

        <div className="py-1">
          <DropdownMenuItem asChild>
            <a href="https://airweave.ai" target="_blank" rel="noopener noreferrer" className="flex items-center justify-between px-3 py-1.5 text-sm">
              Blog <ExternalLink className="h-3.5 w-3.5 opacity-70" />
            </a>
          </DropdownMenuItem>

          <DropdownMenuItem asChild>
            <a href="https://docs.airweave.ai" target="_blank" rel="noopener noreferrer" className="flex items-center justify-between px-3 py-1.5 text-sm">
              Documentation <ExternalLink className="h-3.5 w-3.5 opacity-70" />
            </a>
          </DropdownMenuItem>

          <DropdownMenuItem asChild>
            <a href="https://discord.gg/484HY9Ehxt" target="_blank" rel="noopener noreferrer" className="flex items-center justify-between px-3 py-1.5 text-sm">
              Join Discord community <ExternalLink className="h-3.5 w-3.5 opacity-70" />
            </a>
          </DropdownMenuItem>
        </div>

        <DropdownMenuSeparator className="opacity-10" />

        <div className="py-1">

          <DropdownMenuItem asChild>
            <Link to="/settings" className="px-3 py-1.5 text-sm">
              Account Settings
            </Link>
          </DropdownMenuItem>
        </div>

        <DropdownMenuSeparator className="opacity-10" />

        <div className="py-1">
          <DropdownMenuItem onSelect={handleLogout} className="px-3 py-1.5 text-sm text-muted-foreground">
            Sign out
          </DropdownMenuItem>
        </div>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
