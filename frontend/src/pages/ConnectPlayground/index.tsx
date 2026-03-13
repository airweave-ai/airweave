import { useEffect } from "react";
import { ExternalLink } from "lucide-react";
import posthog from "@/lib/posthog-provider";
import { usePlaygroundState } from "./hooks/usePlaygroundState";
import { PlaygroundConfig } from "./config/PlaygroundConfig";
import { ExportDropdown } from "./config/ExportDropdown";
import { CollectionPicker } from "./config/CollectionPicker";
import { SandboxShell } from "./sandbox/SandboxShell";
import { ConnectPreview } from "./preview/ConnectPreview";
import { CodePreview } from "./code/CodePreview";

const CONNECT_URL = import.meta.env.VITE_CONNECT_URL || "http://localhost:8082";

export default function ConnectPlayground() {
  const state = usePlaygroundState();

  useEffect(() => {
    posthog.capture("connect_playground_opened");
  }, []);

  return (
    <>
      <div className="mx-auto w-full max-w-[1800px] h-[calc(100vh-64px)] flex flex-col px-6 py-6">
        {/* Header */}
        <div className="flex items-center justify-between mb-5 shrink-0">
          <div>
            <h1 className="text-2xl font-bold">Connect</h1>
            <p className="text-sm text-muted-foreground mt-0.5">
              Configure and preview the embeddable widget.
            </p>
          </div>
          <div className="flex items-center gap-1.5">
            <a
              href="https://docs.airweave.ai/connect"
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium text-muted-foreground hover:text-foreground hover:bg-accent/30 transition-colors"
            >
              <ExternalLink className="h-3.5 w-3.5" />
              Docs
            </a>
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
          {/* Left: config panel */}
          <div className="w-[260px] shrink-0 overflow-hidden">
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

          {/* Center: sandbox */}
          <div className="flex-[4] min-w-0">
            <SandboxShell
              onOpenConnect={state.openPreview}
              isLoading={state.isCreatingSession}
            />
          </div>

          {/* Right: code */}
          <div className="flex-[5] min-w-0">
            <CodePreview config={state.config} isNewCollection={state.isNewCollection} />
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
