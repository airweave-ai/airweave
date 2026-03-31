import { Card, CardContent } from '@/shared/ui/card';
import { Skeleton } from '@/shared/ui/skeleton';

export function ApiKeyDashboardCard() {
  return (
    <Card className="gap-0 bg-card/95 py-4 ring-1 ring-border/80">
      <CardContent className="space-y-4">
        <div className="flex items-center justify-between gap-3">
          <h2 className="font-heading text-base font-semibold text-foreground">
            Get Airweave API Key
          </h2>
          <span className="text-xs font-medium text-muted-foreground">
            See all API keys
          </span>
        </div>

        <div className="rounded-sm border border-dashed border-border/70 bg-background/30 px-3 py-3 text-sm text-muted-foreground">
          No API key available
        </div>
      </CardContent>
    </Card>
  );
}

export function ApiKeyDashboardCardSkeleton() {
  return (
    <Card className="gap-0 bg-card/95 py-4 ring-1 ring-border/80">
      <CardContent className="space-y-4">
        <div className="flex items-center justify-between gap-3">
          <h2 className="font-heading text-base font-semibold text-foreground">
            Get Airweave API Key
          </h2>
          <span className="text-xs font-medium text-muted-foreground">
            See all API keys
          </span>
        </div>

        <div className="space-y-2">
          <Skeleton className="h-9 rounded-sm bg-muted/60" />
          <Skeleton className="h-9 rounded-sm bg-muted/40" />
        </div>
      </CardContent>
    </Card>
  );
}
