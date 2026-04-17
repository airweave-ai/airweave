import { IconDotsVertical } from '@tabler/icons-react';
import type { Collection, SourceConnection } from '@/shared/api';
import { CollectionStatusBadge } from '@/features/collections';
import { SourceIconTile } from '@/shared/components/source-icon-tile';
import { Button } from '@/shared/ui/button';

export function CollectionDetailHeader({
  collection,
  primarySource,
}: {
  collection: Collection;
  primarySource: Pick<SourceConnection, 'name' | 'short_name'> | undefined;
}) {
  const identifier = collection.readable_id || collection.id;

  return (
    <header className="flex flex-col gap-3 py-4 sm:flex-row sm:items-center sm:justify-between">
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
          <IconDotsVertical className="size-4" />
        </Button>
      </div>
    </header>
  );
}
