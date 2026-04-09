import { CollectionTooltipContent } from './collection-tooltip-content';
import type { SourceConnectionSummary } from '@/shared/api';
import { getAppIconUrl } from '@/shared/icons/get-app-icon-url';
import { cn } from '@/shared/tailwind/cn';
import { Skeleton } from '@/shared/ui/skeleton';
import { Tooltip, TooltipTrigger } from '@/shared/ui/tooltip';

const MAX_SOURCE_CONNECTIONS_ICONS = 3;

export function CollectionSourceConnections({
  sourceConnections,
  size,
}: {
  sourceConnections: Array<SourceConnectionSummary>;
  size?: CollectionSourceConnectionIconProps['size'];
}) {
  const sourceConnectionCount = sourceConnections.length;
  if (!sourceConnectionCount) {
    return null;
  }

  return (
    <Tooltip>
      <TooltipTrigger
        className={cn(
          'flex min-w-26 items-center gap-1.5',
          size === 'sm' && 'min-w-20',
        )}
      >
        <div
          className={cn(
            'flex flex-1 -space-x-3',
            size === 'sm' && '-space-x-2.5',
          )}
        >
          {sourceConnections
            .slice(0, MAX_SOURCE_CONNECTIONS_ICONS)
            .map((source, index) => (
              <CollectionSourceConnectionIcon
                key={`${source.name}:${index}`}
                shortName={source.short_name}
                size={size}
                style={{ zIndex: sourceConnectionCount - index }}
              />
            ))}
        </div>
        {sourceConnectionCount > MAX_SOURCE_CONNECTIONS_ICONS && (
          <p className="ms-0 font-mono text-xs text-muted-foreground">
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

type CollectionSourceConnectionIconProps = React.ComponentProps<'div'> & {
  size?: 'default' | 'sm';
  shortName: string;
};

function CollectionSourceConnectionIcon({
  size = 'default',
  shortName,
  ...props
}: CollectionSourceConnectionIconProps) {
  const sourceIconSrc = getAppIconUrl(shortName);

  return (
    <div className={cn('relative')} {...props}>
      <div
        className={cn(
          'flex size-8 items-center justify-center rounded-md border border-[#1f1f1f] bg-[#353535] p-1.5',
          size === 'sm' && 'size-6 p-1',
        )}
      >
        {sourceIconSrc ? (
          <img
            alt=""
            aria-hidden="true"
            className={cn('size-4.5', size === 'sm' && 'size-3')}
            src={sourceIconSrc}
          />
        ) : (
          <span>{shortName.charAt(0).toUpperCase()}</span>
        )}
      </div>
    </div>
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
