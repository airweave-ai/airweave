import { mockCollections } from '@/features/collections/model/mock-collections';
import { Card, CardContent, CardHeader, CardTitle } from '@/shared/ui/card';

const statusStyles = {
  Draft: 'bg-muted text-muted-foreground',
  Paused: 'bg-amber-500/10 text-amber-700 dark:text-amber-300',
  Synced: 'bg-emerald-500/10 text-emerald-700 dark:text-emerald-300',
} as const;

export function CollectionsTable() {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Active collections</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        {mockCollections.map((collection) => (
          <div
            key={collection.id}
            className="flex flex-col gap-3 rounded-xl border p-4 md:flex-row md:items-center md:justify-between"
          >
            <div>
              <p className="font-medium">{collection.name}</p>
              <p className="text-sm text-muted-foreground">
                {collection.sourceCount} source{collection.sourceCount === 1 ? '' : 's'} connected
              </p>
            </div>
            <div className="flex items-center gap-3 text-sm">
              <span className="text-muted-foreground">{collection.updatedAt}</span>
              <span className={`rounded-full px-2.5 py-1 text-xs font-medium ${statusStyles[collection.status]}`}>
                {collection.status}
              </span>
            </div>
          </div>
        ))}
      </CardContent>
    </Card>
  );
}
