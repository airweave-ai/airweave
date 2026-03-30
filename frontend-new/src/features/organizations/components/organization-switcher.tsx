import { ChevronDown } from 'lucide-react';
import type { OrganizationWithRole } from '@/shared/api';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuTrigger,
} from '@/shared/ui/dropdown-menu';
import { LogoMark } from '@/shared/ui/logo-mark';
import { SidebarMenuButton } from '@/shared/ui/sidebar';

interface OrganizationSwitcherProps {
  currentOrganizationId: string;
  currentOrganizationName: string;
  onCurrentOrganizationChange: (organizationId: string) => void;
  organizations: Array<OrganizationWithRole>;
}

export function OrganizationSwitcher({
  currentOrganizationId,
  currentOrganizationName,
  onCurrentOrganizationChange,
  organizations,
}: OrganizationSwitcherProps) {
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <SidebarMenuButton
          className="w-full min-w-0 gap-2 font-semibold data-open:[&_svg]:rotate-180"
          type="button"
        >
          <LogoMark />
          <span className="min-w-0 flex-1 truncate">
            {currentOrganizationName}
          </span>
          <ChevronDown className="size-4 shrink-0 text-sidebar-foreground/50 transition-[rotate]" />
        </SidebarMenuButton>
      </DropdownMenuTrigger>
      <DropdownMenuContent className="min-w-79 rounded-sm">
        <DropdownMenuLabel className="px-2 py-1.5 font-mono uppercase">
          Organizations
        </DropdownMenuLabel>
        {organizations.length > 0 ? (
          <DropdownMenuRadioGroup
            onValueChange={onCurrentOrganizationChange}
            value={currentOrganizationId}
          >
            {organizations.map((organization) => (
              <DropdownMenuRadioItem
                key={organization.id}
                className="gap-2 rounded-xs p-2"
                value={organization.id}
              >
                <LogoMark />
                {organization.name}
              </DropdownMenuRadioItem>
            ))}
          </DropdownMenuRadioGroup>
        ) : (
          <DropdownMenuItem
            className="rounded-xs p-2 text-muted-foreground"
            disabled
          >
            No organizations yet
          </DropdownMenuItem>
        )}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
