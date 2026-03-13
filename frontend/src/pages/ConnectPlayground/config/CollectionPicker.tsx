import { Plus } from "lucide-react";
import { cn } from "@/lib/utils";

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
  return (
    <div className="relative">
      <select
        value={isNew ? "__new__" : selected}
        onChange={(e) => {
          if (e.target.value === "__new__") {
            onSelectNew();
          } else {
            onSelect(e.target.value);
          }
        }}
        className={cn(
          "h-8 pl-3 pr-8 text-[11px] font-medium rounded-lg border border-border/30 bg-background text-foreground",
          "focus:outline-none focus:ring-1 focus:ring-primary/20",
          "appearance-none cursor-pointer",
          isNew && "text-primary"
        )}
        style={{
          backgroundImage: `url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 24 24' fill='none' stroke='%236b7280' stroke-width='2'%3E%3Cpath d='M6 9l6 6 6-6'/%3E%3C/svg%3E")`,
          backgroundRepeat: "no-repeat",
          backgroundPosition: "right 8px center",
        }}
      >
        <option value="__new__">+ New collection</option>
        {collections.map((c) => (
          <option key={c.readable_id} value={c.readable_id}>
            {c.name || c.readable_id}
          </option>
        ))}
      </select>
    </div>
  );
}
