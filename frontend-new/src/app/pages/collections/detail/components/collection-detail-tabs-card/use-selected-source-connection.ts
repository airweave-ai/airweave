import * as React from 'react';
import { useQuery } from '@tanstack/react-query';
import type { SourceConnectionListItem } from '@/shared/api';
import { useGetSourceConnectionQueryOptions } from '@/features/source-connections';

export function useSelectedSourceConnection(
  sourceConnections: Array<SourceConnectionListItem>,
) {
  const [selectedSourceConnectionId, setSelectedSourceConnectionId] =
    React.useState<string | undefined>(undefined);
  const defaultSourceConnectionSummary = sourceConnections[0];
  const selectedSourceConnectionSummary =
    (selectedSourceConnectionId !== undefined
      ? sourceConnections.find(
          (sourceConnection) =>
            sourceConnection.id === selectedSourceConnectionId,
        )
      : undefined) ?? defaultSourceConnectionSummary;
  const sourceConnectionQueryOptions = useGetSourceConnectionQueryOptions({
    sourceConnectionId: selectedSourceConnectionSummary?.id ?? '',
  });
  const sourceConnectionQuery = useQuery({
    ...sourceConnectionQueryOptions,
    enabled: Boolean(selectedSourceConnectionSummary),
  });

  return {
    selectedSourceConnectionSummary,
    setSelectedSourceConnectionId,
    sourceConnection: sourceConnectionQuery.data,
    sourceConnectionQuery,
  };
}
