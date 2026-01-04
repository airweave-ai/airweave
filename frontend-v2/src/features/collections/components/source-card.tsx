import { Plus } from "lucide-react";

import { Button } from "@/components/ui/button";
import { useIsDark } from "@/hooks/use-is-dark";
import { cn } from "@/lib/utils";

import { getAppIconUrl, getSourceColorClass } from "../utils/helpers";

interface SourceCardProps {
  id: string;
  name: string;
  shortName: string;
  onClick?: () => void;
  disabled?: boolean;
}

export function SourceCard({
  name,
  shortName,
  onClick,
  disabled = false,
}: SourceCardProps) {
  const isDark = useIsDark();

  return (
    <div
      className={cn(
        "group overflow-hidden rounded-lg border transition-all",
        disabled
          ? isDark
            ? "cursor-not-allowed border-slate-800 bg-slate-900/30 opacity-50"
            : "cursor-not-allowed border-slate-200 bg-white/50 opacity-50"
          : isDark
            ? "cursor-pointer border-slate-800 bg-slate-900/50 hover:border-slate-700 hover:bg-slate-900"
            : "cursor-pointer border-slate-200 bg-white hover:border-slate-300 hover:bg-slate-50"
      )}
      onClick={disabled ? undefined : onClick}
    >
      <div className="flex items-center justify-between p-2 sm:p-3 md:p-4">
        <div className="flex items-center gap-2 sm:gap-3">
          <SourceIcon shortName={shortName} isDark={isDark} />
          <span
            className={cn(
              "truncate text-xs font-medium sm:text-sm",
              disabled && "text-muted-foreground"
            )}
          >
            {name}
          </span>
        </div>
        <Button
          size="icon"
          variant="ghost"
          disabled={disabled}
          className={cn(
            "h-6 w-6 flex-shrink-0 rounded-full sm:h-7 sm:w-7 md:h-8 md:w-8",
            disabled
              ? isDark
                ? "cursor-not-allowed bg-slate-800/50 text-slate-500"
                : "cursor-not-allowed bg-slate-100/50 text-slate-400"
              : isDark
                ? "bg-slate-800/80 text-blue-400 group-hover:bg-blue-600/30 hover:bg-blue-600/20 hover:text-blue-300"
                : "bg-slate-100/80 text-blue-500 group-hover:bg-blue-100/80 hover:bg-blue-100 hover:text-blue-600"
          )}
        >
          <Plus className="h-3 w-3 transition-all sm:h-3.5 sm:w-3.5 md:h-4 md:w-4" />
        </Button>
      </div>
    </div>
  );
}

interface SourceIconProps {
  shortName: string;
  isDark: boolean;
}

function SourceIcon({ shortName, isDark }: SourceIconProps) {
  return (
    <div className="flex h-8 w-8 flex-shrink-0 items-center justify-center overflow-hidden rounded-md sm:h-9 sm:w-9 md:h-10 md:w-10">
      <img
        src={getAppIconUrl(shortName, isDark ? "dark" : "light")}
        alt={`${shortName} icon`}
        className="h-7 w-7 object-contain sm:h-8 sm:w-8 md:h-9 md:w-9"
        onError={(e) => {
          // Fallback to initials if icon fails to load
          const target = e.currentTarget;
          target.style.display = "none";
          const parent = target.parentElement;
          if (parent) {
            parent.classList.add(getSourceColorClass(shortName));
            parent.innerHTML = `<span class="text-white font-semibold text-xs sm:text-sm">${shortName.substring(0, 2).toUpperCase()}</span>`;
          }
        }}
      />
    </div>
  );
}
