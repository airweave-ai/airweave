/**
 * SearchMethodSelector - Selector for hybrid/neural/keyword search methods
 */

import { ChartScatter, GitMerge, Type } from "lucide-react";

import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";

import type { SearchMethod } from "../types";

interface MethodConfig {
  id: SearchMethod;
  icon: React.ReactNode;
  title: string;
  description: string;
}

const METHODS: MethodConfig[] = [
  {
    id: "hybrid",
    icon: <GitMerge className="size-4" strokeWidth={1.5} />,
    title: "Hybrid Search",
    description: "Combines semantic and keyword signals",
  },
  {
    id: "neural",
    icon: <ChartScatter className="size-4" strokeWidth={1.5} />,
    title: "Neural Search",
    description: "Pure semantic matching using embeddings",
  },
  {
    id: "keyword",
    icon: <Type className="size-4" strokeWidth={1.5} />,
    title: "Keyword Search",
    description: "BM25 keyword matching",
  },
];

interface SearchMethodSelectorProps {
  value: SearchMethod;
  onChange: (method: SearchMethod) => void;
  openTooltip: string | null;
  onMouseEnter: (id: string) => void;
  onMouseLeave: (id: string) => void;
  onContentMouseEnter: (id: string) => void;
  onContentMouseLeave: (id: string) => void;
}

export function SearchMethodSelector({
  value,
  onChange,
  openTooltip,
  onMouseEnter,
  onMouseLeave,
  onContentMouseEnter,
  onContentMouseLeave,
}: SearchMethodSelectorProps) {
  return (
    <div className="inline-block h-7">
      <div className="bg-background relative grid h-full grid-cols-3 items-stretch gap-0.5 overflow-hidden rounded-md border p-0.5">
        {METHODS.map((method) => (
          <Tooltip key={method.id} open={openTooltip === method.id}>
            <TooltipTrigger asChild>
              <button
                type="button"
                onClick={() => onChange(method.id)}
                onMouseEnter={() => onMouseEnter(method.id)}
                onMouseLeave={() => onMouseLeave(method.id)}
                className={cn(
                  "flex aspect-square h-full items-center justify-center rounded-md border transition-all",
                  value === method.id
                    ? "border-primary text-primary"
                    : "text-foreground hover:bg-muted border-transparent"
                )}
              >
                {method.icon}
              </button>
            </TooltipTrigger>
            <TooltipContent
              side="bottom"
              onMouseEnter={() => onContentMouseEnter(method.id)}
              onMouseLeave={() => onContentMouseLeave(method.id)}
            >
              <p className="font-semibold">{method.title}</p>
              <p className="text-muted-foreground text-xs">
                {method.description}
              </p>
              <div className="border-border mt-2 border-t pt-2">
                <a
                  href="https://docs.airweave.ai/search#search-method"
                  target="_blank"
                  rel="noreferrer"
                  className="text-xs text-blue-400 hover:underline"
                >
                  Docs
                </a>
              </div>
            </TooltipContent>
          </Tooltip>
        ))}
      </div>
    </div>
  );
}
