import { Skeleton } from "../components/ui/skeleton";
import type { ComponentPreviewConfig } from "./types";

export const skeletonPreview: ComponentPreviewConfig = {
  variants: [
    {
      title: "Default",
      description: "Basic skeleton shapes for loading states",
      preview: (
        <div className="flex items-center space-x-4">
          <Skeleton className="h-12 w-12 rounded-full" />
          <div className="space-y-2">
            <Skeleton className="h-4 w-[250px]" />
            <Skeleton className="h-4 w-[200px]" />
          </div>
        </div>
      ),
      code: `<div className="flex items-center space-x-4">
  <Skeleton className="h-12 w-12 rounded-full" />
  <div className="space-y-2">
    <Skeleton className="h-4 w-[250px]" />
    <Skeleton className="h-4 w-[200px]" />
  </div>
</div>`,
    },
    {
      title: "Card",
      description: "Skeleton layout for a card component",
      preview: (
        <div className="flex flex-col space-y-3">
          <Skeleton className="h-[125px] w-[250px] rounded-xl" />
          <div className="space-y-2">
            <Skeleton className="h-4 w-[250px]" />
            <Skeleton className="h-4 w-[200px]" />
          </div>
        </div>
      ),
      code: `<div className="flex flex-col space-y-3">
  <Skeleton className="h-[125px] w-[250px] rounded-xl" />
  <div className="space-y-2">
    <Skeleton className="h-4 w-[250px]" />
    <Skeleton className="h-4 w-[200px]" />
  </div>
</div>`,
    },
    {
      title: "Text Lines",
      description: "Skeleton for text content loading",
      preview: (
        <div className="w-full max-w-md space-y-3">
          <Skeleton className="h-4 w-full" />
          <Skeleton className="h-4 w-full" />
          <Skeleton className="h-4 w-3/4" />
        </div>
      ),
      code: `<div className="space-y-3">
  <Skeleton className="h-4 w-full" />
  <Skeleton className="h-4 w-full" />
  <Skeleton className="h-4 w-3/4" />
</div>`,
    },
    {
      title: "Avatar with Details",
      description: "Common pattern for user profile loading states",
      preview: (
        <div className="flex flex-col gap-4">
          <div className="flex items-center gap-3">
            <Skeleton className="h-10 w-10 rounded-full" />
            <div className="space-y-1.5">
              <Skeleton className="h-3 w-24" />
              <Skeleton className="h-3 w-32" />
            </div>
          </div>
          <div className="flex items-center gap-3">
            <Skeleton className="h-14 w-14 rounded-lg" />
            <div className="space-y-1.5">
              <Skeleton className="h-4 w-28" />
              <Skeleton className="h-3 w-40" />
            </div>
          </div>
        </div>
      ),
      code: `{/* Small avatar */}
<div className="flex items-center gap-3">
  <Skeleton className="h-10 w-10 rounded-full" />
  <div className="space-y-1.5">
    <Skeleton className="h-3 w-24" />
    <Skeleton className="h-3 w-32" />
  </div>
</div>

{/* Large avatar */}
<div className="flex items-center gap-3">
  <Skeleton className="h-14 w-14 rounded-lg" />
  <div className="space-y-1.5">
    <Skeleton className="h-4 w-28" />
    <Skeleton className="h-3 w-40" />
  </div>
</div>`,
    },
  ],
};
