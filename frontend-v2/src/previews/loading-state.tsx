import { LoadingState } from "../components/ui/loading-state";
import type { ComponentPreviewConfig } from "./types";

export const loadingStatePreview: ComponentPreviewConfig = {
  variants: [
    {
      title: "Size Variants",
      description: "Loading spinners come in different sizes",
      preview: (
        <div className="flex items-start gap-8">
          <div className="text-center">
            <LoadingState size="sm" />
            <p className="text-xs text-muted-foreground mt-2">Small</p>
          </div>
          <div className="text-center">
            <LoadingState size="md" />
            <p className="text-xs text-muted-foreground mt-2">Medium</p>
          </div>
          <div className="text-center">
            <LoadingState size="lg" />
            <p className="text-xs text-muted-foreground mt-2">Large</p>
          </div>
        </div>
      ),
      code: `<LoadingState size="sm" />
<LoadingState size="md" />
<LoadingState size="lg" />`,
    },
    {
      title: "With Message",
      description: "Loading state with a descriptive message",
      preview: (
        <LoadingState size="md" message="Loading your data..." />
      ),
      code: `<LoadingState size="md" message="Loading your data..." />`,
    },
    {
      title: "Custom Message",
      description: "Different contextual loading messages",
      preview: (
        <div className="flex flex-col gap-4">
          <LoadingState size="sm" message="Fetching results..." />
          <LoadingState size="sm" message="Syncing data..." />
          <LoadingState size="sm" message="Processing request..." />
        </div>
      ),
      code: `<LoadingState size="sm" message="Fetching results..." />
<LoadingState size="sm" message="Syncing data..." />
<LoadingState size="sm" message="Processing request..." />`,
    },
  ],
};

