import { cn } from "@/lib/utils";
import type { SessionMode } from "../hooks/usePlaygroundState";

interface ModePickerProps {
  mode: SessionMode;
  onChange: (mode: SessionMode) => void;
}

const MODES: SessionMode[] = ["all", "connect", "manage", "reauth"];

export function ModePicker({ mode, onChange }: ModePickerProps) {
  return (
    <div className="flex gap-1 rounded-lg bg-muted/50 p-0.5">
      {MODES.map((m) => (
        <button
          key={m}
          onClick={() => onChange(m)}
          className={cn(
            "flex-1 py-1.5 rounded-md text-xs font-medium transition-all capitalize text-center",
            mode === m
              ? "bg-background text-foreground shadow-sm"
              : "text-muted-foreground hover:text-foreground"
          )}
        >
          {m}
        </button>
      ))}
    </div>
  );
}
