/**
 * CollectionHeader - Header section with title, icons, and action buttons
 */

import { Check, Copy, Pencil, RotateCw, Trash } from "lucide-react";
import { useCallback, useRef, useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";

import { getAppIconUrl } from "../utils/helpers";
import { StatusBadge } from "./status-badge";
import type { SourceConnection } from "@/lib/api";

interface Collection {
  name: string;
  readable_id: string;
  status?: string;
}

interface CollectionHeaderProps {
  collection: Collection;
  sourceConnections: SourceConnection[];
  onReload: () => void;
  onDelete: () => void;
  onSaveName?: (newName: string) => Promise<void>;
}

export function CollectionHeader({
  collection,
  sourceConnections,
  onReload,
  onDelete,
  onSaveName,
}: CollectionHeaderProps) {
  const [isEditingName, setIsEditingName] = useState(false);
  const [isCopied, setIsCopied] = useState(false);
  const nameInputRef = useRef<HTMLDivElement>(null);

  const startEditingName = useCallback(() => {
    setIsEditingName(true);
    setTimeout(() => {
      if (nameInputRef.current && collection) {
        nameInputRef.current.innerText = collection.name;
        const range = document.createRange();
        const selection = window.getSelection();
        const textNode =
          nameInputRef.current.firstChild || nameInputRef.current;
        const textLength = nameInputRef.current.innerText.length;
        range.setStart(textNode, textLength);
        range.setEnd(textNode, textLength);
        if (selection) {
          selection.removeAllRanges();
          selection.addRange(range);
        }
        nameInputRef.current.focus();
      }
    }, 0);
  }, [collection]);

  const handleSaveNameChange = useCallback(async () => {
    const newName = nameInputRef.current?.innerText.trim() || "";
    if (!newName || newName === collection?.name) {
      setIsEditingName(false);
      return;
    }

    try {
      await onSaveName?.(newName);
      setIsEditingName(false);
      toast.success("Collection name updated");
    } catch {
      toast.error("Failed to update collection name");
      setIsEditingName(false);
    }
  }, [collection, onSaveName]);

  const handleCopyId = useCallback(() => {
    if (collection?.readable_id) {
      navigator.clipboard.writeText(collection.readable_id);
      setIsCopied(true);
      setTimeout(() => setIsCopied(false), 1500);
      toast.success("ID copied to clipboard");
    }
  }, [collection]);

  return (
    <div className="flex w-full items-center justify-between py-4">
      <div className="flex items-center gap-3">
        {/* Source Icons */}
        <div
          className="flex items-center justify-start"
          style={{ minWidth: "3.5rem" }}
        >
          {sourceConnections.slice(0, 3).map((connection, index) => (
            <div
              key={connection.id}
              className="bg-background flex size-12 items-center justify-center overflow-hidden rounded-md border p-1"
              style={{
                marginLeft: index > 0 ? `-${Math.min(index * 8, 24)}px` : "0px",
                zIndex: 3 - index,
              }}
            >
              <img
                src={getAppIconUrl(connection.short_name)}
                alt={connection.name}
                className="size-auto max-h-full max-w-full object-contain"
              />
            </div>
          ))}
          {sourceConnections.length > 3 && (
            <div className="text-muted-foreground ml-2 text-sm font-medium">
              +{sourceConnections.length - 3}
            </div>
          )}
        </div>

        <div className="flex flex-col justify-center">
          {isEditingName ? (
            <div className="flex items-center gap-2">
              <div
                ref={nameInputRef}
                contentEditable
                className="text-foreground border-border/40 rounded border p-1 pr-3 pl-0 text-3xl font-bold tracking-tight transition-all duration-150 outline-none"
                onKeyDown={(e) => {
                  if (e.key === "Enter") {
                    e.preventDefault();
                    handleSaveNameChange();
                  }
                  if (e.key === "Escape") {
                    e.preventDefault();
                    setIsEditingName(false);
                  }
                }}
                onBlur={handleSaveNameChange}
              />
            </div>
          ) : (
            <div className="flex items-center gap-2">
              <h1 className="text-foreground py-1 pl-0 text-2xl font-bold tracking-tight">
                {collection.name}
              </h1>
              <Button
                variant="ghost"
                size="icon"
                className="text-muted-foreground hover:text-foreground size-6"
                onClick={startEditingName}
              >
                <Pencil className="size-3" />
              </Button>
              {collection.status && <StatusBadge status={collection.status} />}
            </div>
          )}
          <p className="text-muted-foreground group relative flex items-center text-sm">
            {collection.readable_id}
            <button
              className="ml-1.5 opacity-0 transition-opacity group-hover:opacity-100 focus:opacity-100 focus:outline-none"
              onClick={handleCopyId}
              title="Copy ID"
            >
              {isCopied ? (
                <Check className="text-muted-foreground size-3.5 transition-all" />
              ) : (
                <Copy className="text-muted-foreground size-3.5 transition-all" />
              )}
            </button>
          </p>
        </div>
      </div>

      {/* Header action buttons */}
      <div className="flex items-center gap-1.5">
        <TooltipProvider>
          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                variant="outline"
                size="icon"
                className="size-8"
                onClick={onReload}
              >
                <RotateCw className="size-3" />
              </Button>
            </TooltipTrigger>
            <TooltipContent>
              <p>Reload page</p>
            </TooltipContent>
          </Tooltip>
        </TooltipProvider>

        <TooltipProvider>
          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                variant="outline"
                size="icon"
                className="size-8"
                onClick={onDelete}
              >
                <Trash className="size-3" />
              </Button>
            </TooltipTrigger>
            <TooltipContent>
              <p>Delete collection</p>
            </TooltipContent>
          </Tooltip>
        </TooltipProvider>
      </div>
    </div>
  );
}
