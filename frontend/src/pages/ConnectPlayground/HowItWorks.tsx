import { ChevronRight } from "lucide-react";

const STEPS = [
  {
    number: 1,
    title: "Create a session",
    description: "Server calls the API to get a token",
  },
  {
    number: 2,
    title: "Open the widget",
    description: "Frontend launches Connect",
  },
  {
    number: 3,
    title: "Users connect apps",
    description: "Auth and sync happen automatically",
  },
];

export function HowItWorks() {
  return (
    <div className="flex items-center gap-1">
      {STEPS.map((step, i) => (
        <div key={step.number} className="flex items-center gap-1 flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-1 min-w-0 px-2.5 py-1.5 rounded-md bg-muted/40">
            <span className="shrink-0 w-4 h-4 rounded-full bg-primary/10 text-primary flex items-center justify-center text-[9px] font-bold">
              {step.number}
            </span>
            <div className="min-w-0">
              <span className="text-[10px] font-medium text-foreground leading-none">
                {step.title}
              </span>
              <p className="text-[9px] leading-tight text-muted-foreground/60 truncate">
                {step.description}
              </p>
            </div>
          </div>
          {i < STEPS.length - 1 && (
            <ChevronRight className="h-2.5 w-2.5 text-muted-foreground/20 shrink-0" />
          )}
        </div>
      ))}
    </div>
  );
}
