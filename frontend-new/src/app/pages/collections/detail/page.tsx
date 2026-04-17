import { useSuspenseQueries } from '@tanstack/react-query';
import { CollectionDetailHeader } from './components/collection-detail-header';
import { CollectionDetailTabsCard } from './components/collection-detail-tabs-card';
import {
  CollectionSearch,
  useGetCollectionQueryOptions,
} from '@/features/collections';
import { useListSourceConnectionsQueryOptions } from '@/features/source-connections';

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
    <section className="space-y-4 px-4">
      <CollectionDetailHeader
        collection={collection}
        primarySource={sourceConnections[0]}
      />

      <CollectionSearch
        collectionId={collectionId}
        disabled={!hasSourceConnections}
      />

      <CollectionDetailTabsCard
        collectionId={collection.readable_id}
        sourceConnections={sourceConnections}
      />
    </section>
  );
}
