import { Info } from "lucide-react";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { ThemePicker } from "./ThemePicker";
import { ModePicker } from "./ModePicker";
import { SourcePicker } from "./SourcePicker";
import { ConfigToolbar } from "./ConfigToolbar";
import type {
  PlaygroundConfig as ConfigType,
  ThemeColors,
  ThemeMode,
  SessionMode,
  ModalAppearance,
} from "../hooks/usePlaygroundState";

interface PlaygroundConfigProps {
  config: ConfigType;
  activeColors: ThemeColors;
  activeDefaults: ThemeColors;
  activeColorKey: string;
  onModeChange: (mode: ThemeMode) => void;
  onColorChange: (key: keyof ThemeColors, value: string) => void;
  onSessionModeChange: (mode: SessionMode) => void;
  onModalUpdate: (patch: Partial<ModalAppearance>) => void;
  sources: { name: string; short_name: string }[];
  selectedIntegrations: string[];
  onToggleIntegration: (shortName: string) => void;
}

function SectionLabel({
  children,
  tooltip,
}: {
  children: React.ReactNode;
  tooltip?: React.ReactNode;
}) {
  return (
    <div className="flex items-center gap-1.5 text-[11px] font-medium text-muted-foreground mb-2">
      {children}
      {tooltip && (
        <TooltipProvider delayDuration={200}>
          <Tooltip>
            <TooltipTrigger asChild>
              <Info className="h-3 w-3 text-muted-foreground/50 cursor-help" />
            </TooltipTrigger>
            <TooltipContent side="top" className="max-w-[280px] text-xs p-3">
              {tooltip}
            </TooltipContent>
          </Tooltip>
        </TooltipProvider>
      )}
    </div>
  );
}

export function PlaygroundConfig({
  config,
  activeColors,
  activeDefaults,
  activeColorKey,
  onModeChange,
  onColorChange,
  onSessionModeChange,
  onModalUpdate,
  sources,
  selectedIntegrations,
  onToggleIntegration,
}: PlaygroundConfigProps) {
  return (
    <div className="grid grid-cols-2 gap-5 px-1 py-3">
      {/* Left column: Theme + Modal */}
      <div className="space-y-5">
        <div>
          <SectionLabel
            tooltip={
              <div className="space-y-1.5">
                <p className="font-medium text-popover-foreground">Customize the Connect widget appearance.</p>
                <p className="text-muted-foreground">Choose dark, light, or auto mode. Edit colors to match your brand — click any swatch to pick a color, hover to reveal the reset button.</p>
              </div>
            }
          >
            Theme
          </SectionLabel>
          <ThemePicker
            mode={config.themeMode}
            onModeChange={onModeChange}
            colors={activeColors}
            defaults={activeDefaults}
            colorKeyLabel={activeColorKey === "darkColors" ? "dark" : "light"}
            onColorChange={onColorChange}
          />
        </div>

        <div>
          <SectionLabel
            tooltip={
              <div className="space-y-2">
                <p className="font-medium text-popover-foreground">Configure the modal container styling.</p>
                <div className="space-y-1.5">
                  <div className="flex gap-2">
                    <span className="font-mono text-[10px] px-1.5 py-0.5 rounded bg-muted/50 text-popover-foreground shrink-0">Radius</span>
                    <span className="text-muted-foreground">Corner rounding of the widget frame</span>
                  </div>
                  <div className="flex gap-2">
                    <span className="font-mono text-[10px] px-1.5 py-0.5 rounded bg-muted/50 text-popover-foreground shrink-0">Border</span>
                    <span className="text-muted-foreground">Outer border width and color</span>
                  </div>
                </div>
              </div>
            }
          >
            Modal
          </SectionLabel>
          <ConfigToolbar modal={config.modal} onUpdate={onModalUpdate} />
        </div>
      </div>

      {/* Right column: Session mode + Sources */}
      <div className="space-y-5">
        <div>
          <SectionLabel
            tooltip={
              <div className="space-y-2">
                <p className="font-medium text-popover-foreground">Controls what end-users can do in the widget.</p>
                <div className="space-y-1.5">
                  <div className="flex gap-2">
                    <span className="font-mono text-[10px] px-1.5 py-0.5 rounded bg-muted/50 text-popover-foreground shrink-0">all</span>
                    <span className="text-muted-foreground">Connect new sources and manage existing ones</span>
                  </div>
                  <div className="flex gap-2">
                    <span className="font-mono text-[10px] px-1.5 py-0.5 rounded bg-muted/50 text-popover-foreground shrink-0">connect</span>
                    <span className="text-muted-foreground">Only add new source connections</span>
                  </div>
                  <div className="flex gap-2">
                    <span className="font-mono text-[10px] px-1.5 py-0.5 rounded bg-muted/50 text-popover-foreground shrink-0">manage</span>
                    <span className="text-muted-foreground">Only view and manage existing connections</span>
                  </div>
                  <div className="flex gap-2">
                    <span className="font-mono text-[10px] px-1.5 py-0.5 rounded bg-muted/50 text-popover-foreground shrink-0">reauth</span>
                    <span className="text-muted-foreground">Only re-authenticate expired connections</span>
                  </div>
                </div>
              </div>
            }
          >
            Session mode
          </SectionLabel>
          <ModePicker mode={config.sessionMode} onChange={onSessionModeChange} />
        </div>

        <div>
          <SectionLabel
            tooltip={
              <div className="space-y-1.5">
                <p className="font-medium text-popover-foreground">Filter which sources appear in the widget.</p>
                <p className="text-muted-foreground">Select specific sources to restrict the list, or leave empty to show all available sources.</p>
              </div>
            }
          >
            Sources
          </SectionLabel>
          <SourcePicker
            sources={sources}
            selected={selectedIntegrations}
            onToggle={onToggleIntegration}
          />
        </div>
      </div>
    </div>
  );
}
