import { Plus } from "lucide-react";
import { Button } from "../components/ui/button";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "../components/ui/tooltip";
import type { ComponentPreviewConfig } from "./types";

export const tooltipPreview: ComponentPreviewConfig = {
  variants: [
    {
      title: "Default",
      description: "A simple tooltip that appears on hover",
      preview: (
        <Tooltip>
          <TooltipTrigger asChild>
            <Button variant="outline">Hover me</Button>
          </TooltipTrigger>
          <TooltipContent>
            <p>This is a tooltip</p>
          </TooltipContent>
        </Tooltip>
      ),
      code: `<Tooltip>
  <TooltipTrigger asChild>
    <Button variant="outline">Hover me</Button>
  </TooltipTrigger>
  <TooltipContent>
    <p>This is a tooltip</p>
  </TooltipContent>
</Tooltip>`,
    },
    {
      title: "Positions",
      description: "Tooltips can appear on different sides of the trigger",
      preview: (
        <div className="flex gap-4">
          <Tooltip>
            <TooltipTrigger asChild>
              <Button variant="outline" size="sm">
                Top
              </Button>
            </TooltipTrigger>
            <TooltipContent side="top">
              <p>Top tooltip</p>
            </TooltipContent>
          </Tooltip>
          <Tooltip>
            <TooltipTrigger asChild>
              <Button variant="outline" size="sm">
                Right
              </Button>
            </TooltipTrigger>
            <TooltipContent side="right">
              <p>Right tooltip</p>
            </TooltipContent>
          </Tooltip>
          <Tooltip>
            <TooltipTrigger asChild>
              <Button variant="outline" size="sm">
                Bottom
              </Button>
            </TooltipTrigger>
            <TooltipContent side="bottom">
              <p>Bottom tooltip</p>
            </TooltipContent>
          </Tooltip>
          <Tooltip>
            <TooltipTrigger asChild>
              <Button variant="outline" size="sm">
                Left
              </Button>
            </TooltipTrigger>
            <TooltipContent side="left">
              <p>Left tooltip</p>
            </TooltipContent>
          </Tooltip>
        </div>
      ),
      code: `<Tooltip>
  <TooltipTrigger asChild>
    <Button variant="outline">Top</Button>
  </TooltipTrigger>
  <TooltipContent side="top">
    <p>Top tooltip</p>
  </TooltipContent>
</Tooltip>

<Tooltip>
  <TooltipTrigger asChild>
    <Button variant="outline">Right</Button>
  </TooltipTrigger>
  <TooltipContent side="right">
    <p>Right tooltip</p>
  </TooltipContent>
</Tooltip>`,
    },
    {
      title: "With Icon Button",
      description: "Tooltips are commonly used to describe icon-only buttons",
      preview: (
        <Tooltip>
          <TooltipTrigger asChild>
            <Button variant="outline" size="icon">
              <Plus className="h-4 w-4" />
            </Button>
          </TooltipTrigger>
          <TooltipContent>
            <p>Add item</p>
          </TooltipContent>
        </Tooltip>
      ),
      code: `<Tooltip>
  <TooltipTrigger asChild>
    <Button variant="outline" size="icon">
      <Plus className="h-4 w-4" />
    </Button>
  </TooltipTrigger>
  <TooltipContent>
    <p>Add item</p>
  </TooltipContent>
</Tooltip>`,
    },
  ],
};
