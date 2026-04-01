import { useQuery } from '@tanstack/react-query';
import { useCollectionCountQueryOptions } from '../api';
import { Badge } from '@/shared/ui/badge';
import { Skeleton } from '@/shared/ui/skeleton';

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

  return (
    <Badge
      variant="secondary"
      className="text-[0.625rem] text-muted-foreground"
    >
      {collectionCount}
    </Badge>
  );
}

function CollectionCountSkeleton() {
  return <Skeleton className="h-5 w-8 rounded-4xl" />;
}
