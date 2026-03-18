import { useState, useMemo } from "react";
import { Check, Search } from "lucide-react";
import { cn } from "@/lib/utils";
import { getAppIconUrl } from "@/lib/utils/icons";
import { useTheme } from "@/lib/theme-provider";

interface Source {
  name: string;
  short_name: string;
}

interface SourcePickerProps {
  sources: Source[];
  selected: string[];
  onToggle: (shortName: string) => void;
}

function SourceIcon({ shortName }: { shortName: string }) {
  const { resolvedTheme } = useTheme();
  const [failed, setFailed] = useState(false);
  if (failed) {
    return (
      <div className="w-5 h-5 rounded-md bg-muted flex items-center justify-center text-[8px] font-bold text-muted-foreground uppercase">
        {shortName.slice(0, 2)}
      </div>
    );
  }
  return (
    <img
      src={getAppIconUrl(shortName, resolvedTheme)}
      alt=""
      className="w-5 h-5 rounded-md"
      onError={() => setFailed(true)}
    />
  );
}

export function SourcePicker({ sources, selected, onToggle }: SourcePickerProps) {
  const [filter, setFilter] = useState("");

  const filtered = useMemo(() => {
    if (!filter) return sources;
    const q = filter.toLowerCase();
    return sources.filter(
      (s) => s.name.toLowerCase().includes(q) || s.short_name.includes(q)
    );
  }, [sources, filter]);

  return (
    <div className="space-y-2">
      <div className="relative">
        <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground/40" />
        <input
          type="text"
          placeholder="Search sources..."
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          className="w-full h-8 pl-8 pr-3 text-xs rounded-lg bg-muted/40 border-0 text-foreground placeholder:text-muted-foreground/40 focus:outline-none focus:ring-1 focus:ring-primary/20"
        />
      </div>

      {selected.length > 0 && (
        <div className="text-[11px] text-muted-foreground">
          {selected.length} selected
        </div>
      )}

      <div className="grid grid-cols-4 gap-1.5 max-h-[400px] overflow-y-auto pr-1 [scrollbar-width:thin] [scrollbar-color:hsl(var(--muted-foreground)/0.15)_transparent] [&::-webkit-scrollbar]:w-[4px] [&::-webkit-scrollbar-track]:bg-transparent [&::-webkit-scrollbar-thumb]:rounded-full [&::-webkit-scrollbar-thumb]:bg-muted-foreground/15 hover:[&::-webkit-scrollbar-thumb]:bg-muted-foreground/30">
        {filtered.map((s) => {
          const active = selected.includes(s.short_name);
          return (
            <button
              key={s.short_name}
              onClick={() => onToggle(s.short_name)}
              title={s.name}
              className={cn(
                "relative flex flex-col items-center gap-1 px-1 py-2 rounded-lg transition-colors cursor-pointer",
                active
                  ? "bg-primary/10 ring-1 ring-primary/30"
                  : "bg-muted/40 hover:bg-muted/70"
              )}
            >
              <SourceIcon shortName={s.short_name} />
              <span className="text-[9px] leading-tight text-center truncate w-full text-muted-foreground">
                {s.name}
              </span>
              {active && (
                <div className="absolute -top-0.5 -right-0.5 w-3 h-3 rounded-full bg-primary flex items-center justify-center">
                  <Check className="h-2 w-2 text-primary-foreground" />
                </div>
              )}
            </button>
          );
        })}
      </div>
    </div>
  );
}
