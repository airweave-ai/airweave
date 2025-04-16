import { SyncUIMetadata } from "./types";

interface SyncPipelineVisualProps {
  sync: {
    uiMetadata: SyncUIMetadata;
    id?: string;
    status?: string;
    organizationId?: string;
    createdAt?: string;
  };
}

export const SyncPipelineVisual = ({ sync }: SyncPipelineVisualProps) => {
  return (
    <div className="flex items-center justify-center space-x-4 p-4 bg-background rounded-lg border">
      {/* Source */}
      <div className="flex items-center space-x-2 p-2 bg-primary/10 rounded">
        <div className="text-sm font-medium">{sync.uiMetadata.source.name}</div>
      </div>

      {/* Arrow */}
      <div className="text-muted-foreground">→</div>

      {/* Destination */}
      <div className="flex items-center space-x-2 p-2 bg-primary/10 rounded">
        <div className="text-sm font-medium">{sync.uiMetadata.destination.name}</div>
      </div>
    </div>
  );
};
