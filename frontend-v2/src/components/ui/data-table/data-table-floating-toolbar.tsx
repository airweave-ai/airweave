"use client";

import { X } from "lucide-react";
import type { LucideIcon } from "lucide-react";

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
    <div className="fixed bottom-6 left-1/2 -translate-x-1/2 z-50 animate-in slide-in-from-bottom-4 fade-in duration-200">
      <div className="flex items-center gap-3 rounded-lg border bg-background px-4 py-3 shadow-lg">
        <span className="text-sm font-medium text-muted-foreground">
          {selectedCount} selected
        </span>
        <div className="h-4 w-px bg-border" />
        {actions.map((action) => {
          const buttonVariant =
            action.variant === "destructive"
              ? "ghost"
              : action.variant ?? "ghost";

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
        <div className="h-4 w-px bg-border" />
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

