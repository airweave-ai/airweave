import type { PropsWithChildren, ReactNode } from 'react';
import { cn } from '@/shared/tailwind/cn';

type PageShellProps = PropsWithChildren<{
  actions?: ReactNode;
  description?: string;
  title: string;
  className?: string;
}>;

export function PageShell({
  actions,
  children,
  className,
  description,
  title,
}: PageShellProps) {
  return (
    <section className={cn('space-y-6', className)}>
      <header className="flex flex-col gap-4 rounded-2xl border bg-card p-6 md:flex-row md:items-end md:justify-between">
        <div className="space-y-1">
          <p className="text-sm font-medium tracking-[0.2em] text-muted-foreground uppercase">
            Workspace
          </p>
          <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
          {description ? (
            <p className="text-sm text-muted-foreground">{description}</p>
          ) : null}
        </div>
        {actions ? (
          <div className="flex items-center gap-3">{actions}</div>
        ) : null}
      </header>
      {children}
    </section>
  );
}
