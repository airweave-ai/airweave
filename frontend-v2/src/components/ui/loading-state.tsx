import { Loader2 } from "lucide-react";

import { cn } from "@/lib/utils";

interface LoadingStateProps {
  /** Optional message to display below the spinner */
  message?: string;
  /** Additional CSS classes */
  className?: string;
  /** Size variant */
  size?: "sm" | "md" | "lg";
}

/**
 * Reusable loading state component with spinner and optional message.
 */
export function LoadingState({
  message,
  className,
  size = "md",
}: LoadingStateProps) {
  const sizeClasses = {
    sm: "size-4",
    md: "size-6",
    lg: "size-8",
  };

  const paddingClasses = {
    sm: "py-8",
    md: "py-20",
    lg: "py-32",
  };

  return (
    <div
      className={cn(
        "flex items-center justify-center",
        paddingClasses[size],
        className
      )}
    >
      <div className="flex flex-col items-center gap-3">
        <Loader2
          className={cn(
            "text-muted-foreground animate-spin",
            sizeClasses[size]
          )}
        />
        {message && <p className="text-muted-foreground text-sm">{message}</p>}
      </div>
    </div>
  );
}
