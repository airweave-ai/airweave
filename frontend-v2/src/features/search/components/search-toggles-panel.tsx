/**
 * SearchTogglesPanel - Panel containing all search toggle options
 */

import {
  ClockArrowUp,
  Filter,
  Layers,
  ListStart,
  MessageSquare,
  Settings2,
} from "lucide-react";

import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";

import type { SearchToggles } from "../types";
import { JsonFilterEditor } from "./json-filter-editor";
import { RecencyBiasSlider } from "./recency-bias-slider";
import { ToggleButton } from "./search-box-toggle";

interface SearchTogglesPanelProps {
  toggles: SearchToggles;
  onToggle: (name: keyof SearchToggles) => void;
  filterJson: string;
  onFilterChange: (value: string, isValid: boolean) => void;
  recencyBiasValue: number;
  onRecencyBiasChange: (value: number) => void;
  openTooltip: string | null;
  onMouseEnter: (id: string) => void;
  onMouseLeave: (id: string) => void;
  onContentMouseEnter: (id: string) => void;
  onContentMouseLeave: (id: string) => void;
}

export function SearchTogglesPanel({
  toggles,
  onToggle,
  filterJson,
  onFilterChange,
  recencyBiasValue,
  onRecencyBiasChange,
  openTooltip,
  onMouseEnter,
  onMouseLeave,
  onContentMouseEnter,
  onContentMouseLeave,
}: SearchTogglesPanelProps) {
  return (
    <div className="flex items-center gap-1.5">
      {/* Query Expansion */}
      <ToggleButton
        id="queryExpansion"
        icon={<Layers className="size-4" strokeWidth={1.5} />}
        isActive={toggles.queryExpansion}
        onClick={() => onToggle("queryExpansion")}
        tooltip={{
          title: "Query Expansion",
          description: "Generates similar versions of your query",
          docsUrl: "https://docs.airweave.ai/search#query-expansion",
        }}
        openTooltip={openTooltip}
        onMouseEnter={onMouseEnter}
        onMouseLeave={onMouseLeave}
        onContentMouseEnter={onContentMouseEnter}
        onContentMouseLeave={onContentMouseLeave}
      />

      {/* Filter with Editor */}
      <Tooltip open={openTooltip === "filter"}>
        <TooltipTrigger asChild>
          <div
            onMouseEnter={() => onMouseEnter("filter")}
            onMouseLeave={() => onMouseLeave("filter")}
            className={cn(
              "h-7 w-8 overflow-hidden rounded-md border p-0",
              toggles.filter ? "border-primary" : "border-border/50"
            )}
          >
            <button
              type="button"
              onClick={() => onToggle("filter")}
              className={cn(
                "flex size-full items-center justify-center rounded-md transition-all",
                toggles.filter
                  ? "text-primary hover:bg-primary/10"
                  : "text-foreground hover:bg-muted"
              )}
            >
              <Settings2 className="size-4" strokeWidth={1.5} />
            </button>
          </div>
        </TooltipTrigger>
        <TooltipContent
          side="bottom"
          className="w-[360px] max-w-[90vw]"
          onMouseEnter={() => onContentMouseEnter("filter")}
          onMouseLeave={() => onContentMouseLeave("filter")}
        >
          <div className="space-y-3">
            <div>
              <p className="font-semibold">Metadata Filtering</p>
              <p className="text-muted-foreground mt-1 text-xs">
                Filter by fields like source, status, or date before searching.
              </p>
            </div>
            <div className="space-y-2">
              <div className="text-xs font-medium text-slate-400">JSON:</div>
              <JsonFilterEditor
                value={filterJson}
                onChange={onFilterChange}
                height="160px"
              />
            </div>
            <div className="border-border border-t pt-2">
              <a
                href="https://docs.airweave.ai/search#filtering-results"
                target="_blank"
                rel="noreferrer"
                className="text-xs text-blue-400 hover:underline"
              >
                Docs
              </a>
            </div>
          </div>
        </TooltipContent>
      </Tooltip>

      {/* Query Interpretation */}
      <ToggleButton
        id="queryInterpretation"
        icon={<Filter className="size-4" strokeWidth={1.5} />}
        isActive={toggles.queryInterpretation}
        onClick={() => onToggle("queryInterpretation")}
        tooltip={{
          title: "Query Interpretation (Beta)",
          description: "Auto-extracts filters from natural language",
          docsUrl: "https://docs.airweave.ai/search#query-interpretation-beta",
        }}
        openTooltip={openTooltip}
        onMouseEnter={onMouseEnter}
        onMouseLeave={onMouseLeave}
        onContentMouseEnter={onContentMouseEnter}
        onContentMouseLeave={onContentMouseLeave}
      />

      {/* Recency Bias */}
      <Tooltip open={openTooltip === "recencyBias"}>
        <TooltipTrigger asChild>
          <div
            onMouseEnter={() => onMouseEnter("recencyBias")}
            onMouseLeave={() => onMouseLeave("recencyBias")}
            className={cn(
              "h-7 w-8 overflow-hidden rounded-md border p-0",
              toggles.recencyBias ? "border-primary" : "border-border/50"
            )}
          >
            <button
              type="button"
              onClick={() => onToggle("recencyBias")}
              className={cn(
                "flex size-full items-center justify-center rounded-md transition-all",
                toggles.recencyBias
                  ? "text-primary hover:bg-primary/10"
                  : "text-foreground hover:bg-muted"
              )}
            >
              <ClockArrowUp className="size-4" strokeWidth={1.5} />
            </button>
          </div>
        </TooltipTrigger>
        <TooltipContent
          side="bottom"
          className="w-[240px]"
          onMouseEnter={() => onContentMouseEnter("recencyBias")}
          onMouseLeave={() => onContentMouseLeave("recencyBias")}
        >
          <p className="font-semibold">Recency Bias</p>
          <p className="text-muted-foreground mb-2 text-xs">
            Prioritize recent documents
          </p>
          <div className="px-1.5 py-1">
            <RecencyBiasSlider
              value={recencyBiasValue}
              onChange={onRecencyBiasChange}
            />
          </div>
          <div className="border-border mt-2 border-t pt-2">
            <a
              href="https://docs.airweave.ai/search#recency-bias"
              target="_blank"
              rel="noreferrer"
              className="text-xs text-blue-400 hover:underline"
            >
              Docs
            </a>
          </div>
        </TooltipContent>
      </Tooltip>

      {/* Re-ranking */}
      <ToggleButton
        id="reRanking"
        icon={<ListStart className="size-4" strokeWidth={1.5} />}
        isActive={toggles.reRanking}
        onClick={() => onToggle("reRanking")}
        tooltip={{
          title: "AI Reranking",
          description: "LLM reorders results for better relevance",
          docsUrl: "https://docs.airweave.ai/search#ai-reranking",
        }}
        openTooltip={openTooltip}
        onMouseEnter={onMouseEnter}
        onMouseLeave={onMouseLeave}
        onContentMouseEnter={onContentMouseEnter}
        onContentMouseLeave={onContentMouseLeave}
      />

      {/* Answer */}
      <ToggleButton
        id="answer"
        icon={<MessageSquare className="size-4" strokeWidth={1.5} />}
        isActive={toggles.answer}
        onClick={() => onToggle("answer")}
        tooltip={{
          title: "Generate Answer",
          description: "Returns an AI-written answer",
          docsUrl: "https://docs.airweave.ai/search#generate-ai-answers",
        }}
        openTooltip={openTooltip}
        onMouseEnter={onMouseEnter}
        onMouseLeave={onMouseLeave}
        onContentMouseEnter={onContentMouseEnter}
        onContentMouseLeave={onContentMouseLeave}
      />
    </div>
  );
}
