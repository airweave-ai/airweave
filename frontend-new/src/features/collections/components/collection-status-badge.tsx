import * as React from 'react';
import type { CollectionStatus } from '@/shared/api';
import {
  StatusBadge,
  StatusBadgeIndicator,
} from '@/shared/components/status-badge';

const statusLabels: Record<CollectionStatus, string> = {
  ACTIVE: 'Active',
  ERROR: 'Error',
  'NEEDS SOURCE': 'Needs source',
};

const statusVariants: Record<
  CollectionStatus,
  React.ComponentProps<typeof StatusBadge>['variant']
> = {
  ACTIVE: 'success',
  ERROR: 'destructive',
  'NEEDS SOURCE': 'destructive',
};

export function CollectionStatusBadge({
  status,
}: {
  status: CollectionStatus;
}) {
  return (
    <StatusBadge variant={statusVariants[status]}>
      <StatusBadgeIndicator />
      {statusLabels[status]}
    </StatusBadge>
  );
}
