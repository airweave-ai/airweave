import { IconKey, IconSearchOff } from '@tabler/icons-react';
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

type ApiKeysEmptyStateCardProps = {
  action: ReactNode;
  description: string;
  icon: typeof IconKey;
  title: string;
};

type ApiKeysNoSearchResultsStateProps = {
  onClearSearch: () => void;
  search: string;
};

export function ApiKeysNoSearchResultsState({
  search,
  onClearSearch,
}: ApiKeysNoSearchResultsStateProps) {
  return (
    <ApiKeysEmptyStateCard
      action={
        <Button onClick={onClearSearch} type="button" variant="outline">
          Clear Search
        </Button>
      }
      description="Try a different term or clear your search to see all available API keys."
      icon={IconSearchOff}
      title={`No API keys found for "${search}"`}
    />
  );
}

export function ApiKeysEmptyState({ action }: { action?: ReactNode }) {
  return (
    <ApiKeysEmptyStateCard
      action={action}
      description="API keys let you authenticate requests to the Airweave API. Create your first API key to get started."
      icon={IconKey}
      title="No API keys yet"
    />
  );
}

function ApiKeysEmptyStateCard({
  action,
  description,
  icon: Icon,
  title,
}: ApiKeysEmptyStateCardProps) {
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
