import { AppWindowMac, Key, Link2, ShieldCheck } from "lucide-react";
import { useTheme } from "../lib/theme";
import type { ConnectLabels } from "../lib/types";

interface EmptyStateProps {
  labels: Required<ConnectLabels>;
  showConnect: boolean;
}

export function EmptyState({ labels, showConnect }: EmptyStateProps) {
  const { options, resolvedMode } = useTheme();
  const logoUrl = options.logoUrl;

  // Use nice design when connect is allowed
  if (showConnect) {
    return (
      <div className="flex flex-col -mx-6">
        {/* Header with icon */}
        <header className="pt-8 pb-6 px-6">
          {/* App icons */}
          <div className="flex items-center justify-center gap-3 mb-5">
            {/* Logo or fallback icon */}
            <div
              className="p-3 rounded-xl size-18"
              style={{
                backgroundColor: "var(--connect-bg)",
                boxShadow:
                  resolvedMode === "dark"
                    ? "0 4px 12px rgba(0, 0, 0, 0.3)"
                    : "0 4px 12px rgba(0, 0, 0, 0.08)",
              }}
            >
              {logoUrl ? (
                <img
                  src={logoUrl}
                  alt="Logo"
                  className="size-12 object-contain rounded-lg"
                />
              ) : (
                <div
                  className="size-12 rounded-lg flex items-center justify-center"
                  style={{
                    backgroundColor:
                      "color-mix(in srgb, var(--connect-text) 10%, transparent)",
                  }}
                >
                  <AppWindowMac
                    size={24}
                    strokeWidth={1.5}
                    style={{ color: "var(--connect-text-muted)" }}
                  />
                </div>
              )}
            </div>

            {/* Connection indicator dots */}
            <div className="flex gap-1">
              <div
                className="size-1.5 rounded-full"
                style={{
                  backgroundColor: "var(--connect-text-muted)",
                  opacity: 0.5,
                }}
              />
              <div
                className="size-1.5 rounded-full"
                style={{
                  backgroundColor: "var(--connect-text-muted)",
                  opacity: 0.5,
                }}
              />
            </div>

            {/* 2x2 grid of popular app icons */}
            <div
              className="p-2 rounded-xl size-18"
              style={{
                backgroundColor: "var(--connect-bg)",
                boxShadow:
                  resolvedMode === "dark"
                    ? "0 4px 12px rgba(0, 0, 0, 0.3)"
                    : "0 4px 12px rgba(0, 0, 0, 0.08)",
              }}
            >
              <div className="grid grid-cols-2 gap-1 items-center justify-center gap-2 p-1">
                {["notion", "gmail", "slack", "jira"].map((app) => (
                  <div
                    className="rounded flex items-center justify-center"
                    key={app}
                  >
                    <img
                      src={`/icons/apps/${app}.svg`}
                      alt={app}
                      className="object-contain rounded"
                    />
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Title */}
          <h1
            className="text-xl font-semibold text-center"
            style={{ color: "var(--connect-text)" }}
          >
            {labels.emptyStateHeading}
          </h1>
          <p
            className="text-sm text-center mt-1 w-3/4 mx-auto"
            style={{ color: "var(--connect-text-muted)" }}
          >
            {labels.emptyStateDescription}
          </p>
        </header>

        {/* Info items */}
        <div className="px-6 py-5">
          <div className="flex flex-col gap-4">
            {/* Verify info */}
            <div className="flex items-center gap-4">
              <div
                className="flex-shrink-0 size-10 rounded-full flex items-center justify-center"
                style={{
                  backgroundColor:
                    "color-mix(in srgb, var(--connect-text-muted) 15%, transparent)",
                }}
              >
                <ShieldCheck
                  size={20}
                  strokeWidth={1.5}
                  style={{ color: "var(--connect-text-muted)" }}
                />
              </div>
              <p
                className="text-sm"
                style={{ color: "var(--connect-text-muted)" }}
              >
                {labels.welcomeInfoVerify}
              </p>
            </div>

            {/* Access info */}
            <div className="flex items-center gap-4">
              <div
                className="flex-shrink-0 size-10 rounded-full flex items-center justify-center"
                style={{
                  backgroundColor:
                    "color-mix(in srgb, var(--connect-text-muted) 15%, transparent)",
                }}
              >
                <Key
                  size={20}
                  strokeWidth={1.5}
                  style={{ color: "var(--connect-text-muted)" }}
                />
              </div>
              <p
                className="text-sm"
                style={{ color: "var(--connect-text-muted)" }}
              >
                {labels.welcomeInfoAccess}
              </p>
            </div>
          </div>
        </div>
      </div>
    );
  }

  // Default simple design (for manage-only mode)
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
    </div>
  );
}
