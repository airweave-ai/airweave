import { SourceCard } from "./source-card";

interface Source {
  id: string;
  name: string;
  short_name: string;
}

interface SourcesGridProps {
  sources: Source[];
  onSourceClick: (source: Source) => void;
  title?: string;
}

export function SourcesGrid({
  sources,
  onSourceClick,
  title = "Start with a source",
}: SourcesGridProps) {
  if (sources.length === 0) {
    return null;
  }

  return (
    <div>
      <h2 className="text-muted-foreground mb-4 font-mono font-medium uppercase opacity-70">
        {title}
      </h2>
      <div className="flex flex-wrap gap-3">
        {sources.map((source) => (
          <SourceCard
            key={source.id}
            id={source.id}
            name={source.name}
            shortName={source.short_name}
            onClick={() => onSourceClick(source)}
          />
        ))}
      </div>
    </div>
  );
}
