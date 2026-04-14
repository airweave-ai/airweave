import { IconCheck } from '@tabler/icons-react';
import { Spinner } from '@/shared/ui/spinner';
import { cn } from '@/shared/tailwind/cn';

interface ConnectSourceSyncStatusCardProps {
  completed?: boolean;
  progress?: number;
  showProgressBar?: boolean;
  subtitle: string;
  title: string;
}

export function ConnectSourceSyncStatusCard({
  completed = false,
  progress = 0,
  showProgressBar = true,
  subtitle,
  title,
}: ConnectSourceSyncStatusCardProps) {
  const normalizedProgress = completed
    ? 1
    : Math.max(0, Math.min(progress, 0.95));

  return (
    <div className="space-y-4 rounded-md border border-border bg-background p-4">
      <div className="flex items-start gap-4">
        <div className="flex size-8 shrink-0 items-center justify-center rounded-sm border border-border bg-muted">
          {completed ? (
            <IconCheck className="size-4 text-foreground" />
          ) : (
            <Spinner className="size-4 text-foreground" />
          )}
        </div>

        <div className="min-w-0 flex-1 space-y-1">
          <p className="text-sm font-medium text-foreground">{title}</p>
          <p className="font-mono text-sm text-muted-foreground">{subtitle}</p>
        </div>
      </div>

      {showProgressBar ? (
        <div className="h-1 overflow-hidden rounded-full bg-primary/20">
          <div
            className={cn(
              'h-full w-full rounded-full bg-foreground transition-transform duration-500 ease-[cubic-bezier(0.215,0.61,0.355,1)] motion-reduce:transition-none',
            )}
            style={{
              transform: `scaleX(${normalizedProgress})`,
              transformOrigin: 'left center',
            }}
            aria-hidden="true"
          />
        </div>
      ) : null}
    </div>
  );
}
