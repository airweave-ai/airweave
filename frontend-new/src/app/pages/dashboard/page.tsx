import { Plus } from 'lucide-react';
import { CreateCollectionButton } from '@/app/components/create-collection-button';
import { ApiKeyDashboardCard } from '@/features/api-keys';
import { CollectionsSummaryCard } from '@/features/collections';

export function DashboardPage() {
  return (
    <section className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_24rem] xl:items-start">
      <CollectionsSummaryCard
        createCollectionAction={
          <CreateCollectionButton size="lg">
            <Plus />
            Create Collection
          </CreateCollectionButton>
        }
      />

      <div className="xl:sticky xl:top-0">
        <ApiKeyDashboardCard />
      </div>
    </section>
  );
}
