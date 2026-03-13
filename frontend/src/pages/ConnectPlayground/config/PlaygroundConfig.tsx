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

function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <div className="text-[11px] font-medium text-muted-foreground mb-2">
      {children}
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
    <div className="h-full overflow-y-auto px-3 py-3 space-y-5">
      <div>
        <SectionLabel>Theme</SectionLabel>
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
        <SectionLabel>Session mode</SectionLabel>
        <ModePicker mode={config.sessionMode} onChange={onSessionModeChange} />
      </div>

      <div>
        <SectionLabel>Modal</SectionLabel>
        <ConfigToolbar modal={config.modal} onUpdate={onModalUpdate} />
      </div>

      <div>
        <SectionLabel>Sources</SectionLabel>
        <SourcePicker
          sources={sources}
          selected={selectedIntegrations}
          onToggle={onToggleIntegration}
        />
      </div>
    </div>
  );
}
