import { IconAlertTriangleFilled, IconRefresh } from '@tabler/icons-react';
import {
  Alert,
  AlertAction,
  AlertDescription,
  AlertTitle,
} from '@/shared/ui/alert';
import { Button } from '@/shared/ui/button';

type SourceConnectionSyncErrorCardProps = {
  error?: string;
  onResync: () => void;
};

export function SourceConnectionSyncErrorCard({
  error,
  onResync,
}: SourceConnectionSyncErrorCardProps) {
  return (
    <Alert variant="destructive">
      <IconAlertTriangleFilled />
      <AlertTitle>Last sync failed on our side</AlertTitle>
      <AlertDescription>
        {error ??
          'Your existing data is still searchable. Only the latest sync was affected.'}
      </AlertDescription>
      <AlertAction className="top-1/2 -translate-y-1/2">
        <Button
          size="sm"
          variant="outline"
          className="text-foreground"
          onClick={onResync}
        >
          <IconRefresh className="size-3.5" /> Resync
        </Button>
      </AlertAction>
    </Alert>
  );
}
