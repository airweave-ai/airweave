import { cn } from "@/lib/utils";

import { ORGANIZATION_TYPES } from "../utils/constants";

interface StepOrgTypeProps {
  value: string;
  onChange: (value: string) => void;
}

export function StepOrgType({ value, onChange }: StepOrgTypeProps) {
  return (
    <div className="space-y-8">
      <div className="space-y-2">
        <h2 className="text-2xl font-normal">What type of company are you?</h2>
        <p className="text-muted-foreground">
          This helps us understand your data integration needs
        </p>
      </div>

      <div className="grid grid-cols-2 gap-4">
        {ORGANIZATION_TYPES.map((type) => {
          const Icon = type.icon;
          return (
            <button
              key={type.value}
              type="button"
              onClick={() => onChange(type.value)}
              className={cn(
                "group rounded-lg border p-6 text-left transition-all",
                "hover:border-primary/50",
                value === type.value
                  ? "border-primary bg-primary/5"
                  : "border-border"
              )}
            >
              <div className="flex items-start space-x-4">
                <Icon
                  className={cn(
                    "mt-0.5 h-6 w-6 flex-shrink-0 transition-colors",
                    value === type.value
                      ? "text-primary"
                      : "text-muted-foreground group-hover:text-foreground"
                  )}
                />
                <div>
                  <div className="mb-1 font-medium">{type.label}</div>
                  <div className="text-muted-foreground text-xs">
                    {type.description}
                  </div>
                </div>
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}

