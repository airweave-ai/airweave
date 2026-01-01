"use client";

import { type Row } from "@tanstack/react-table";
import { MoreHorizontal } from "lucide-react";
import type { LucideIcon } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

export interface RowAction<TData> {
  id: string;
  label: string;
  icon?: LucideIcon;
  variant?: "default" | "destructive";
  onSelect: (row: Row<TData>) => void;
  separator?: boolean;
}

interface DataTableRowActionsProps<TData> {
  row: Row<TData>;
  actions: RowAction<TData>[];
}

export function DataTableRowActions<TData>({
  row,
  actions,
}: DataTableRowActionsProps<TData>) {
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button
          variant="ghost"
          size="icon"
          className="size-8 text-muted-foreground"
        >
          <MoreHorizontal className="size-4" />
          <span className="sr-only">Open menu</span>
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        {actions.map((action, index) => (
          <div key={action.id}>
            {action.separator && index > 0 && <DropdownMenuSeparator />}
            <DropdownMenuItem
              variant={action.variant}
              onClick={() => action.onSelect(row)}
            >
              {action.icon && <action.icon className="mr-2 size-4" />}
              {action.label}
            </DropdownMenuItem>
          </div>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

