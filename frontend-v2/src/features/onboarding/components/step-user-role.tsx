import { cn } from "@/lib/utils";

import { USER_ROLES } from "../utils/constants";

interface StepUserRoleProps {
  value: string;
  onChange: (value: string) => void;
}

export function StepUserRole({ value, onChange }: StepUserRoleProps) {
  return (
    <div className="space-y-8">
      <div className="space-y-2">
        <h2 className="text-2xl font-normal">What's your role?</h2>
        <p className="text-muted-foreground">
          We'll customize your experience based on your needs
        </p>
      </div>

      <div className="grid grid-cols-3 gap-3">
        {USER_ROLES.map((role) => {
          const Icon = role.icon;
          return (
            <button
              key={role.value}
              type="button"
              onClick={() => onChange(role.value)}
              className={cn(
                "group rounded-lg border p-6 text-center transition-all",
                "hover:border-primary/50",
                value === role.value
                  ? "border-primary bg-primary/5"
                  : "border-border"
              )}
            >
              <Icon
                className={cn(
                  "mx-auto mb-3 h-8 w-8 transition-colors",
                  value === role.value
                    ? "text-primary"
                    : "text-muted-foreground group-hover:text-foreground"
                )}
              />
              <div className="text-sm">{role.label}</div>
            </button>
          );
        })}
      </div>
    </div>
  );
}

