import { AlertCircle } from "lucide-react";
import type { ConnectLabels } from "../lib/types";
import { PoweredByAirweave } from "./PoweredByAirweave";

interface ConnectionsErrorViewProps {
  error: Error | unknown;
  labels: Required<ConnectLabels>;
}

export function ConnectionsErrorView({
  error,
  labels,
}: ConnectionsErrorViewProps) {
  return (
    <div
      className="h-screen flex flex-col"
      style={{ backgroundColor: "var(--connect-bg)" }}
    >
      {/* Fixed Header */}
      <header className="flex-shrink-0 p-6 pb-4">
        <h1
          className="font-medium text-lg"
          style={{ color: "var(--connect-text)" }}
        >
          {labels.loadErrorHeading}
        </h1>
      </header>

      {/* Scrollable Content */}
      <main className="flex-1 overflow-y-auto px-6 scrollable-content flex flex-col items-center justify-center text-center">
        <div
          className="w-16 h-16 rounded-full flex items-center justify-center mx-auto mb-4"
          style={{
            backgroundColor:
              "color-mix(in srgb, var(--connect-error) 20%, transparent)",
          }}
        >
          <AlertCircle
            className="w-8 h-8"
            strokeWidth={1.5}
            style={{ color: "var(--connect-error)" }}
          />
        </div>
        <p style={{ color: "var(--connect-text-muted)" }}>
          {error instanceof Error ? error.message : "An error occurred"}
        </p>
      </main>

      {/* Fixed Footer */}
      <footer className="flex-shrink-0">
        <PoweredByAirweave />
      </footer>
    </div>
  );
}
