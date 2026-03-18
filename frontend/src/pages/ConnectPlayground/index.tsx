import { useEffect } from "react";
import { Navigate } from "react-router-dom";
import { ExternalLink } from "lucide-react";
import { posthog } from "@/lib/posthog-provider";
import { useOrganizationStore } from "@/lib/stores/organizations";
import { FeatureFlags } from "@/lib/constants/feature-flags";
import { usePlaygroundState } from "./hooks/usePlaygroundState";
import { PlaygroundConfig } from "./config/PlaygroundConfig";
import { ExportDropdown } from "./config/ExportDropdown";
import { CollectionPicker } from "./config/CollectionPicker";
import { SandboxShell } from "./sandbox/SandboxShell";
import { ConnectPreview } from "./preview/ConnectPreview";
import { WidgetPreview } from "./preview/WidgetPreview";
import { CodePreview } from "./code/CodePreview";
import { HowItWorks } from "./HowItWorks";

function getConnectUrl(): string {
  if (import.meta.env.VITE_CONNECT_URL) {
    return import.meta.env.VITE_CONNECT_URL as string;
  }
  const { hostname, protocol } = window.location;
  if (hostname === "localhost" || hostname === "127.0.0.1") {
    return "http://localhost:8082";
  }
  return `${protocol}//connect.${hostname.replace(/^app\./, "")}`;
}

const CONNECT_URL = getConnectUrl();

export default function ConnectPlayground() {
  const hasConnectFeature = useOrganizationStore((state) => state.hasFeature(FeatureFlags.CONNECT));
  const state = usePlaygroundState();

  useEffect(() => {
    if (hasConnectFeature) {
      posthog.capture("connect_playground_opened");
    }
  }, [hasConnectFeature]);

  if (!hasConnectFeature) {
    return <Navigate to="/" replace />;
  }

  return (
    <>
      <div className="mx-auto w-full max-w-[1800px] min-h-[calc(100vh-64px)] flex flex-col px-6 py-6 overflow-auto">
        {/* Header */}
        <div className="flex items-center justify-between mb-4 shrink-0">
          <div className="min-w-0 flex-1 mr-4">
            <h1 className="text-2xl font-bold">Airweave Connect</h1>
            <p className="text-sm text-muted-foreground mt-1 leading-relaxed">
              Airweave Connect is an embeddable widget that handles OAuth, credentials, and data sync, letting your users connect their apps to your product.{" "}
              <a
                href="https://docs.airweave.ai/connect"
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1 text-primary hover:underline"
              >
                Learn more
                <ExternalLink className="h-3 w-3" />
              </a>
            </p>
          </div>
          <div className="flex items-center gap-1.5 shrink-0">
            <ExportDropdown config={state.config} />
            <CollectionPicker
              collections={state.collections}
              selected={state.selectedCollection}
              isNew={state.isNewCollection}
              onSelect={(id) => {
                state.setSelectedCollection(id);
                state.setIsNewCollection(false);
              }}
              onSelectNew={() => state.setIsNewCollection(true)}
            />
          </div>
        </div>

        {/* Main area */}
        <div className="flex-1 min-h-0 flex gap-5">
          {/* Left column */}
          <div className="flex-1 min-w-0 flex flex-col gap-5 overflow-hidden">
            {/* How it works */}
            <div>
              <h2 className="text-[11px] font-medium text-muted-foreground/50 uppercase tracking-wider mb-2">
                How it works
              </h2>
              <HowItWorks />
            </div>

            {/* Preview */}
            <div>
              <h2 className="text-[11px] font-medium text-muted-foreground/50 uppercase tracking-wider mb-2">
                Preview
              </h2>
              <div className="grid grid-cols-2 gap-4">
                <div className="flex flex-col min-w-0">
                  <div className="text-[10px] text-muted-foreground/40 mb-1.5">Widget theme</div>
                  <div
                    className="flex-1 rounded-xl border border-border/40 bg-muted/20 p-3"
                    title="Live preview of how the Connect widget will look with your current theme and modal settings"
                  >
                    <WidgetPreview
                      colors={state.activeColors}
                      modal={state.config.modal}
                    />
                  </div>
                </div>
                <div className="flex flex-col min-w-0">
                  <div className="text-[10px] text-muted-foreground/40 mb-1.5">Sandbox</div>
                  <div className="flex-1 rounded-xl border border-border/40 bg-muted/20 p-3">
                    <SandboxShell
                      onOpenConnect={state.openPreview}
                      isLoading={state.isCreatingSession}
                    />
                  </div>
                </div>
              </div>
            </div>

            {/* Configuration */}
            <div>
              <h2 className="text-[11px] font-medium text-muted-foreground/50 uppercase tracking-wider mb-2">
                Customize your widget
              </h2>
              <PlaygroundConfig
                config={state.config}
                activeColors={state.activeColors}
                activeDefaults={state.activeDefaults}
                activeColorKey={state.activeColorKey}
                onModeChange={(m) => state.updateConfig({ themeMode: m })}
                onColorChange={state.setActiveColor}
                onSessionModeChange={(m) => state.updateConfig({ sessionMode: m })}
                onModalUpdate={state.updateModal}
                sources={state.sources}
                selectedIntegrations={state.config.allowedIntegrations}
                onToggleIntegration={state.toggleIntegration}
              />
            </div>
          </div>

          {/* Right: code */}
          <div className="w-[420px] shrink-0 min-w-0 flex flex-col">
            <h2 className="text-[11px] font-medium text-muted-foreground/50 uppercase tracking-wider mb-2 shrink-0">
              Integration code
            </h2>
            <div className="flex-1 min-h-0">
              <CodePreview config={state.config} isNewCollection={state.isNewCollection} />
            </div>
          </div>
        </div>
      </div>

      <ConnectPreview
        isOpen={state.isPreviewOpen}
        onClose={state.closePreview}
        sessionToken={state.sessionToken}
        config={state.config}
        connectUrl={CONNECT_URL}
      />
    </>
  );
}
