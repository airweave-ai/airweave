import {
  Avatar,
  AvatarFallback,
  AvatarImage,
} from "../components/ui/avatar";
import type { ComponentPreviewConfig } from "./types";

export const avatarPreview: ComponentPreviewConfig = {
  variants: [
    {
      title: "Default",
      description: "Avatar with an image and fallback initials",
      preview: (
        <Avatar>
          <AvatarImage src="https://github.com/shadcn.png" alt="@shadcn" />
          <AvatarFallback>CN</AvatarFallback>
        </Avatar>
      ),
      code: `<Avatar>
  <AvatarImage src="https://github.com/shadcn.png" alt="@shadcn" />
  <AvatarFallback>CN</AvatarFallback>
</Avatar>`,
    },
    {
      title: "Fallback States",
      description: "Avatar displays fallback content when image fails to load",
      preview: (
        <div className="flex items-center gap-4">
          <Avatar>
            <AvatarImage src="https://github.com/shadcn.png" alt="@shadcn" />
            <AvatarFallback>CN</AvatarFallback>
          </Avatar>
          <Avatar>
            <AvatarFallback>JD</AvatarFallback>
          </Avatar>
          <Avatar>
            <AvatarFallback>AB</AvatarFallback>
          </Avatar>
        </div>
      ),
      code: `{/* With image */}
<Avatar>
  <AvatarImage src="https://github.com/shadcn.png" alt="@shadcn" />
  <AvatarFallback>CN</AvatarFallback>
</Avatar>

{/* Fallback only */}
<Avatar>
  <AvatarFallback>JD</AvatarFallback>
</Avatar>`,
    },
    {
      title: "Sizes",
      description: "Avatars can be sized using className",
      preview: (
        <div className="flex items-center gap-4">
          <Avatar className="size-6">
            <AvatarFallback className="text-xs">SM</AvatarFallback>
          </Avatar>
          <Avatar>
            <AvatarFallback>MD</AvatarFallback>
          </Avatar>
          <Avatar className="size-12">
            <AvatarFallback>LG</AvatarFallback>
          </Avatar>
          <Avatar className="size-16">
            <AvatarFallback className="text-lg">XL</AvatarFallback>
          </Avatar>
        </div>
      ),
      code: `<Avatar className="size-6">
  <AvatarFallback className="text-xs">SM</AvatarFallback>
</Avatar>
<Avatar>
  <AvatarFallback>MD</AvatarFallback>
</Avatar>
<Avatar className="size-12">
  <AvatarFallback>LG</AvatarFallback>
</Avatar>
<Avatar className="size-16">
  <AvatarFallback className="text-lg">XL</AvatarFallback>
</Avatar>`,
    },
  ],
};

