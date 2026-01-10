import type { LucideIcon } from "lucide-react";
import { X } from "lucide-react";

import { Button } from "@/components/ui/button";

export interface FloatingToolbarAction {
  id: string;
  label: string;
  icon?: LucideIcon;
  variant?: "default" | "destructive" | "ghost";
  onClick: () => void;
}

interface DataTableFloatingToolbarProps {
  /** Number of selected items */
  selectedCount: number;
  /** Actions to display in the toolbar */
  actions: FloatingToolbarAction[];
  /** Callback to clear selection */
  onClearSelection: () => void;
  /** Optional children to render after actions */
  children?: React.ReactNode;
}

export function DataTableFloatingToolbar({
  selectedCount,
  actions,
  onClearSelection,
  children,
}: DataTableFloatingToolbarProps) {
  if (selectedCount === 0) return null;

  return (
    <div className="animate-in slide-in-from-bottom-4 fade-in fixed bottom-6 left-1/2 z-50 -translate-x-1/2 duration-200">
      <div className="bg-background flex items-center gap-3 rounded-lg border px-4 py-3 shadow-lg">
        <span className="text-muted-foreground text-sm font-medium">
          {selectedCount} selected
        </span>
        <div className="bg-border h-4 w-px" />
        {actions.map((action) => {
          const buttonVariant =
            action.variant === "destructive"
              ? "ghost"
              : (action.variant ?? "ghost");

          return (
            <Button
              key={action.id}
              variant={buttonVariant}
              size="sm"
              onClick={action.onClick}
              className={
                action.variant === "destructive"
                  ? "text-destructive hover:text-destructive hover:bg-destructive/10"
                  : undefined
              }
            >
              {action.icon && <action.icon className="mr-2 size-4" />}
              {action.label}
            </Button>
          );
        })}
        {children}
        <div className="bg-border h-4 w-px" />
        <Button
          variant="ghost"
          size="icon"
          className="size-8"
          onClick={onClearSelection}
        >
          <X className="size-4" />
          <span className="sr-only">Clear selection</span>
        </Button>
      </div>
    </div>
  );
}
