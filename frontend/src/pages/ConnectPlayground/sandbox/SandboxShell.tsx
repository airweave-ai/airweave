import { Plug, Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";

interface SandboxShellProps {
  onOpenConnect: () => void;
  isLoading: boolean;
}

export function SandboxShell({ onOpenConnect, isLoading }: SandboxShellProps) {
  return (
    <div className="h-full flex items-center justify-center">
      {/* Browser frame */}
      <div className="w-full max-w-[480px] rounded-xl border border-border/40 bg-background shadow-sm overflow-hidden">
        {/* Safari-style top bar */}
        <div className="flex items-center px-3.5 py-2.5 bg-muted/30 border-b border-border/30">
          <div className="flex gap-1.5">
            <div className="w-3 h-3 rounded-full bg-[#ff5f57]" />
            <div className="w-3 h-3 rounded-full bg-[#febc2e]" />
            <div className="w-3 h-3 rounded-full bg-[#28c840]" />
          </div>
          <div className="flex-1 flex justify-center px-4">
            <div className="w-full max-w-[240px] h-6 rounded-md bg-muted/50 flex items-center justify-center">
              <span className="text-[11px] text-muted-foreground/50 font-medium select-none">
                your-app.com
              </span>
            </div>
          </div>
          <div className="w-[52px]" />
        </div>

        {/* Content area with CTA */}
        <div className="flex flex-col items-center justify-center py-16 px-6">
          <span className="text-[10px] uppercase tracking-[0.15em] text-muted-foreground/30 font-medium mb-4">
            Your application
          </span>

          <button
            onClick={onOpenConnect}
            disabled={isLoading}
            className={cn(
              "flex items-center gap-2.5 px-7 py-3 rounded-xl",
              "bg-primary text-primary-foreground",
              "text-sm font-semibold",
              "shadow-lg shadow-primary/20 hover:shadow-xl hover:shadow-primary/25",
              "hover:scale-[1.02] active:scale-[0.98]",
              "transition-all duration-150",
              "disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:scale-100"
            )}
          >
            {isLoading ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Plug className="h-4 w-4" />
            )}
            Connect your apps
          </button>

          <p className="text-[11px] text-muted-foreground/30 mt-3 text-center">
            Click to open the Connect modal
          </p>
        </div>
      </div>
    </div>
  );
}
