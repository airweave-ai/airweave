import { useState } from "react";
import { getAppIconUrl } from "../lib/icons";
import { useTheme } from "../lib/theme";

interface AppIconProps {
  shortName: string;
  name: string;
  className?: string;
}

export function AppIcon({ shortName, name, className = "size-8" }: AppIconProps) {
  const { resolvedMode } = useTheme();
  const [imgError, setImgError] = useState(false);

  if (imgError) {
    return (
      <div
        className={`${className} rounded-lg flex items-center justify-center text-sm font-medium uppercase`}
        style={{
          backgroundColor:
            "color-mix(in srgb, var(--connect-primary) 20%, transparent)",
          color: "var(--connect-primary)",
        }}
      >
        {shortName.slice(0, 2)}
      </div>
    );
  }

  return (
    <img
      src={getAppIconUrl(shortName, resolvedMode)}
      alt={name}
      className={`${className} object-contain`}
      onError={() => setImgError(true)}
    />
  );
}
