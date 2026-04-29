import { cn } from '@/shared/tailwind/cn';

type OrganizationIconProps = {
  className?: string;
  name: string;
};

function OrganizationIcon({ className, name }: OrganizationIconProps) {
  return (
    <span
      className={cn(
        'flex size-5 shrink-0 items-center justify-center rounded-xs bg-orange-600 text-sm font-semibold text-sidebar-foreground',
        className,
      )}
    >
      {name.trim().charAt(0).toUpperCase() || '?'}
    </span>
  );
}

export { OrganizationIcon };
