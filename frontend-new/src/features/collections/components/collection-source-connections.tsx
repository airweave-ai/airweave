import { CollectionTooltipContent } from './collection-tooltip-content';
import type { SourceConnectionSummary } from '@/shared/api';
import { getAppIconUrl } from '@/shared/icons/get-app-icon-url';
import { cn } from '@/shared/tailwind/cn';
import { Skeleton } from '@/shared/ui/skeleton';
import { Tooltip, TooltipTrigger } from '@/shared/ui/tooltip';

const MAX_SOURCE_CONNECTIONS_ICONS = 3;

export function CollectionSourceConnections({
  sourceConnections,
  size = 'default',
}: {
  sourceConnections: Array<SourceConnectionSummary>;
  size?: 'default' | 'lg';
}) {
  const sourceConnectionCount = sourceConnections.length;
  if (!sourceConnectionCount) {
    return null;
  }

  return (
    <Tooltip>
      <TooltipTrigger className="flex w-28 items-center gap-1.5">
        {sourceConnections
          .slice(0, MAX_SOURCE_CONNECTIONS_ICONS)
          .map((source, index) => {
            const sourceLogoSrc = getAppIconUrl(source.short_name);

            return (
              <div
                key={source.short_name}
                className={cn('relative', index > 0 && '-ml-3')}
                style={{ zIndex: sourceConnectionCount - index }}
              >
                <div
                  className={cn(
                    'flex size-6 items-center justify-center rounded-md border border-[#1f1f1f] bg-[#353535] p-1',
                    size === 'lg' && 'size-8 p-1.5',
                  )}
                >
                  <img
                    alt=""
                    aria-hidden="true"
                    className={cn('size-3', size === 'lg' && 'size-4.5')}
                    src={sourceLogoSrc}
                  />
                </div>
              </div>
            );
          })}
        {sourceConnectionCount > MAX_SOURCE_CONNECTIONS_ICONS && (
          <p className="font-mono text-xs text-muted-foreground">
            +{sourceConnectionCount - MAX_SOURCE_CONNECTIONS_ICONS}
          </p>
        )}
      </TooltipTrigger>
      <CollectionTooltipContent
        sideOffset={8}
        description={sourceConnections.map((source) => source.name).join(', ')}
        title={
          <>
            {sourceConnections.length} Connection
            {sourceConnections.length > 1 && 's'}
          </>
        }
      />
    </Tooltip>
  );
}

export function CollectionSourceConnectionsSkeleton() {
  return (
    <div className="flex items-center pl-3">
      {Array.from({ length: 3 }).map((_, sourceIndex) => (
        <Skeleton
          key={sourceIndex}
          className={cn(
            'size-8 rounded-md border border-[#1f1f1f] bg-[#353535]',
            sourceIndex > 0 && '-ml-3',
          )}
          style={{ zIndex: 3 - sourceIndex }}
        />
      ))}
    </div>
  );
}
