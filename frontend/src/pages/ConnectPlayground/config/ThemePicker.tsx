import { Moon, Sun, Monitor, RotateCcw } from "lucide-react";
import { cn } from "@/lib/utils";
import type { ThemeMode, ThemeColors } from "../hooks/usePlaygroundState";

interface ThemePickerProps {
  mode: ThemeMode;
  onModeChange: (mode: ThemeMode) => void;
  colors: ThemeColors;
  defaults: ThemeColors;
  colorKeyLabel: string;
  onColorChange: (key: keyof ThemeColors, value: string) => void;
}

const MODE_OPTIONS: { value: ThemeMode; icon: typeof Moon; label: string }[] = [
  { value: "dark", icon: Moon, label: "Dark" },
  { value: "light", icon: Sun, label: "Light" },
  { value: "system", icon: Monitor, label: "Auto" },
];

const COLOR_KEYS: { key: keyof ThemeColors; label: string }[] = [
  { key: "primary", label: "Accent" },
  { key: "background", label: "Background" },
  { key: "surface", label: "Surface" },
  { key: "text", label: "Text" },
  { key: "textMuted", label: "Muted" },
  { key: "border", label: "Border" },
];

export function ThemePicker({
  mode,
  onModeChange,
  colors,
  defaults,
  colorKeyLabel,
  onColorChange,
}: ThemePickerProps) {
  return (
    <div className="space-y-3">
      {/* Mode */}
      <div className="flex gap-1 rounded-lg bg-muted/50 p-0.5">
        {MODE_OPTIONS.map(({ value, icon: Icon, label }) => (
          <button
            key={value}
            onClick={() => onModeChange(value)}
            className={cn(
              "flex-1 flex items-center justify-center gap-1.5 py-1.5 rounded-md text-xs font-medium transition-all",
              mode === value
                ? "bg-background text-foreground shadow-sm"
                : "text-muted-foreground hover:text-foreground"
            )}
          >
            <Icon className="h-3 w-3" />
            {label}
          </button>
        ))}
      </div>

      {/* Colors */}
      <div className="space-y-1">
        {COLOR_KEYS.map(({ key, label }) => {
          const isCustom = colors[key] !== defaults[key];
          return (
            <label
              key={key}
              className="group flex items-center gap-2.5 py-1 cursor-pointer"
            >
              <div className="relative shrink-0">
                <input
                  type="color"
                  value={colors[key]}
                  onChange={(e) => onColorChange(key, e.target.value)}
                  className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
                />
                <div
                  className="w-5 h-5 rounded-md border border-border/40"
                  style={{ backgroundColor: colors[key] }}
                />
              </div>
              <span className="text-xs text-muted-foreground flex-1">{label}</span>
              {isCustom && (
                <button
                  onClick={(e) => {
                    e.preventDefault();
                    onColorChange(key, defaults[key]);
                  }}
                  className="opacity-0 group-hover:opacity-100 transition-opacity"
                >
                  <RotateCcw className="h-3 w-3 text-muted-foreground/40" />
                </button>
              )}
            </label>
          );
        })}
      </div>
    </div>
  );
}
