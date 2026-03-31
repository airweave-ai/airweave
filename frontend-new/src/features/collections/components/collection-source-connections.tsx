import type { SourceConnectionSummary } from '@/shared/api';
import { getAppIconUrl } from '@/shared/icons/get-app-icon-url';
import { cn } from '@/shared/tailwind/cn';
import { Separator } from '@/shared/ui/separator';
import { Skeleton } from '@/shared/ui/skeleton';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/shared/ui/tooltip';

const MAX_SOURCE_CONNECTIONS_ICONS = 3;

export function CollectionSourceConnections({
  sourceConnections,
}: {
  sourceConnections: SourceConnectionSummary[];
}) {
  const sourceConnectionCount = sourceConnections.length;
  if (!sourceConnectionCount) {
    return null;
  }

  return (
    <Tooltip>
      <TooltipTrigger className="flex items-center gap-1.5 pl-3">
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
                <div className="flex size-8 items-center justify-center rounded-md border border-[#1f1f1f] bg-[#353535] p-1.5">
                  <img
                    alt=""
                    aria-hidden="true"
                    className="size-4.5"
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
      <TooltipContent
        sideOffset={8}
        className="flex max-w-50 flex-col border bg-secondary px-3 py-1.5 text-foreground [&_svg]:hidden!"
      >
        <p>
          {sourceConnections.length} Connection
          {sourceConnections.length > 1 && 's'}
        </p>
        <Separator className="w-full" />
        <p className="text-center text-muted-foreground">
          {sourceConnections.map((source) => source.name).join(', ')}
        </p>
      </TooltipContent>
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
