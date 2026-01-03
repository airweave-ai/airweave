import { Input } from "../components/ui/input";
import type { ComponentPreviewConfig } from "./types";

export const inputPreview: ComponentPreviewConfig = {
  variants: [
    {
      title: "Default",
      description: "A standard text input field",
      preview: (
        <div className="w-full max-w-sm">
          <Input type="text" placeholder="Enter text..." />
        </div>
      ),
      code: `<Input type="text" placeholder="Enter text..." />`,
    },
    {
      title: "Input Types",
      description: "Different input types for various data",
      preview: (
        <div className="flex w-full max-w-sm flex-col gap-3">
          <Input type="email" placeholder="Email address" />
          <Input type="password" placeholder="Password" />
          <Input type="number" placeholder="Number" />
          <Input type="search" placeholder="Search..." />
        </div>
      ),
      code: `<Input type="email" placeholder="Email address" />
<Input type="password" placeholder="Password" />
<Input type="number" placeholder="Number" />
<Input type="search" placeholder="Search..." />`,
    },
    {
      title: "States",
      description: "Disabled and file input states",
      preview: (
        <div className="flex w-full max-w-sm flex-col gap-3">
          <Input disabled placeholder="Disabled input" />
          <Input type="file" />
        </div>
      ),
      code: `<Input disabled placeholder="Disabled input" />
<Input type="file" />`,
    },
    {
      title: "With Label",
      description: "Input paired with a label for accessibility",
      preview: (
        <div className="flex w-full max-w-sm flex-col gap-2">
          <label htmlFor="email" className="text-sm font-medium">
            Email
          </label>
          <Input id="email" type="email" placeholder="you@example.com" />
        </div>
      ),
      code: `<div className="flex flex-col gap-2">
  <label htmlFor="email" className="text-sm font-medium">
    Email
  </label>
  <Input id="email" type="email" placeholder="you@example.com" />
</div>`,
    },
  ],
};
