import { Button } from "@/components/ui/button";
import { Eye, Plus } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { getAppIconUrl } from "@/lib/utils/icons";
import { useTheme } from "@/lib/theme-provider";
import { cn } from "@/lib/utils";
import { StatusBadge } from "@/components/ui/StatusBadge";
import type { SourceConnectionSummary } from "@/lib/stores/collections";

interface CollectionCardProps {
  id: string;
  name: string;
  readableId: string;
  status?: string;
  sourceConnectionSummaries?: SourceConnectionSummary[];
  onClick?: () => void;
}

export const CollectionCard = ({
  id,
  name,
  readableId,
  status = "active",
  sourceConnectionSummaries = [],
  onClick,
}: CollectionCardProps) => {
  const navigate = useNavigate();
  const { resolvedTheme } = useTheme();

  const handleClick = () => {
    if (onClick) {
      onClick();
    } else {
      navigate(`/collections/${readableId}`);
    }
  };

  const handleViewClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    navigate(`/collections/${readableId}`);
  };

  return (
    <div
      className={cn(
        "relative rounded-xl overflow-hidden cursor-pointer min-w-[240px] h-full",
        "border border-slate-200 dark:border-slate-800",
        "bg-white dark:bg-slate-900",
        "hover:border-slate-300 dark:hover:border-slate-700 transition-colors"
      )}
      onClick={handleClick}
    >
      {/* Card Content */}
      <div className="relative h-full flex flex-col">
        {/* Card Header */}
        <div className="p-4 flex-1">
          <div className="flex justify-between items-start mb-2">
            <h3 className="text-xl font-semibold tracking-tight text-slate-900 dark:text-white">
              {name}
            </h3>
          </div>
          <p className="text-sm text-slate-500 dark:text-slate-400 mb-3 truncate">
            {readableId}.airweave.ai
          </p>

          {/* Status badge */}
          <StatusBadge status={status} showTooltip={true} tooltipContext="collection" />
        </div>

        {/* Card Footer */}
        <div className="border-t border-slate-100 dark:border-slate-800 p-2 flex justify-between items-center">
          {/* View & Edit Button */}
          <Button
            variant="ghost"
            size="sm"
            className="text-slate-700 dark:text-slate-300 hover:text-slate-900 dark:hover:text-white hover:bg-slate-100 dark:hover:bg-slate-800 rounded-lg text-sm"
            onClick={handleViewClick}
          >
            <Eye className="h-4 w-4 mr-1.5" />
            View & edit
          </Button>

          {/* Source connection icons */}
          {sourceConnectionSummaries.length > 0 ? (
            sourceConnectionSummaries.length === 1 ? (
              <div className="flex items-center justify-center">
                <div className="h-10 w-10 rounded-lg bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 p-1 flex items-center justify-center overflow-hidden">
                  <img
                    src={getAppIconUrl(sourceConnectionSummaries[0].short_name, resolvedTheme)}
                    alt={sourceConnectionSummaries[0].name}
                    className="h-full w-full object-contain"
                  />
                </div>
              </div>
            ) : (
              <div className="flex items-center">
                <div className="flex -space-x-2">
                  {sourceConnectionSummaries.slice(0, 2).map((connection, index) => (
                    <div
                      key={`${connection.short_name}-${index}`}
                      className="h-10 w-10 rounded-lg bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 p-1.5 flex items-center justify-center overflow-hidden"
                      style={{ zIndex: 2 - index }}
                    >
                      <img
                        src={getAppIconUrl(connection.short_name, resolvedTheme)}
                        alt={connection.name}
                        className="h-full w-full object-contain"
                      />
                    </div>
                  ))}
                </div>
                {sourceConnectionSummaries.length > 2 && (
                  <div className="ml-1 text-xs font-medium text-slate-500 dark:text-slate-400">
                    +{sourceConnectionSummaries.length - 2}
                  </div>
                )}
              </div>
            )
          ) : (
            <div className="h-10 w-10 rounded-lg bg-slate-100 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 p-2 flex items-center justify-center">
              <Plus className="h-full w-full text-slate-400" />
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default CollectionCard;
