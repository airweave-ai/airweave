/**
 * ResultScoreBadge - Displays result ranking and similarity score
 */

import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";

interface ScoreDisplay {
  value: string;
  color: "green" | "yellow" | "gray";
}

interface ResultScoreBadgeProps {
  index: number;
  score?: number;
}

function getScoreDisplay(score: number | undefined): ScoreDisplay | null {
  if (score === undefined) return null;

  const isNormalizedScore = score >= 0 && score <= 1;

  if (isNormalizedScore) {
    return {
      value: `${(score * 100).toFixed(1)}%`,
      color: score >= 0.7 ? "green" : score >= 0.5 ? "yellow" : "gray",
    };
  }

  return {
    value: score.toFixed(3),
    color: score >= 10 ? "green" : score >= 5 ? "yellow" : "gray",
  };
}

export function ResultScoreBadge({ index, score }: ResultScoreBadgeProps) {
  const scoreDisplay = getScoreDisplay(score);

  if (!scoreDisplay) return null;

  const isNormalizedScore = score !== undefined && score >= 0 && score <= 1;

  return (
    <TooltipProvider delayDuration={200}>
      <Tooltip>
        <TooltipTrigger asChild>
          <div
            className={cn(
              "flex flex-shrink-0 cursor-help items-center gap-2 rounded-full px-3 py-1 text-[11px] font-semibold whitespace-nowrap shadow-sm transition-all duration-200 hover:shadow-md",
              scoreDisplay.color === "green" &&
                "border-emerald-200 bg-emerald-50 text-emerald-700 hover:bg-emerald-100 dark:border-emerald-500/30 dark:bg-emerald-500/15 dark:text-emerald-400 dark:hover:bg-emerald-500/20",
              scoreDisplay.color === "yellow" &&
                "border-amber-200 bg-amber-50 text-amber-700 hover:bg-amber-100 dark:border-amber-500/30 dark:bg-amber-500/15 dark:text-amber-400 dark:hover:bg-amber-500/20",
              scoreDisplay.color === "gray" &&
                "hover:bg-gray-150 border-gray-300 bg-gray-100 text-gray-600 dark:border-gray-600/50 dark:bg-gray-700/40 dark:text-gray-400 dark:hover:bg-gray-700/50"
            )}
          >
            <span className="font-bold tracking-wider opacity-70">
              #{index + 1}
            </span>
            <div className="h-3 w-px opacity-30 dark:bg-gray-400" />
            <span className="font-mono tracking-tight">
              {scoreDisplay.value}
            </span>
          </div>
        </TooltipTrigger>
        <TooltipContent side="left">
          <div className="space-y-2">
            <div className="text-[11px] font-bold tracking-wide">
              Result #{index + 1}
            </div>
            <div className="text-[12px]">
              <span className="font-medium">Similarity:</span>{" "}
              <span className="font-semibold">
                {isNormalizedScore
                  ? `${(score! * 100).toFixed(1)}%`
                  : score!.toFixed(3)}
              </span>
            </div>
            <div className="bg-border h-px w-full" />
            <div className="text-muted-foreground text-[11px] leading-relaxed">
              Position determined by semantic reranking.
            </div>
          </div>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}
