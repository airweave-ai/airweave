import type { ComponentProps } from 'react';
import type { OrganizationWithRole } from '@/shared/api';
import { cn } from '@/shared/tailwind/cn';
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

interface OrganizationSwitcherMenuProps extends ComponentProps<
  typeof DropdownMenuContent
> {
  currentOrganizationId: string;
  onCurrentOrganizationChange: (organizationId: string) => void;
  organizations: Array<OrganizationWithRole>;
}

function OrganizationSwitcher(props: ComponentProps<typeof DropdownMenu>) {
  return <DropdownMenu data-slot="organization-switcher" {...props} />;
}

function OrganizationSwitcherTrigger(
  props: ComponentProps<typeof DropdownMenuTrigger>,
) {
  return (
    <DropdownMenuTrigger data-slot="organization-switcher-trigger" {...props} />
  );
}

function OrganizationSwitcherMenu({
  className,
  currentOrganizationId,
  onCurrentOrganizationChange,
  organizations,
  sideOffset = 4,
  ...props
}: OrganizationSwitcherMenuProps) {
  return (
    <DropdownMenuContent
      className={cn('rounded-sm', className)}
      sideOffset={sideOffset}
      {...props}
    >
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
              className="gap-2 truncate rounded-xs p-2"
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
  );
}

export {
  OrganizationSwitcher,
  OrganizationSwitcherMenu,
  OrganizationSwitcherTrigger,
};
