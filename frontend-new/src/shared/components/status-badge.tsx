import * as React from 'react';
import { cva } from 'class-variance-authority';
import { Badge } from '../ui/badge';
import { cn } from '../tailwind/cn';
import type { VariantProps } from 'class-variance-authority';

const statusBadgeVariants = cva(
  'h-auto rounded-full border-[0.5px] px-2 py-0.5 font-mono text-xs font-normal',
  {
    variants: {
      variant: {
        success:
          'border-[rgba(215,248,227,0.1)] bg-[linear-gradient(155deg,rgba(74,222,128,0.5)_12.564%,rgba(74,222,128,0.35)_21.591%,rgba(40,120,69,0.024)_69.459%)] text-green-100 [&>[data-slot=status-badge-indicator]]:bg-green-200',
        info: 'border-[rgba(56,189,248,0.10)] bg-[linear-gradient(117deg,rgba(56,189,248,0.50)_12.56%,rgba(56,189,248,0.35)_21.59%,rgba(56,189,248,0.03)_69.46%)] text-sky-100 [&>[data-slot=status-badge-indicator]]:bg-sky-200',
        destructive:
          'border-[rgba(215,248,227,0.10)] bg-[linear-gradient(117deg,rgba(248,113,113,0.50)_12.56%,rgba(248,113,113,0.35)_21.59%,rgba(248,113,113,0.03)_69.46%)] text-red-100 [&>[data-slot=status-badge-indicator]]:bg-red-200',
      },
    },
    defaultVariants: {
      variant: 'info',
    },
  },
);

export function StatusBadge({
  children,
  variant = 'info',
  className,
  ...props
}: Omit<React.ComponentProps<typeof Badge>, 'variant'> &
  VariantProps<typeof statusBadgeVariants>) {
  return (
    <Badge
      variant="outline"
      className={statusBadgeVariants({ variant, className })}
      {...props}
    >
      {children}
    </Badge>
  );
}

export function StatusBadgeIndicator({
  className,
  ...props
}: React.ComponentProps<'span'>) {
  return (
    <span
      aria-hidden="true"
      data-slot="status-badge-indicator"
      className={cn('size-1.5 rounded-full', className)}
      {...props}
    />
  );
}
