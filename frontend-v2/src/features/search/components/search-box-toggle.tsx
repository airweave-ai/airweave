/**
 * SearchBoxToggle - Toggle button component with docs link support
 */

import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";

export interface ToggleButtonProps {
  id: string;
  icon: React.ReactNode;
  isActive: boolean;
  onClick: () => void;
  tooltip: { title: string; description: string; docsUrl?: string };
  openTooltip: string | null;
  onMouseEnter: (id: string) => void;
  onMouseLeave: (id: string) => void;
  onContentMouseEnter: (id: string) => void;
  onContentMouseLeave: (id: string) => void;
}

export function ToggleButton({
  id,
  icon,
  isActive,
  onClick,
  tooltip,
  openTooltip,
  onMouseEnter,
  onMouseLeave,
  onContentMouseEnter,
  onContentMouseLeave,
}: ToggleButtonProps) {
  return (
    <Tooltip open={openTooltip === id}>
      <TooltipTrigger asChild>
        <div
          onMouseEnter={() => onMouseEnter(id)}
          onMouseLeave={() => onMouseLeave(id)}
          className={cn(
            "h-7 w-8 overflow-hidden rounded-md border p-0",
            isActive ? "border-primary" : "border-border/50"
          )}
        >
          <button
            type="button"
            onClick={onClick}
            className={cn(
              "flex size-full items-center justify-center rounded-md transition-all",
              isActive
                ? "text-primary hover:bg-primary/10"
                : "text-foreground hover:bg-muted"
            )}
          >
            {icon}
          </button>
        </div>
      </TooltipTrigger>
      <TooltipContent
        side="bottom"
        onMouseEnter={() => onContentMouseEnter(id)}
        onMouseLeave={() => onContentMouseLeave(id)}
      >
        <p className="font-semibold">{tooltip.title}</p>
        <p className="text-muted-foreground text-xs">{tooltip.description}</p>
        {tooltip.docsUrl && (
          <div className="border-border mt-2 border-t pt-2">
            <a
              href={tooltip.docsUrl}
              target="_blank"
              rel="noreferrer"
              className="text-xs text-blue-400 hover:underline"
            >
              Docs
            </a>
          </div>
        )}
      </TooltipContent>
    </Tooltip>
  );
}
