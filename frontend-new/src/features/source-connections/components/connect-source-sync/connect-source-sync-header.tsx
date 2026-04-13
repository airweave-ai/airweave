import { IconAlertCircleFilled, IconCheck } from '@tabler/icons-react';
import { SourceConnectionHeader } from '../source-connection-header';
import type { Source } from '@/shared/api';
import { Badge } from '@/shared/ui/badge';
import { cn } from '@/shared/tailwind/cn';

type ConnectSourceSyncHeaderVariant = 'active' | 'completed' | 'error';

interface ConnectSourceSyncHeaderProps {
  source: Pick<Source, 'name' | 'short_name'>;
  variant: ConnectSourceSyncHeaderVariant;
}

const badgeVariantLabels: Record<ConnectSourceSyncHeaderVariant, string> = {
  active: 'Active',
  completed: 'Completed',
  error: 'Error',
};

export function ConnectSourceSyncHeader({
  source,
  variant,
}: ConnectSourceSyncHeaderProps) {
  const isError = variant === 'error';

  return (
    <SourceConnectionHeader
      source={source}
      title={
        <>
          <span>
            {source.name} {isError ? 'Not Connected' : 'Connected'}
          </span>
          {isError ? (
            <IconAlertCircleFilled className="size-5 text-destructive" />
          ) : (
            <IconCheck className="size-4 text-green-400" />
          )}
        </>
      }
      aside={
        <Badge
          variant="outline"
          className={cn('border border-foreground/10 font-mono', {
            'bg-green-400/25': !isError,
            'bg-red-400/50': isError,
          })}
        >
          <span
            aria-hidden="true"
            className={cn('size-1.5 rounded-full border border-foreground/10', {
              'bg-green-400': !isError,
              'bg-red-400': isError,
            })}
          />
          {badgeVariantLabels[variant]}
        </Badge>
      }
    />
  );
}
