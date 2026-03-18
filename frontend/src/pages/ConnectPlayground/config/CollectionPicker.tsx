import { ChevronDown, Database, Plus } from "lucide-react";
import { cn } from "@/lib/utils";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";

interface Collection {
  readable_id: string;
  name: string;
}

interface CollectionPickerProps {
  collections: Collection[];
  selected: string;
  isNew: boolean;
  onSelect: (readableId: string) => void;
  onSelectNew: () => void;
}

export function CollectionPicker({
  collections,
  selected,
  isNew,
  onSelect,
  onSelectNew,
}: CollectionPickerProps) {
  const current = collections.find((c) => c.readable_id === selected);
  const displayName = isNew
    ? "New collection"
    : current?.name || current?.readable_id || "Select collection";

  return (
    <TooltipProvider delayDuration={300}>
      <Tooltip>
        <DropdownMenu>
          <TooltipTrigger asChild>
            <DropdownMenuTrigger asChild>
              <button
                className={cn(
                  "flex items-center gap-1.5 h-8 pl-3 pr-2.5 rounded-full text-xs font-medium transition-colors",
                  "bg-primary/10 text-primary hover:bg-primary/15",
                )}
              >
                <Database className="h-3 w-3" />
                <span className="max-w-[140px] truncate">{displayName}</span>
                <ChevronDown className="h-3 w-3 opacity-60" />
              </button>
            </DropdownMenuTrigger>
          </TooltipTrigger>
          <TooltipContent side="bottom" className="max-w-[260px] p-3">
            <div className="space-y-1.5">
              <p className="font-medium text-popover-foreground text-xs">What is a collection?</p>
              <p className="text-[11px] text-muted-foreground leading-relaxed">
                Collections group synced data from your users' connected apps. Each Connect session is scoped to one collection.
              </p>
            </div>
          </TooltipContent>
          <DropdownMenuContent align="end" className="w-52">
            <DropdownMenuItem
              onClick={onSelectNew}
              className={cn("text-xs gap-2", isNew && "bg-accent")}
            >
              <Plus className="h-3 w-3" />
              New collection
            </DropdownMenuItem>
            {collections.length > 0 && <DropdownMenuSeparator />}
            {collections.map((c) => (
              <DropdownMenuItem
                key={c.readable_id}
                onClick={() => onSelect(c.readable_id)}
                className={cn(
                  "text-xs gap-2",
                  !isNew && selected === c.readable_id && "bg-accent",
                )}
              >
                <Database className="h-3 w-3 opacity-40" />
                <span className="truncate">{c.name || c.readable_id}</span>
              </DropdownMenuItem>
            ))}
          </DropdownMenuContent>
        </DropdownMenu>
      </Tooltip>
    </TooltipProvider>
  );
}
