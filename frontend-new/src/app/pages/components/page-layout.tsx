import type { ReactNode } from 'react';
import { cn } from '@/shared/tailwind/cn';

export function PageLayout({
  className,
  ...props
}: React.ComponentProps<'section'>) {
  return (
    <section
      className={cn('flex min-h-full flex-1 flex-col px-16 py-4', className)}
      {...props}
    />
  );
}

export type PageHeaderProps = {
  title: ReactNode;
  description?: ReactNode;
  badge?: ReactNode;
  actions?: ReactNode;
  className?: string;
};

export function PageHeader({
  title,
  description,
  badge,
  actions,
  className,
}: PageHeaderProps) {
  return (
    <div
      className={cn(
        'flex flex-col gap-3 xl:flex-row xl:items-center xl:justify-between',
        className,
      )}
    >
      <div className="min-w-0">
        <div className="flex items-center gap-1">
          <h1 className="font-heading text-lg font-semibold text-foreground">
            {title}
          </h1>
          {badge}
        </div>

        {description ? (
          <p className="mt-1 font-mono text-sm text-muted-foreground">
            {description}
          </p>
        ) : null}
      </div>

      {actions ? (
        <div className="flex flex-wrap items-center gap-2">{actions}</div>
      ) : null}
    </div>
  );
}
