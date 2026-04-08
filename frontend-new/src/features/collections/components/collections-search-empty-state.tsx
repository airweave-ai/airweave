import { SearchX } from 'lucide-react';

import { Button } from '@/shared/ui/button';
import {
  Empty,
  EmptyContent,
  EmptyDescription,
  EmptyHeader,
  EmptyMedia,
  EmptyTitle,
} from '@/shared/ui/empty';

type CollectionsSearchEmptyStateProps = {
  search: string;
  onClearSearch?: () => void;
};

export function CollectionsSearchEmptyState({
  search,
  onClearSearch,
}: CollectionsSearchEmptyStateProps) {
  return (
    <Empty className="p-6">
      <EmptyHeader className="gap-4">
        <EmptyMedia variant="icon" className="mb-0">
          <SearchX className="size-4" />
        </EmptyMedia>

        <div className="flex max-w-sm flex-col items-center gap-2">
          <EmptyTitle className="w-full text-center">
            No collections found for "{search}"
          </EmptyTitle>
          <EmptyDescription className="text-center">
            Try a different name, check spelling, or clear your search to see
            all available collections.
          </EmptyDescription>
        </div>
      </EmptyHeader>

      <EmptyContent className="max-w-none gap-4">
        <Button onClick={onClearSearch} type="button" variant="outline">
          Clear Search
        </Button>
      </EmptyContent>
    </Empty>
  );
}
