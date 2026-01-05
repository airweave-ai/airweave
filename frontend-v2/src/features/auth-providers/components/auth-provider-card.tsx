import { Check, Plus } from "lucide-react";

import { Button } from "@/components/ui/button";
import { useIsDark } from "@/hooks/use-is-dark";
import { cn } from "@/lib/utils";

import { getAuthProviderIconUrl } from "../utils/helpers";

interface AuthProviderCardProps {
  id: string;
  name: string;
  shortName: string;
  isConnected?: boolean;
  isComingSoon?: boolean;
  onClick?: () => void;
}

export function AuthProviderCard({
  name,
  shortName,
  isConnected = false,
  isComingSoon = false,
  onClick,
}: AuthProviderCardProps) {
  const isDark = useIsDark();

  const handleClick = () => {
    if (isComingSoon) return;
    onClick?.();
  };

  const getColorClass = (name: string) => {
    const colors = [
      "bg-blue-500",
      "bg-green-500",
      "bg-purple-500",
      "bg-orange-500",
      "bg-pink-500",
      "bg-indigo-500",
      "bg-red-500",
      "bg-yellow-500",
    ];
    const index =
      name.split("").reduce((acc, char) => acc + char.charCodeAt(0), 0) %
      colors.length;
    return colors[index];
  };

  return (
    <div
      className={cn(
        "relative min-w-[150px] overflow-hidden rounded-lg border transition-all",
        isComingSoon ? "cursor-not-allowed opacity-60" : "group cursor-pointer",
        "border-border hover:border-muted-foreground/30 bg-card hover:bg-accent/50",
        isComingSoon && "hover:border-border hover:bg-card"
      )}
      onClick={handleClick}
    >
      <div className="flex items-center justify-between p-3 sm:p-4">
        <div className="flex items-center gap-3">
          {/* Auth Provider Icon */}
          <div className="flex h-9 w-9 flex-shrink-0 items-center justify-center overflow-hidden rounded-md sm:h-10 sm:w-10">
            <img
              src={getAuthProviderIconUrl(shortName, isDark ? "dark" : "light")}
              alt={`${shortName} icon`}
              className="h-8 w-8 rounded object-contain sm:h-9 sm:w-9"
              onError={(e) => {
                e.currentTarget.style.display = "none";
                const parent = e.currentTarget.parentElement;
                if (parent) {
                  parent.classList.add(getColorClass(shortName));
                  parent.innerHTML = `<span class="text-white font-semibold text-xs sm:text-sm">${shortName.substring(0, 2).toUpperCase()}</span>`;
                }
              }}
            />
          </div>

          {/* Name and status */}
          <div className="flex flex-col">
            <span className="truncate text-sm font-medium">{name}</span>
            {isComingSoon && (
              <span className="text-muted-foreground text-xs">Coming soon</span>
            )}
          </div>
        </div>

        {/* Action button */}
        {!isComingSoon && (
          <Button
            size="icon"
            variant="ghost"
            className={cn(
              "h-7 w-7 flex-shrink-0 rounded-full sm:h-8 sm:w-8",
              isConnected
                ? "bg-green-100 text-green-600 hover:bg-green-200 dark:bg-green-900/30 dark:text-green-400 dark:hover:bg-green-800/30"
                : "bg-muted text-primary hover:bg-primary/10 group-hover:bg-primary/20"
            )}
          >
            {isConnected ? (
              <Check className="h-3.5 w-3.5 sm:h-4 sm:w-4" />
            ) : (
              <Plus className="h-3.5 w-3.5 transition-transform group-hover:scale-110 sm:h-4 sm:w-4" />
            )}
          </Button>
        )}
      </div>
    </div>
  );
}
