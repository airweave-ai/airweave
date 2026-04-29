import { cn } from '@/shared/tailwind/cn';
import { Badge } from '@/shared/ui/badge';

type OrganizationRoleBadgeProps = {
  role: string;
};

function OrganizationRoleBadge({ role }: OrganizationRoleBadgeProps) {
  const normalizedRole = role.toLowerCase();

  return (
    <Badge
      className={cn(
        'capitalize',
        normalizedRole === 'owner' && 'bg-green-700 text-secondary-foreground',
        normalizedRole === 'admin' && 'bg-blue-700 text-secondary-foreground',
      )}
      variant="secondary"
    >
      {role}
    </Badge>
  );
}

export { OrganizationRoleBadge };
