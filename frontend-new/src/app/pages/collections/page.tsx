import { useQuery } from '@tanstack/react-query';
import { CollectionsTable } from '@/features/collections';
import { useListCollectionsQueryOptions } from '@/features/collections/api';

export function CollectionsPage() {
  const collectionsQueryOptions = useListCollectionsQueryOptions();
  const {
    data: collections,
    error,
    isLoading,
  } = useQuery(collectionsQueryOptions);

  const emptyMessage = isLoading
    ? 'Loading collections...'
    : error
      ? 'Failed to load collections.'
      : 'No collections found.';

  return (
    <section className="space-y-4 px-13 py-1">
      <div className="space-y-1">
        <h1 className="font-heading text-lg font-semibold text-foreground">
          Collections
        </h1>
        <p className="text-sm text-muted-foreground">
          Browse your collections and basic metadata.
        </p>
      </div>

      <CollectionsTable
        collections={collections ?? []}
        emptyMessage={emptyMessage}
      />
    </section>
  );
}
