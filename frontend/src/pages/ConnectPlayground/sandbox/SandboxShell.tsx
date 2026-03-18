import {
  Plug,
  Loader2,
  ChevronLeft,
  ChevronRight,
  RotateCw,
  Lock,
  Share,
  Plus,
} from "lucide-react";
import { cn } from "@/lib/utils";

interface SandboxShellProps {
  onOpenConnect: () => void;
  isLoading: boolean;
}

function BarButton({ children }: { children: React.ReactNode }) {
  return (
    <div className="w-5 h-5 flex items-center justify-center rounded text-foreground/20">
      {children}
    </div>
  );
}

export function SandboxShell({ onOpenConnect, isLoading }: SandboxShellProps) {
  return (
    <div className="h-full flex items-center justify-center">
      {/* Browser frame */}
      <div className="w-full max-w-[240px] rounded-lg border border-border/60 shadow-sm overflow-hidden">
        {/* Tab bar */}
        <div className="flex items-center gap-1.5 px-2.5 pt-2 pb-0 bg-muted/80">
          <div className="flex gap-1 shrink-0 pl-0.5">
            <div className="w-2.5 h-2.5 rounded-full bg-[#ff5f57]" />
            <div className="w-2.5 h-2.5 rounded-full bg-[#febc2e]" />
            <div className="w-2.5 h-2.5 rounded-full bg-[#28c840]" />
          </div>
          {/* Active tab */}
          <div className="flex items-center gap-1.5 px-2.5 py-1 bg-muted rounded-t-md min-w-0 max-w-[160px]">
            <div className="w-3 h-3 rounded bg-primary/30 flex items-center justify-center shrink-0">
              <span className="text-[6px] font-bold text-primary">A</span>
            </div>
            <span className="text-[10px] text-foreground/50 font-medium truncate select-none">
              Your App
            </span>
          </div>
          <BarButton><Plus className="h-2.5 w-2.5" /></BarButton>
        </div>

        {/* Toolbar */}
        <div className="flex items-center gap-0.5 px-2 py-1 bg-muted border-b border-border/40">
          <BarButton><ChevronLeft className="h-3 w-3" /></BarButton>
          <BarButton><ChevronRight className="h-3 w-3" /></BarButton>
          <BarButton><RotateCw className="h-2.5 w-2.5" /></BarButton>
          {/* Address bar */}
          <div className="flex-1 flex items-center justify-center gap-1 h-5 rounded bg-background px-2 mx-0.5 border border-border/30">
            <Lock className="h-2 w-2 text-foreground/25 shrink-0" />
            <span className="text-[9px] text-foreground/40 font-medium select-none truncate">
              your-app.com
            </span>
          </div>
          <BarButton><Share className="h-2.5 w-2.5" /></BarButton>
        </div>

        {/* Content area with CTA */}
        <div className="flex flex-col items-center justify-center py-7 px-4 bg-background">
          <span className="text-[9px] uppercase tracking-[0.15em] text-foreground/20 font-medium mb-3">
            Your application
          </span>

          <button
            onClick={onOpenConnect}
            disabled={isLoading}
            className={cn(
              "flex items-center gap-2 px-5 py-2 rounded-lg",
              "bg-primary text-primary-foreground",
              "text-xs font-semibold",
              "shadow-md shadow-primary/20 hover:shadow-lg hover:shadow-primary/25",
              "hover:scale-[1.02] active:scale-[0.98]",
              "transition-all duration-150",
              "disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:scale-100",
            )}
          >
            {isLoading ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
            ) : (
              <Plug className="h-3.5 w-3.5" />
            )}
            Connect your apps
          </button>

          <p className="text-[10px] text-foreground/20 mt-2 text-center">
            Click to open the Connect modal
          </p>
        </div>
      </div>
    </div>
  );
}
