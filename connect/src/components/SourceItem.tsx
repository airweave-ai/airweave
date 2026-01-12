import { useState } from "react";
import { getAppIconUrl } from "../lib/icons";
import { useTheme } from "../lib/theme";
import type { Source } from "../lib/types";

interface SourceItemProps {
  source: Source;
  onClick: () => void;
}

export function SourceItem({ source, onClick }: SourceItemProps) {
  const { resolvedMode } = useTheme();
  const [imgError, setImgError] = useState(false);

  return (
    <button
      onClick={onClick}
      className="flex items-center gap-3 p-2 rounded-lg w-full text-left transition-colors duration-150 cursor-pointer border-none"
      style={{
        backgroundColor: "var(--connect-surface)",
        border: "1px solid var(--connect-border)",
      }}
      onMouseEnter={(e) => {
        e.currentTarget.style.backgroundColor =
          "color-mix(in srgb, var(--connect-surface) 80%, var(--connect-primary) 20%)";
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.backgroundColor = "var(--connect-surface)";
      }}
    >
      {imgError ? (
        <div
          className="size-8 rounded-lg flex items-center justify-center text-sm font-medium uppercase"
          style={{
            backgroundColor:
              "color-mix(in srgb, var(--connect-primary) 20%, transparent)",
            color: "var(--connect-primary)",
          }}
        >
          {source.short_name.slice(0, 2)}
        </div>
      ) : (
        <img
          src={getAppIconUrl(source.short_name, resolvedMode)}
          alt={source.name}
          className="size-8 object-contain"
          onError={() => setImgError(true)}
        />
      )}
      <p
        className="font-medium text-sm truncate w-full"
        style={{ color: "var(--connect-text)" }}
      >
        {source.name}
      </p>
    </button>
  );
}
