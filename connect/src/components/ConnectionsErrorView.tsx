import { AlertCircle } from "lucide-react";
import type { ConnectLabels } from "../lib/types";
import { PageLayout } from "./PageLayout";

interface ConnectionsErrorViewProps {
  error: Error | unknown;
  labels: Required<ConnectLabels>;
}

export function ConnectionsErrorView({
  error,
  labels,
}: ConnectionsErrorViewProps) {
  return (
    <PageLayout title={labels.loadErrorHeading} centerContent>
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
    </PageLayout>
  );
}
