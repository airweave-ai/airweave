import type { SyncJobStatus } from '@/shared/api';

const activeSyncJobStatuses = new Set<SyncJobStatus>([
  'created',
  'pending',
  'running',
  'cancelling',
]);

export function isActiveSyncJobStatus(
  status: SyncJobStatus | null | undefined,
) {
  return status ? activeSyncJobStatuses.has(status) : false;
}
