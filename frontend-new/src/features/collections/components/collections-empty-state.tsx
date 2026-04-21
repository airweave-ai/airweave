import { IconFolderPlus, IconSearchOff } from '@tabler/icons-react';
import type { ReactNode } from 'react';
import { Button } from '@/shared/ui/button';
import {
  Empty,
  EmptyContent,
  EmptyDescription,
  EmptyHeader,
  EmptyMedia,
  EmptyTitle,
} from '@/shared/ui/empty';

type CollectionsEmptyStateCardProps = {
  action: ReactNode;
  description: string;
  icon: typeof IconFolderPlus;
  title: string;
};

type CollectionsNoSearchResultsStateProps = {
  onClearSearch: () => void;
  search: string;
};

export function CollectionsNoSearchResultsState({
  search,
  onClearSearch,
}: CollectionsNoSearchResultsStateProps) {
  return (
    <CollectionsEmptyStateCard
      action={
        <Button onClick={onClearSearch} type="button" variant="outline">
          Clear Search
        </Button>
      }
      description="Try a different name, check spelling, or clear your search to see all available collections."
      icon={IconSearchOff}
      title={`No collections found for "${search}"`}
    />
  );
}

export function CollectionsEmptyState({
  onCreateCollection,
}: {
  onCreateCollection: () => void;
}) {
  return (
    <CollectionsEmptyStateCard
      action={
        <Button onClick={onCreateCollection} type="button" variant="outline">
          Create Collection
        </Button>
      }
      description="Collections group connected sources into searchable context for your agents. Create your first collection to get started."
      icon={IconFolderPlus}
      title="No collections yet"
    />
  );
}

function CollectionsEmptyStateCard({
  action,
  description,
  icon: Icon,
  title,
}: CollectionsEmptyStateCardProps) {
  return (
    <Empty>
      <EmptyHeader>
        <EmptyMedia variant="icon">
          <Icon className="size-4" />
        </EmptyMedia>

        <EmptyTitle>{title}</EmptyTitle>
        <EmptyDescription>{description}</EmptyDescription>
      </EmptyHeader>

      <EmptyContent>{action}</EmptyContent>
    </Empty>
  );
}
