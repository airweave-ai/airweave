import { useQuery } from '@tanstack/react-query';
import { useCollectionCountQueryOptions } from '../api';
import { Skeleton } from '@/shared/ui/skeleton';
import { CountBadge } from '@/shared/components/count-badge';

export function CollectionCountBadge() {
  const collectionCountQueryOptions = useCollectionCountQueryOptions();
  const {
    data: collectionCount,
    isPending,
    isError,
  } = useQuery(collectionCountQueryOptions);

  if (isPending) {
    return <CollectionCountSkeleton />;
  }

  if (isError) {
    return null;
  }

  return <CountBadge>{collectionCount}</CountBadge>;
}

function CollectionCountSkeleton() {
  return <Skeleton className="h-5 w-8 rounded-4xl" />;
}
