import { Button } from "@/components/ui/button";
import { Plus } from "lucide-react";
import { getAppIconUrl } from "@/lib/utils/icons";
import { useTheme } from "@/lib/theme-provider";
import { cn } from "@/lib/utils";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { SingleActionCheckResponse } from "@/types";

interface SourceButtonProps {
  id: string;
  name: string;
  shortName: string;
  onClick?: () => void;
  disabled?: boolean;
  usageCheckDetails?: {
    source_connections?: SingleActionCheckResponse | null;
    entities?: SingleActionCheckResponse | null;
  };
}

export const SourceButton = ({ id, name, shortName, onClick, disabled, usageCheckDetails }: SourceButtonProps) => {
  const { resolvedTheme } = useTheme();
  const isDark = resolvedTheme === 'dark';

  // Get color class based on shortName
  const getColorClass = (shortName: string) => {
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

    // Hash the short name to get a consistent color
    const index = shortName.split("").reduce((acc, char) => acc + char.charCodeAt(0), 0) % colors.length;
    return colors[index];
  };

  // Source icon component
  const SourceIcon = () => (
    <div className="flex items-center justify-center w-8 h-8 sm:w-9 sm:h-9 md:w-10 md:h-10 overflow-hidden rounded-md flex-shrink-0">
      <img
        src={getAppIconUrl(shortName, resolvedTheme)}
        alt={`${shortName} icon`}
        className="w-7 h-7 sm:w-8 sm:h-8 md:w-9 md:h-9 object-contain"
        onError={(e) => {
          // Fallback to initials if icon fails to load
          e.currentTarget.style.display = 'none';
          const parent = e.currentTarget.parentElement!;
          parent.classList.add(getColorClass(shortName));

          // Create span element safely without innerHTML to prevent XSS
          const span = document.createElement('span');
          span.className = 'text-white font-semibold text-xs sm:text-sm';
          span.textContent = shortName.substring(0, 2).toUpperCase();
          parent.appendChild(span);
        }}
      />
    </div>
  );

  // Determine which action is blocking and get tooltip content
  const getTooltipContent = () => {
    if (!usageCheckDetails || !disabled) return null;

    const { source_connections, entities } = usageCheckDetails;

    if (source_connections && !source_connections.allowed && source_connections.reason === 'usage_limit_exceeded') {
      return (
        <>
          Source connection limit reached.{' '}
          <a
            href="/organization/settings?tab=billing"
            className="underline"
            onClick={(e) => e.stopPropagation()}
          >
            Upgrade your plan
          </a>
          {' '}for more connections.
        </>
      );
    } else if (entities && !entities.allowed && entities.reason === 'usage_limit_exceeded') {
      return (
        <>
          Entity processing limit reached.{' '}
          <a
            href="/organization/settings?tab=billing"
            className="underline"
            onClick={(e) => e.stopPropagation()}
          >
            Upgrade your plan
          </a>
          {' '}to process more data.
        </>
      );
    }

    return 'Unable to create collection at this time.';
  };

  const tooltipContent = getTooltipContent();

  const buttonContent = (
    <div
      className={cn(
        "border rounded-lg overflow-hidden group transition-all min-w-[150px]",
        disabled
          ? isDark
            ? "border-gray-800 bg-gray-900/30 opacity-50 cursor-not-allowed"
            : "border-gray-200 bg-white/50 opacity-50 cursor-not-allowed"
          : isDark
            ? "border-gray-800 hover:border-gray-700 bg-gray-900/50 hover:bg-gray-900 cursor-pointer"
            : "border-gray-200 hover:border-gray-300 bg-white hover:bg-gray-50 cursor-pointer"
      )}
      onClick={disabled ? undefined : onClick}
    >
      <div className="p-2 sm:p-3 md:p-4 flex items-center justify-between">
        <div className="flex items-center gap-2 sm:gap-3">
          <SourceIcon />
          <span className={cn(
            "text-xs sm:text-sm font-medium truncate",
            disabled && "text-muted-foreground"
          )}>{name}</span>
        </div>
        <Button
          size="icon"
          variant="ghost"
          disabled={disabled}
          className={cn(
            "h-6 w-6 sm:h-7 sm:w-7 md:h-8 md:w-8 rounded-full flex-shrink-0",
            disabled
              ? isDark
                ? "bg-gray-800/50 text-gray-500 cursor-not-allowed"
                : "bg-gray-100/50 text-gray-400 cursor-not-allowed"
              : isDark
                ? "bg-gray-800/80 text-blue-400 hover:bg-blue-600/20 hover:text-blue-300 group-hover:bg-blue-600/30"
                : "bg-gray-100/80 text-blue-500 hover:bg-blue-100 hover:text-blue-600 group-hover:bg-blue-100/80"
          )}
        >
          <Plus className="h-3 w-3 sm:h-3.5 sm:w-3.5 md:h-4 md:w-4 group-hover:h-4 group-hover:w-4 sm:group-hover:h-4.5 sm:group-hover:w-4.5 md:group-hover:h-5 md:group-hover:w-5 transition-all" />
        </Button>
      </div>
    </div>
  );

  if (disabled && tooltipContent) {
    return (
      <TooltipProvider delayDuration={100}>
        <Tooltip>
          <TooltipTrigger asChild>
            <span tabIndex={0} className="w-full">
              {buttonContent}
            </span>
          </TooltipTrigger>
          <TooltipContent className="max-w-xs">
            <p className="text-xs">{tooltipContent}</p>
          </TooltipContent>
        </Tooltip>
      </TooltipProvider>
    );
  }

  return buttonContent;
};

export default SourceButton;
