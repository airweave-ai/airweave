import type { ReactNode } from 'react';
import { cn } from '@/shared/tailwind/cn';

type ProvidersListEmptyStateProps = {
  message: ReactNode;
  className?: string;
};

export function ProvidersListEmptyState({
  message,
  className,
}: ProvidersListEmptyStateProps) {
  return (
    <div
      className={cn(
        'flex min-h-14 items-center justify-center rounded-sm border border-dashed border-input px-3 py-4',
        className,
      )}
    >
      <p className="text-center font-mono text-sm text-muted-foreground">
        {message}
      </p>
    </div>
  );
}
