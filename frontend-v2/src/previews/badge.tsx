import { Badge } from "../components/ui/badge";
import type { ComponentPreviewConfig } from "./types";

export const badgePreview: ComponentPreviewConfig = {
  variants: [
    {
      title: "Default Variants",
      description:
        "Badges come in different visual styles for various contexts",
      preview: (
        <div className="flex flex-wrap items-center gap-2">
          <Badge variant="default">Default</Badge>
          <Badge variant="secondary">Secondary</Badge>
          <Badge variant="destructive">Destructive</Badge>
          <Badge variant="outline">Outline</Badge>
        </div>
      ),
      code: `<Badge variant="default">Default</Badge>
<Badge variant="secondary">Secondary</Badge>
<Badge variant="destructive">Destructive</Badge>
<Badge variant="outline">Outline</Badge>`,
    },
    {
      title: "With Icons",
      description: "Badges can include icons alongside text",
      preview: (
        <div className="flex flex-wrap items-center gap-2">
          <Badge>
            <svg
              className="size-3"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M5 13l4 4L19 7"
              />
            </svg>
            Verified
          </Badge>
          <Badge variant="secondary">
            <svg
              className="size-3"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"
              />
            </svg>
            Pending
          </Badge>
          <Badge variant="destructive">
            <svg
              className="size-3"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M6 18L18 6M6 6l12 12"
              />
            </svg>
            Error
          </Badge>
        </div>
      ),
      code: `<Badge>
  <CheckIcon className="size-3" />
  Verified
</Badge>
<Badge variant="secondary">
  <ClockIcon className="size-3" />
  Pending
</Badge>
<Badge variant="destructive">
  <XIcon className="size-3" />
  Error
</Badge>`,
    },
    {
      title: "As Link",
      description: "Badges can be rendered as links using asChild",
      preview: (
        <div className="flex items-center gap-2">
          <Badge asChild>
            <a href="#">Clickable</a>
          </Badge>
          <Badge variant="outline" asChild>
            <a href="#">Link Badge</a>
          </Badge>
        </div>
      ),
      code: `<Badge asChild>
  <a href="#">Clickable</a>
</Badge>
<Badge variant="outline" asChild>
  <a href="#">Link Badge</a>
</Badge>`,
    },
  ],
};
