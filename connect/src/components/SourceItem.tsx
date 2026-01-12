import type { Source } from "../lib/types";
import { AppIcon } from "./AppIcon";

interface SourceItemProps {
  source: Source;
  onClick: () => void;
}

export function SourceItem({ source, onClick }: SourceItemProps) {
  return (
    <button
      onClick={onClick}
      className="flex items-center gap-3 p-2 rounded-lg w-full text-left transition-colors duration-150 cursor-pointer border-none [background-color:var(--connect-surface)] [border:1px_solid_var(--connect-border)] hover:brightness-95"
    >
      <AppIcon shortName={source.short_name} name={source.name} />
      <p
        className="font-medium text-sm truncate w-full"
        style={{ color: "var(--connect-text)" }}
      >
        {source.name}
      </p>
    </button>
  );
}
