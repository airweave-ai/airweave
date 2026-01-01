import { Package } from "lucide-react";
import { Button } from "../components/ui/button";
import type { ComponentPreviewConfig } from "./types";

export const buttonPreview: ComponentPreviewConfig = {
  variants: [
    {
      title: "Default Variants",
      description: "The button component supports multiple visual variants",
      preview: (
        <>
          <Button variant="default">Default</Button>
          <Button variant="secondary">Secondary</Button>
          <Button variant="destructive">Destructive</Button>
          <Button variant="outline">Outline</Button>
          <Button variant="ghost">Ghost</Button>
          <Button variant="link">Link</Button>
        </>
      ),
      code: `<Button variant="default">Default</Button>
<Button variant="secondary">Secondary</Button>
<Button variant="destructive">Destructive</Button>
<Button variant="outline">Outline</Button>
<Button variant="ghost">Ghost</Button>
<Button variant="link">Link</Button>`,
    },
    {
      title: "Sizes",
      description: "Buttons come in different sizes for various use cases",
      preview: (
        <>
          <Button size="sm">Small</Button>
          <Button size="default">Default</Button>
          <Button size="lg">Large</Button>
          <Button size="icon">
            <Package className="w-4 h-4" />
          </Button>
        </>
      ),
      code: `<Button size="sm">Small</Button>
<Button size="default">Default</Button>
<Button size="lg">Large</Button>
<Button size="icon"><Icon /></Button>`,
    },
    {
      title: "States",
      description: "Buttons can be disabled or used as child components",
      preview: (
        <>
          <Button disabled>Disabled</Button>
          <Button asChild>
            <a href="#">As Link</a>
          </Button>
        </>
      ),
      code: `<Button disabled>Disabled</Button>
<Button asChild>
  <a href="#">As Link</a>
</Button>`,
    },
  ],
};

