import type { PropsWithChildren, ReactNode } from 'react';
import { CountBadge } from '@/shared/components/count-badge';

type ProvidersSectionProps = PropsWithChildren<{
  title: ReactNode;
  count: ReactNode;
}>;

export function ProvidersSection({
  title,
  count,
  children,
}: ProvidersSectionProps) {
  return (
    <section className="flex flex-col gap-3">
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
