import * as React from 'react';
import { cn } from '@/shared/tailwind/cn';

type StatusDotVariant = 'default' | 'destructive' | 'muted' | 'success';

const statusDotVariantClasses: Record<StatusDotVariant, string> = {
  default: 'text-foreground',
  destructive: 'text-destructive',
  muted: 'text-muted-foreground',
  success: 'text-green-400',
};

export function StatusDot({
  className,
  variant = 'default',
  ...props
}: React.ComponentProps<'span'> & {
  variant?: StatusDotVariant;
}) {
  return (
    <span
      aria-hidden="true"
      className={cn(
        'size-2 shrink-0 rounded-full bg-current shadow-[0_0_4px_currentColor]',
        statusDotVariantClasses[variant],
        className,
      )}
      {...props}
    />
  );
}
