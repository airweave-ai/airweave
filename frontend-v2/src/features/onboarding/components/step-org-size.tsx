import { cn } from "@/lib/utils";

import { ORGANIZATION_SIZES } from "../utils/constants";

interface StepOrgSizeProps {
  value: string;
  onChange: (value: string) => void;
}

export function StepOrgSize({ value, onChange }: StepOrgSizeProps) {
  return (
    <div className="space-y-8">
      <div className="space-y-2">
        <h2 className="text-2xl font-normal">
          How many people are in your organization?
        </h2>
        <p className="text-muted-foreground">
          This helps us recommend the right plan
        </p>
      </div>

      <div className="grid grid-cols-3 gap-3">
        {ORGANIZATION_SIZES.map((size) => (
          <button
            key={size.value}
            type="button"
            onClick={() => onChange(size.value)}
            className={cn(
              "rounded-lg border p-6 text-center transition-all",
              "hover:border-primary/50",
              value === size.value
                ? "border-primary bg-primary/5"
                : "border-border"
            )}
          >
            <div className="mb-1 text-2xl font-light">{size.label}</div>
            <div className="text-muted-foreground text-xs">
              {size.description}
            </div>
          </button>
        ))}
      </div>
    </div>
  );
}
