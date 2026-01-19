import { Separator } from "../components/ui/separator";
import type { ComponentPreviewConfig } from "./types";

export const separatorPreview: ComponentPreviewConfig = {
  variants: [
    {
      title: "Horizontal",
      description: "A horizontal separator dividing content vertically",
      preview: (
        <div className="w-full max-w-md">
          <div className="space-y-1">
            <h4 className="text-sm leading-none font-medium">
              Radix Primitives
            </h4>
            <p className="text-muted-foreground text-sm">
              An open-source UI component library.
            </p>
          </div>
          <Separator className="my-4" />
          <div className="flex h-5 items-center space-x-4 text-sm">
            <div>Blog</div>
            <Separator orientation="vertical" />
            <div>Docs</div>
            <Separator orientation="vertical" />
            <div>Source</div>
          </div>
        </div>
      ),
      code: `<div className="space-y-1">
  <h4 className="text-sm font-medium">Radix Primitives</h4>
  <p className="text-sm text-muted-foreground">
    An open-source UI component library.
  </p>
</div>
<Separator className="my-4" />
<div className="flex h-5 items-center space-x-4 text-sm">
  <div>Blog</div>
  <Separator orientation="vertical" />
  <div>Docs</div>
  <Separator orientation="vertical" />
  <div>Source</div>
</div>`,
    },
    {
      title: "Vertical",
      description: "A vertical separator dividing content horizontally",
      preview: (
        <div className="flex h-12 items-center space-x-4">
          <span className="text-sm">Item One</span>
          <Separator orientation="vertical" />
          <span className="text-sm">Item Two</span>
          <Separator orientation="vertical" />
          <span className="text-sm">Item Three</span>
        </div>
      ),
      code: `<div className="flex h-12 items-center space-x-4">
  <span className="text-sm">Item One</span>
  <Separator orientation="vertical" />
  <span className="text-sm">Item Two</span>
  <Separator orientation="vertical" />
  <span className="text-sm">Item Three</span>
</div>`,
    },
  ],
};
