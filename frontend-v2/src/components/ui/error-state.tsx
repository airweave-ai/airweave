import { AlertCircle } from "lucide-react";

import { cn } from "@/lib/utils";

interface ErrorStateProps {
  /** Error message or Error object */
  error: Error | string;
  /** Optional title */
  title?: string;
  /** Additional CSS classes */
  className?: string;
}

/**
 * Reusable error state component for displaying error messages.
 */
export function ErrorState({ error, title, className }: ErrorStateProps) {
  const message = error instanceof Error ? error.message : error;

  return (
    <div
      className={cn(
        "rounded-lg border border-red-200 bg-red-50 px-4 py-3 dark:border-red-900/50 dark:bg-red-900/10",
        className
      )}
    >
      <div className="flex items-start gap-3">
        <AlertCircle className="mt-0.5 size-5 shrink-0 text-red-600 dark:text-red-400" />
        <div className="space-y-1">
          {title && (
            <p className="text-sm font-medium text-red-700 dark:text-red-300">
              {title}
            </p>
          )}
          <p className="text-sm text-red-600 dark:text-red-400">{message}</p>
        </div>
      </div>
    </div>
  );
}
