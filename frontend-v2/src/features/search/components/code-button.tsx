/**
 * CodeButton - Button to open API integration code modal
 */

import { CodeXml } from "lucide-react";

import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";

interface CodeButtonProps {
  onClick: () => void;
}

export function CodeButton({ onClick }: CodeButtonProps) {
  return (
    <TooltipProvider delayDuration={0}>
      <Tooltip>
        <TooltipTrigger asChild>
          <button
            type="button"
            onClick={onClick}
            className="absolute top-2 right-2 z-20 flex size-8 items-center justify-center rounded-md border border-dashed border-blue-500/30 bg-blue-500/10 shadow-sm transition-all hover:border-blue-400/40 hover:bg-blue-500/15"
            title="View integration code"
          >
            <CodeXml className="size-4 text-blue-400" />
          </button>
        </TooltipTrigger>
        <TooltipContent side="left" sideOffset={8}>
          <p className="font-semibold">Call the Search API</p>
          <p className="text-muted-foreground text-xs">
            Open a ready-to-use snippet for JS or Python.
          </p>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}
