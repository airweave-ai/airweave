import { Link2, Plus } from "lucide-react";
import type { ConnectLabels } from "../lib/types";

interface EmptyStateProps {
  labels: Required<ConnectLabels>;
  showConnect: boolean;
  onConnect: () => void;
}

export function EmptyState({ labels, showConnect, onConnect }: EmptyStateProps) {
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
        <button
          onClick={onConnect}
          className="px-4 py-2 font-medium rounded-md text-sm transition-colors flex items-center gap-2"
          style={{
            backgroundColor: "var(--connect-primary)",
            color: "white",
          }}
          onMouseEnter={(e) =>
            (e.currentTarget.style.backgroundColor =
              "var(--connect-primary-hover)")
          }
          onMouseLeave={(e) =>
            (e.currentTarget.style.backgroundColor = "var(--connect-primary)")
          }
        >
          <Plus className="w-4 h-4" />
          {labels.buttonConnect}
        </button>
      )}
    </div>
  );
}
