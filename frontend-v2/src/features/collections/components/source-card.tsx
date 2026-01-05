import { useIsDark } from "@/hooks/use-is-dark";
import { cn } from "@/lib/utils";

import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { getAppIconUrl } from "../utils/helpers";

interface SourceCardProps {
  id: string;
  name: string;
  shortName: string;
  onClick?: () => void;
  disabled?: boolean;
}

export function SourceCard({
  name,
  shortName,
  onClick,
  disabled = false,
}: SourceCardProps) {
  const isDark = useIsDark();

  return (
    <div
      className={cn(
        "group border-border/50 flex items-center justify-center gap-2 overflow-hidden rounded-lg border px-3 py-1.5 shadow-xs transition-all",
        disabled
          ? "bg-card/50 cursor-not-allowed opacity-50"
          : "bg-card hover:bg-card/50 hover:border-border cursor-pointer"
      )}
      onClick={disabled ? undefined : onClick}
    >
      <SourceIcon shortName={shortName} isDark={isDark} />
      <div
        className={cn(
          "truncate text-xs font-medium",
          disabled && "text-muted-foreground"
        )}
      >
        {name}
      </div>
    </div>
  );
}

interface SourceIconProps {
  shortName: string;
  isDark: boolean;
}

function SourceIcon({ shortName, isDark }: SourceIconProps) {
  return (
    <Avatar className="size-6 rounded">
      <AvatarImage
        src={getAppIconUrl(shortName, isDark ? "dark" : "light")}
        alt={`${shortName} icon`}
      />
      <AvatarFallback className="rounded text-xs font-semibold">
        {shortName[0].toUpperCase()}
      </AvatarFallback>
    </Avatar>
  );
}
