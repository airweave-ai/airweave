import { useSuspenseQuery } from '@tanstack/react-query';
import { Link } from '@tanstack/react-router';
import {
  CollectionSourceConnections,
  CollectionStatusBadge,
  useGetCollectionQueryOptions,
} from '@/features/collections';
import { Button } from '@/shared/ui/button';

export function CollectionDetailPage({
  collectionId,
}: {
  collectionId: string;
}) {
  const collectionQueryOptions = useGetCollectionQueryOptions({ collectionId });
  const { data: collection } = useSuspenseQuery(collectionQueryOptions);
  const sourceConnections = collection.source_connection_summaries ?? [];
  const hasSourceConnections = sourceConnections.length > 0;

  return (
    <section className="space-y-6 px-13 py-1">
      <div className="space-y-1">
        <div className="flex flex-wrap items-center gap-2">
          <h1 className="font-heading text-lg font-semibold text-foreground">
            {collection.name}
          </h1>
          {collection.status ? (
            <CollectionStatusBadge status={collection.status} />
          ) : null}
        </div>

        <p className="font-mono text-sm text-muted-foreground">
          {collection.readable_id}
        </p>
      </div>

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
                  to="/collections/$collectionId"
                  search={{
                    dialog: {
                      state: {
                        collectionId: collection.readable_id,
                        step: 'source',
                      },
                      type: 'connect-source',
                    },
                  }}
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
                  to="/collections/$collectionId"
                  search={{
                    dialog: {
                      state: {
                        collectionId: collection.readable_id,
                        step: 'source',
                      },
                      type: 'connect-source',
                    },
                  }}
                >
                  Connect Source
                </Link>
              </Button>
            </div>
          </div>
        )}
      </div>
    </section>
  );
}
