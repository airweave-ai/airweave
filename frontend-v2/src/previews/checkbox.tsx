import { Checkbox } from "../components/ui/checkbox";
import type { ComponentPreviewConfig } from "./types";

export const checkboxPreview: ComponentPreviewConfig = {
  variants: [
    {
      title: "Default",
      description: "A basic checkbox that can be checked or unchecked",
      preview: (
        <div className="flex items-center space-x-2">
          <Checkbox id="terms" />
          <label
            htmlFor="terms"
            className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70"
          >
            Accept terms and conditions
          </label>
        </div>
      ),
      code: `<div className="flex items-center space-x-2">
  <Checkbox id="terms" />
  <label htmlFor="terms" className="text-sm font-medium">
    Accept terms and conditions
  </label>
</div>`,
    },
    {
      title: "States",
      description: "Checkbox in different states: unchecked, checked, and disabled",
      preview: (
        <div className="flex flex-col gap-4">
          <div className="flex items-center space-x-2">
            <Checkbox id="unchecked" />
            <label htmlFor="unchecked" className="text-sm">
              Unchecked
            </label>
          </div>
          <div className="flex items-center space-x-2">
            <Checkbox id="checked" defaultChecked />
            <label htmlFor="checked" className="text-sm">
              Checked
            </label>
          </div>
          <div className="flex items-center space-x-2">
            <Checkbox id="disabled" disabled />
            <label htmlFor="disabled" className="text-sm opacity-50">
              Disabled
            </label>
          </div>
          <div className="flex items-center space-x-2">
            <Checkbox id="disabled-checked" disabled defaultChecked />
            <label htmlFor="disabled-checked" className="text-sm opacity-50">
              Disabled Checked
            </label>
          </div>
        </div>
      ),
      code: `<Checkbox id="unchecked" />
<Checkbox id="checked" defaultChecked />
<Checkbox id="disabled" disabled />
<Checkbox id="disabled-checked" disabled defaultChecked />`,
    },
    {
      title: "Indeterminate",
      description: "Checkbox with indeterminate state for partial selections",
      preview: (
        <div className="flex items-center space-x-2">
          <Checkbox id="indeterminate" indeterminate />
          <label htmlFor="indeterminate" className="text-sm">
            Select all (partial)
          </label>
        </div>
      ),
      code: `<Checkbox id="indeterminate" indeterminate />`,
    },
  ],
};

