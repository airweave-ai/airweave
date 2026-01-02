import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";

interface StepOrgNameProps {
  value: string;
  onChange: (value: string) => void;
  onKeyPress?: (e: React.KeyboardEvent) => void;
}

export function StepOrgName({ value, onChange, onKeyPress }: StepOrgNameProps) {
  return (
    <div className="space-y-8">
      <div className="space-y-2">
        <h2 className="text-2xl font-normal">
          What should we call your organization?
        </h2>
        <p className="text-muted-foreground">
          Choose a name that represents your team or company
        </p>
      </div>

      <div className="space-y-3">
        <Input
          type="text"
          placeholder="e.g., Acme AI"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          onKeyDown={onKeyPress}
          className={cn(
            "w-full px-4 py-3 text-lg",
            "placeholder:text-muted-foreground/50"
          )}
          autoFocus
        />
        <p className="text-muted-foreground text-xs">
          Use letters, numbers, spaces, hyphens, and underscores only - You can
          always change this later
        </p>
      </div>
    </div>
  );
}
