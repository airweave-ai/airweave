import type { LucideIcon } from "lucide-react";
import { AppWindowMac, Key, Link2, ShieldCheck } from "lucide-react";
import { getAppIconUrl } from "../lib/icons";
import { useTheme } from "../lib/theme";
import type { ConnectLabels } from "../lib/types";

interface EmptyStateProps {
  labels: Required<ConnectLabels>;
  showConnect: boolean;
}

const FEATURED_APPS = ["notion", "gmail", "slack", "jira"];

function IconCard({
  children,
  resolvedMode,
}: {
  children: React.ReactNode;
  resolvedMode: "dark" | "light";
}) {
  return (
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
      {children}
    </div>
  );
}

function InfoItem({ icon: Icon, text }: { icon: LucideIcon; text: string }) {
  return (
    <div className="flex items-center gap-4">
      <div
        className="flex-shrink-0 size-10 rounded-full flex items-center justify-center"
        style={{
          backgroundColor:
            "color-mix(in srgb, var(--connect-text-muted) 15%, transparent)",
        }}
      >
        <Icon
          size={20}
          strokeWidth={1.5}
          style={{ color: "var(--connect-text-muted)" }}
        />
      </div>
      <p className="text-sm" style={{ color: "var(--connect-text-muted)" }}>
        {text}
      </p>
    </div>
  );
}

function ConnectionDots() {
  return (
    <div className="flex gap-1 opacity-50">
      <div
        className="size-1.5 rounded-full"
        style={{ backgroundColor: "var(--connect-text-muted)" }}
      />
      <div
        className="size-1.5 rounded-full"
        style={{ backgroundColor: "var(--connect-text-muted)" }}
      />
    </div>
  );
}

export function EmptyState({ labels, showConnect }: EmptyStateProps) {
  const { options, resolvedMode } = useTheme();
  const logoUrl = options.logoUrl;

  if (showConnect) {
    return (
      <div
        className="flex flex-col -mx-6"
        style={{
          background: `linear-gradient(to bottom, color-mix(in srgb, var(--connect-primary) 8%, var(--connect-bg)) 0%, var(--connect-bg) 100%)`,
        }}
      >
        <header className="pt-8 pb-6 px-6">
          <div className="flex items-center justify-center gap-3 mb-5">
            <IconCard resolvedMode={resolvedMode}>
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
            </IconCard>

            <ConnectionDots />

            <IconCard resolvedMode={resolvedMode}>
              <div className="grid grid-cols-2 gap-1 p-1">
                {FEATURED_APPS.map((app) => (
                  <div
                    className="rounded flex items-center justify-center"
                    key={app}
                  >
                    <img
                      src={getAppIconUrl(app, resolvedMode)}
                      alt={app}
                      className="object-contain rounded"
                    />
                  </div>
                ))}
              </div>
            </IconCard>
          </div>

          <h1
            className="text-xl font-semibold text-center"
            style={{
              color: "var(--connect-text)",
              fontFamily: "var(--connect-font-heading)",
            }}
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

        <div className="px-6 py-5">
          <div className="flex flex-col gap-4">
            <InfoItem icon={ShieldCheck} text={labels.welcomeInfoVerify} />
            <InfoItem icon={Key} text={labels.welcomeInfoAccess} />
          </div>
        </div>
      </div>
    );
  }

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
      <p
        className="font-medium mb-1"
        style={{
          color: "var(--connect-text)",
          fontFamily: "var(--connect-font-heading)",
        }}
      >
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
