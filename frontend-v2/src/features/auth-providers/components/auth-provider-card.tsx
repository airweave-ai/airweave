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

  // Get color class based on shortName for fallback
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
        "border rounded-lg overflow-hidden transition-all min-w-[150px] relative",
        isComingSoon ? "cursor-not-allowed opacity-60" : "cursor-pointer group",
        "border-border hover:border-muted-foreground/30 bg-card hover:bg-accent/50",
        isComingSoon && "hover:border-border hover:bg-card",
      )}
      onClick={handleClick}
    >
      <div className="p-3 sm:p-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          {/* Auth Provider Icon */}
          <div className="flex items-center justify-center w-9 h-9 sm:w-10 sm:h-10 overflow-hidden rounded-md flex-shrink-0">
            <img
              src={getAuthProviderIconUrl(shortName, isDark ? "dark" : "light")}
              alt={`${shortName} icon`}
              className="w-8 h-8 sm:w-9 sm:h-9 object-contain rounded"
              onError={(e) => {
                // Fallback to initials if icon fails to load
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
            <span className="text-sm font-medium truncate">{name}</span>
            {isComingSoon && (
              <span className="text-xs text-muted-foreground">Coming soon</span>
            )}
          </div>
        </div>

        {/* Action button */}
        {!isComingSoon && (
          <Button
            size="icon"
            variant="ghost"
            className={cn(
              "h-7 w-7 sm:h-8 sm:w-8 rounded-full flex-shrink-0",
              isConnected
                ? "bg-green-100 dark:bg-green-900/30 text-green-600 dark:text-green-400 hover:bg-green-200 dark:hover:bg-green-800/30"
                : "bg-muted text-primary hover:bg-primary/10 group-hover:bg-primary/20",
            )}
          >
            {isConnected ? (
              <Check className="h-3.5 w-3.5 sm:h-4 sm:w-4" />
            ) : (
              <Plus className="h-3.5 w-3.5 sm:h-4 sm:w-4 group-hover:scale-110 transition-transform" />
            )}
          </Button>
        )}
      </div>
    </div>
  );
}
