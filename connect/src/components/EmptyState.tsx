import { Link2, Plus } from "lucide-react";
import type { ConnectLabels } from "../lib/types";
import { Button } from "./Button";

interface EmptyStateProps {
  labels: Required<ConnectLabels>;
  showConnect: boolean;
  onConnect: () => void;
}

export function EmptyState({
  labels,
  showConnect,
  onConnect,
}: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center py-12 text-center">
      <div
        className="w-12 h-12 rounded-full flex items-center justify-center mb-4"
        style={{
          backgroundColor:
            "color-mix(in srgb, var(--connect-text-muted) 20%, transparent)",
        }}
      >
        <Link2
          className="w-6 h-6"
          strokeWidth={1.5}
          style={{ color: "var(--connect-text-muted)" }}
        />
      </div>
      <p className="font-medium mb-1" style={{ color: "var(--connect-text)" }}>
        {labels.emptyStateHeading}
      </p>
      <p
        className="text-sm mb-4"
        style={{ color: "var(--connect-text-muted)" }}
      >
        {labels.emptyStateDescription}
      </p>
      {showConnect && (
        <Button onClick={onConnect} className="py-2">
          <Plus className="w-4 h-4" />
          {labels.buttonConnect}
        </Button>
      )}
    </div>
  );
}
