import type { ReactNode } from 'react';
import { Card, CardContent } from '@/shared/ui/card';

export function CollectionSearchStatusCard({
  children,
  description,
  icon,
  title,
}: {
  children?: ReactNode;
  description: ReactNode;
  icon: ReactNode;
  title: ReactNode;
}) {
  return (
    <Card size="sm" className="rounded-sm bg-foreground/5 shadow-none ring-0">
      <CardContent className="space-y-4 px-4 group-data-[size=sm]/card:px-4">
        <div className="flex items-center gap-2">
          <div className="flex size-8 shrink-0 items-center justify-center rounded-sm border border-border bg-muted">
            {icon}
          </div>

          <div className="min-w-0">
            <p className="text-sm font-medium text-foreground">{title}</p>
            <p className="font-mono text-xs text-muted-foreground">
              {description}
            </p>
          </div>
        </div>

        {children}
      </CardContent>
    </Card>
  );
}
