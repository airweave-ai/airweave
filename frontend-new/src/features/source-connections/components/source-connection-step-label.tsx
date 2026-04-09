export interface SourceConnectionStepLabelProps {
  label: string;
  numberOfSteps: number;
  step: number;
}

export function SourceConnectionStepLabel({
  label,
  numberOfSteps,
  step,
}: SourceConnectionStepLabelProps) {
  return (
    <span className="font-mono text-sm text-foreground/60">
      Step {step}{' '}
      <span className="text-foreground/40">
        of {numberOfSteps}: {label}
      </span>
    </span>
  );
}
