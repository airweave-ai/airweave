import * as React from 'react';
import { useSuspenseQueries } from '@tanstack/react-query';
import { CollectionDetailHeader } from './components/collection-detail-header';
import { CollectionDetailTabsCard } from './components/collection-detail-tabs-card';
import {
  CollectionCodeSnippetAside,
  CollectionSearch,
  useCollectionSearchWorkspace,
  useGetCollectionQueryOptions,
} from '@/features/collections';
import { useListSourceConnectionsQueryOptions } from '@/features/source-connections';
import { cn } from '@/shared/tailwind/cn';

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
  const { form, tiers } = useCollectionSearchWorkspace({ collectionId });
  const [isSnippetAsideCollapsed, setIsSnippetAsideCollapsed] =
    React.useState(false);

  return (
    <section
      className={cn(
        'grid min-h-full lg:h-full lg:min-h-0 lg:grid-cols-[minmax(0,1fr)_24rem] lg:grid-rows-[minmax(0,1fr)] lg:items-stretch lg:overflow-hidden',
        isSnippetAsideCollapsed && 'lg:grid-cols-[minmax(0,1fr)_2.75rem]',
      )}
    >
      <div className="min-w-0 space-y-4 px-4 pb-4 lg:min-h-0 lg:overflow-y-auto">
        <CollectionDetailHeader
          collection={collection}
          primarySource={sourceConnections[0]}
        />

        <CollectionSearch
          disabled={!hasSourceConnections}
          form={form}
          tiers={tiers}
        />

        <CollectionDetailTabsCard
          collectionId={collection.readable_id}
          sourceConnections={sourceConnections}
        />
      </div>

      <CollectionCodeSnippetAside
        collapsed={isSnippetAsideCollapsed}
        collectionId={collection.readable_id}
        form={form}
        onCollapseToggle={() =>
          setIsSnippetAsideCollapsed((current) => !current)
        }
      />
    </section>
  );
}
