import { useSuspenseQueries } from '@tanstack/react-query';
import { Link } from '@tanstack/react-router';
import { EllipsisVertical } from 'lucide-react';
import type { Collection, SourceConnection } from '@/shared/api';
import {
  CollectionSourceConnections,
  CollectionStatusBadge,
  useGetCollectionQueryOptions,
} from '@/features/collections';
import { useListSourceConnectionsQueryOptions } from '@/features/source-connections';
import { SourceIconTile } from '@/shared/components/source-icon-tile';
import { Button } from '@/shared/ui/button';

export function CollectionDetailPage({
  collectionId,
}: {
  collectionId: string;
}) {
  const collectionQueryOptions = useGetCollectionQueryOptions({ collectionId });
  const sourceConnectionsQueryOptions = useListSourceConnectionsQueryOptions({
    collectionId,
  });
  const [{ data: collection }, { data: sourceConnections }] =
    useSuspenseQueries({
      queries: [collectionQueryOptions, sourceConnectionsQueryOptions],
    });
  const hasSourceConnections = sourceConnections.length > 0;

  return (
    <section className="space-y-4">
      <CollectionDetailHeader
        collection={collection}
        primarySource={sourceConnections[0]}
      />

      <div className="px-4">
        <div className="rounded-sm border border-border bg-foreground/5 p-5">
          {hasSourceConnections ? (
            <div className="space-y-4">
              <div className="space-y-2">
                <p className="text-sm font-medium text-foreground">Sources</p>
                <div className="flex flex-wrap items-center gap-3">
                  <CollectionSourceConnections
                    sourceConnections={sourceConnections}
                  />
                  <p className="text-sm text-muted-foreground">
                    {sourceConnections.length} source connection
                    {sourceConnections.length === 1 ? '' : 's'}
                  </p>
                </div>
              </div>

              <div>
                <Button asChild variant="outline">
                  <Link
                    params={{ collectionId: collection.readable_id }}
                    to="/collections/$collectionId/connect-source"
                  >
                    Add Source
                  </Link>
                </Button>
              </div>
            </div>
          ) : (
            <div className="space-y-3">
              <p className="text-sm text-muted-foreground">
                This collection does not have any source connections yet.
              </p>

              <div>
                <Button asChild>
                  <Link
                    params={{ collectionId: collection.readable_id }}
                    to="/collections/$collectionId/connect-source"
                  >
                    Connect Source
                  </Link>
                </Button>
              </div>
            </div>
          )}
        </div>
      </div>
    </section>
  );
}

function CollectionDetailHeader({
  collection,
  primarySource,
}: {
  collection: Collection;
  primarySource: Pick<SourceConnection, 'name' | 'short_name'> | undefined;
}) {
  const identifier = collection.readable_id || collection.id;

  return (
    <header className="flex flex-col gap-3 p-4 sm:flex-row sm:items-center sm:justify-between">
      <div className="flex min-w-0 items-center gap-3">
        <SourceIconTile
          name={primarySource?.name ?? collection.name}
          shortName={primarySource?.short_name}
        />

        <div className="min-w-0 space-y-0.5">
          <div className="flex flex-wrap items-center gap-2">
            <h1 className="font-heading text-xl font-semibold text-foreground">
              {collection.name}
            </h1>
            {collection.status ? (
              <CollectionStatusBadge status={collection.status} />
            ) : null}
          </div>

          <p className="truncate font-mono text-sm text-muted-foreground">
            {identifier}
          </p>
        </div>
      </div>

      <div className="flex items-center justify-end gap-2 sm:shrink-0">
        <Button className="border-0 font-mono" type="button" variant="outline">
          Memory
        </Button>
        <Button
          aria-label="More collection actions"
          size="icon-lg"
          type="button"
          variant="ghost"
        >
          <EllipsisVertical className="size-4" />
        </Button>
      </div>
    </header>
  );
}
