import type { PropsWithChildren, ReactNode } from 'react';
import { CountBadge } from '@/shared/components/count-badge';
import { cn } from '@/shared/tailwind/cn';

type ProvidersSectionProps = PropsWithChildren<{
  title: ReactNode;
  count: ReactNode;
  className?: string;
}>;

export function ProvidersSection({
  title,
  count,
  children,
  className,
}: ProvidersSectionProps) {
  return (
    <section className={cn('flex flex-col gap-3', className)}>
      <div className="flex items-center gap-2">
        <h2 className="text-sm font-medium text-foreground">{title}</h2>
        <CountBadge className="rounded-full border-border bg-transparent font-mono text-foreground">
          {count}
        </CountBadge>
      </div>

      {children}
    </section>
  );
}
