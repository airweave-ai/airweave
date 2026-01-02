import * as React from "react";
import { createContext, useContext } from "react";

import { cn } from "@/lib/utils";

// Types
interface StepsContextValue {
  currentStep: number;
  totalSteps: number;
  goToStep: (step: number) => void;
  nextStep: () => void;
  prevStep: () => void;
  isFirstStep: boolean;
  isLastStep: boolean;
}

const StepsContext = createContext<StepsContextValue | null>(null);

function useStepsContext() {
  const context = useContext(StepsContext);
  if (!context) {
    throw new Error("Steps compound components must be used within Steps");
  }
  return context;
}

// Root Steps component
interface StepsProps {
  currentStep: number;
  onStepChange: (step: number) => void;
  totalSteps: number;
  children: React.ReactNode;
  className?: string;
}

function Steps({
  currentStep,
  onStepChange,
  totalSteps,
  children,
  className,
}: StepsProps) {
  const goToStep = (step: number) => {
    if (step >= 1 && step <= totalSteps) {
      onStepChange(step);
    }
  };

  const nextStep = () => goToStep(currentStep + 1);
  const prevStep = () => goToStep(currentStep - 1);

  return (
    <StepsContext.Provider
      value={{
        currentStep,
        totalSteps,
        goToStep,
        nextStep,
        prevStep,
        isFirstStep: currentStep === 1,
        isLastStep: currentStep === totalSteps,
      }}
    >
      <div className={cn("w-full", className)}>{children}</div>
    </StepsContext.Provider>
  );
}

// Progress indicator (dots style)
interface StepsIndicatorProps {
  className?: string;
}

function StepsIndicator({ className }: StepsIndicatorProps) {
  const { currentStep, totalSteps } = useStepsContext();

  return (
    <div className={cn("flex items-center gap-2", className)}>
      {Array.from({ length: totalSteps }, (_, i) => {
        const stepNumber = i + 1;
        const isCompleted = stepNumber < currentStep;
        const isCurrent = stepNumber === currentStep;

        return (
          <div
            key={i}
            className={cn(
              "h-1.5 rounded-full transition-all duration-300",
              isCompleted
                ? "bg-primary w-6"
                : isCurrent
                  ? "bg-primary w-12"
                  : "bg-muted w-6"
            )}
          />
        );
      })}
    </div>
  );
}

// Step counter text
interface StepsCounterProps {
  className?: string;
}

function StepsCounter({ className }: StepsCounterProps) {
  const { currentStep, totalSteps } = useStepsContext();

  return (
    <span className={cn("text-muted-foreground text-sm", className)}>
      Step {currentStep} of {totalSteps}
    </span>
  );
}

// Step content container with transition
interface StepContentProps {
  step: number;
  children: React.ReactNode;
  className?: string;
}

function StepContent({ step, children, className }: StepContentProps) {
  const { currentStep } = useStepsContext();

  if (step !== currentStep) return null;

  return (
    <div
      className={cn(
        "animate-in fade-in-0 slide-in-from-right-4 duration-300",
        className
      )}
    >
      {children}
    </div>
  );
}

// Navigation buttons container
interface StepsNavigationProps {
  children: React.ReactNode;
  className?: string;
}

function StepsNavigation({ children, className }: StepsNavigationProps) {
  return (
    <div
      className={cn("flex items-center justify-between", className)}
    >
      {children}
    </div>
  );
}

// Export hook for consuming context
export { useStepsContext };

// Attach sub-components
Steps.Indicator = StepsIndicator;
Steps.Counter = StepsCounter;
Steps.Content = StepContent;
Steps.Navigation = StepsNavigation;

export { Steps };
export type { StepsProps };

