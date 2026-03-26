import { FolderKanban, Layers3 } from 'lucide-react';
import { mockCollections } from '@/features/collections/model/mock-collections';
import { Card, CardContent, CardHeader, CardTitle } from '@/shared/ui/card';

export function CollectionsSummaryCard() {
  const syncedCollections = mockCollections.filter((collection) => collection.status === 'Synced');
  const totalSources = mockCollections.reduce((sum, collection) => sum + collection.sourceCount, 0);

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-3">
        <CardTitle>Collections</CardTitle>
        <FolderKanban className="size-4 text-muted-foreground" />
      </CardHeader>
      <CardContent className="space-y-4">
        <div>
          <p className="text-3xl font-semibold tracking-tight">{mockCollections.length}</p>
          <p className="text-sm text-muted-foreground">
            {syncedCollections.length} synced and searchable now.
          </p>
        </div>
        <div className="flex items-center justify-between rounded-xl border bg-muted/30 px-4 py-3 text-sm">
          <span className="text-muted-foreground">Connected sources</span>
          <span className="inline-flex items-center gap-2 font-medium text-foreground">
            <Layers3 className="size-4" />
            {totalSources}
          </span>
        </div>
      </CardContent>
    </Card>
  );
}
