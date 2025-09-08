import React from 'react';
import { AlertCircle, RefreshCw } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';

interface SyncErrorBannerProps {
  error: string | undefined;
  onRetry: () => void;
  isRetrying?: boolean;
  isDark: boolean;
}

export const SyncErrorBanner: React.FC<SyncErrorBannerProps> = ({
  error,
  onRetry,
  isRetrying = false,
  isDark
}) => {
  if (!error) return null;

  return (
    <div className={cn(
      "rounded-lg border-2 p-4 mb-4",
      isDark
        ? "bg-red-900/20 border-red-800/50"
        : "bg-red-50 border-red-200"
    )}>
      <div className="flex items-start gap-3">
        <AlertCircle className={cn(
          "h-5 w-5 mt-0.5 flex-shrink-0",
          isDark ? "text-red-400" : "text-red-600"
        )} />

        <div className="flex-1 space-y-2">
          <div className="flex items-center justify-between">
            <h4 className={cn(
              "font-medium",
              isDark ? "text-red-300" : "text-red-900"
            )}>
              401 Unauthorized Error
            </h4>
            <span className={cn(
              "text-xs uppercase tracking-wider font-medium",
              isDark ? "text-red-400" : "text-red-600"
            )}>
              Error
            </span>
          </div>

          <p className={cn(
            "text-sm",
            isDark ? "text-red-200/80" : "text-red-800"
          )}>
            {error}
          </p>

          <Button
            onClick={onRetry}
            variant="outline"
            size="sm"
            disabled={isRetrying}
            className={cn(
              "mt-2",
              isDark
                ? "border-red-700 text-red-300 hover:bg-red-900/30"
                : "border-red-300 text-red-700 hover:bg-red-100"
            )}
          >
            <RefreshCw className={cn(
              "h-3.5 w-3.5 mr-1.5",
              isRetrying && "animate-spin"
            )} />
            {isRetrying ? 'Retrying...' : 'Retry Sync'}
          </Button>
        </div>
      </div>
    </div>
  );
};
