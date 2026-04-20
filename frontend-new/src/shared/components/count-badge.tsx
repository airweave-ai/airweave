import * as React from 'react';
import { Badge } from '../ui/badge';
import { cn } from '../tailwind/cn';

type CountBadgeProps = Omit<React.ComponentProps<typeof Badge>, 'variant'>;

export function CountBadge({ className, children, ...props }: CountBadgeProps) {
  return (
    <Badge
      variant="secondary"
      className={cn('text-[0.625rem] text-muted-foreground', className)}
      {...props}
    >
      {children}
    </Badge>
  );
}
