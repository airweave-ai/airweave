import React, { useState } from 'react';
import { toast } from 'sonner';
import { Copy, ArrowRight, Loader2 } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useTheme } from '@/lib/theme-provider';
import { getAppIconUrl } from '@/lib/utils/icons';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import '@/styles/connection-animation.css';

interface SourceAuthenticationViewProps {
  sourceName: string;
  sourceShortName?: string; // Added for icon display
  authenticationUrl?: string;
  onRefreshUrl?: () => void;
  isRefreshing?: boolean;
  showBorder?: boolean; // Optional border for collection detail view
}

export const SourceAuthenticationView: React.FC<SourceAuthenticationViewProps> = ({
  sourceName,
  sourceShortName,
  authenticationUrl,
  onRefreshUrl,
  isRefreshing = false,
  showBorder = false
}) => {
  const { resolvedTheme } = useTheme();
  const isDark = resolvedTheme === 'dark';
  const [copied, setCopied] = useState(false);
  const [isConnecting, setIsConnecting] = useState(false);

  const copyToClipboard = () => {
    if (authenticationUrl) {
      navigator.clipboard.writeText(authenticationUrl);
      setCopied(true);
      toast.success('Link copied to clipboard');
      setTimeout(() => setCopied(false), 2000);
    }
  };

  const handleConnect = () => {
    if (authenticationUrl) {
      setIsConnecting(true);
      // Small delay for visual feedback before navigation
      setTimeout(() => {
        window.location.href = authenticationUrl;
      }, 100);
    }
  };

  if (!authenticationUrl) {
    // Error state - minimal and helpful
    return (
      <div className={cn(
        "rounded-xl p-6",
        showBorder && "border",
        showBorder && (isDark ? "border-gray-800" : "border-gray-200"),
        isDark ? "bg-gray-900/20" : "bg-gray-50"
      )}>
        <div>
          <p className={cn(
            "text-sm font-medium mb-2",
            isDark ? "text-gray-300" : "text-gray-700"
          )}>
            Unable to generate authentication link
          </p>
          {onRefreshUrl && (
            <button
              onClick={onRefreshUrl}
              disabled={isRefreshing}
              className={cn(
                "inline-flex items-center gap-1.5",
                "px-3 py-1.5 rounded-lg",
                "text-xs font-medium",
                "transition-all",
                isRefreshing
                  ? "bg-muted text-muted-foreground cursor-not-allowed"
                  : "bg-primary text-primary-foreground hover:bg-primary/90"
              )}
            >
              {isRefreshing ? (
                <>
                  <Loader2 className="h-3 w-3 animate-spin" />
                  <span>Refreshing</span>
                </>
              ) : (
                <span>Try again</span>
              )}
            </button>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className={cn(
      "rounded-xl",
      showBorder && "border",
      showBorder && (isDark ? "border-gray-800" : "border-gray-200"),
      isDark ? "bg-gray-900/5" : "bg-gray-50/30"
    )}>
      <div className="space-y-6">
        {/* Header - direct and clear */}
        <div className="flex items-start gap-3">
          <div className={cn(
            "h-2 w-2 rounded-full mt-2 flex-shrink-0",
            "bg-cyan-500"
          )} />
          <div>
            <h3 className={cn(
              "text-base font-semibold mb-1",
              isDark ? "text-white" : "text-gray-900"
            )}>
              Authorize this source connection
            </h3>
            <p className={cn(
              "text-sm",
              isDark ? "text-gray-400" : "text-gray-600"
            )}>
              Grant permission to Airweave
            </p>
          </div>
        </div>

        {/* Two options with visual hierarchy */}
        <div className="space-y-4">
          {/* Option 1: Share Link */}
          <div className="space-y-2">
            <p className={cn(
              "text-sm font-medium",
              isDark ? "text-gray-200" : "text-gray-800"
            )}>
              Share the secure link
            </p>
            <p className={cn(
              "text-xs",
              isDark ? "text-gray-500" : "text-gray-500"
            )}>
              Send this link to someone who has {sourceName} access
            </p>

            <div className={cn(
              "group relative rounded-lg mt-2",
              "border transition-all duration-200",
              isDark
                ? "bg-black/30 border-white/10 hover:border-white/20"
                : "bg-gray-50 border-gray-200 hover:border-gray-300"
            )}>
              <div className="flex items-center p-2.5">
                <code className={cn(
                  "flex-1 text-xs font-mono",
                  "overflow-x-auto whitespace-nowrap",
                  "scrollbar-none select-all",
                  isDark ? "text-gray-400" : "text-gray-600"
                )}>
                  {authenticationUrl}
                </code>
                <button
                  onClick={copyToClipboard}
                  className={cn(
                    "ml-3 p-1.5 rounded-md flex-shrink-0",
                    "transition-all duration-200",
                    copied
                      ? "bg-green-500/10 text-green-500"
                      : isDark
                        ? "hover:bg-white/5 text-gray-500 hover:text-gray-400"
                        : "hover:bg-gray-100 text-gray-400 hover:text-gray-600"
                  )}
                  title={copied ? "Copied!" : "Copy link"}
                >
                  <Copy className={cn(
                    "h-3.5 w-3.5",
                    "transition-transform duration-200",
                    copied && "scale-110"
                  )} />
                </button>
              </div>
            </div>
          </div>

          {/* Visual divider with OR */}
          <div className="relative">
            <div className={cn(
              "absolute inset-0 flex items-center"
            )}>
              <div className={cn(
                "w-full border-t",
                isDark ? "border-white/10" : "border-gray-200"
              )} />
            </div>
            <div className="relative flex justify-center">
              <span className={cn(
                "px-3 text-[11px] font-medium uppercase tracking-wider",
                isDark ? "text-gray-600 bg-gray-900" : "text-gray-400 bg-white"
              )}>
                or
              </span>
            </div>
          </div>

          {/* Option 2: Direct Connect */}
          <div className="flex items-start justify-between gap-4">
            <div>
              <p className={cn(
                "text-sm font-medium",
                isDark ? "text-gray-200" : "text-gray-800"
              )}>
                Connect directly
              </p>
              <p className={cn(
                "text-xs mt-0.5",
                isDark ? "text-gray-500" : "text-gray-500"
              )}>
                Use your own {sourceName} account to authorize
              </p>
            </div>

            <TooltipProvider>
              <Tooltip>
                <TooltipTrigger asChild>
                  <button
                    onClick={handleConnect}
                    disabled={isConnecting || !authenticationUrl}
                    className={cn(
                      "inline-flex items-center gap-2",
                      "px-4 py-2 rounded-lg",
                      "text-sm font-medium",
                      "transition-all whitespace-nowrap",

                      isConnecting || !authenticationUrl
                        ? "bg-muted text-muted-foreground cursor-not-allowed"
                        : "bg-primary text-primary-foreground hover:bg-primary/90"
                    )}
                  >
                    {isConnecting ? (
                      <>
                        <Loader2 className="h-3.5 w-3.5 animate-spin" />
                        <span>Connecting</span>
                      </>
                    ) : (
                      <>
                        {sourceShortName && (
                          <img
                            src={getAppIconUrl(sourceShortName, resolvedTheme)}
                            alt={sourceName}
                            className="h-3.5 w-3.5 object-contain"
                            onError={(e) => {
                              e.currentTarget.style.display = 'none';
                            }}
                          />
                        )}
                        <span>Connect now</span>
                        <ArrowRight className="h-3.5 w-3.5" />
                      </>
                    )}
                  </button>
                </TooltipTrigger>
                <TooltipContent>
                  <p>You'll be redirected to {sourceName} to authorize this connection</p>
                </TooltipContent>
              </Tooltip>
            </TooltipProvider>
          </div>
        </div>

        {/* Connection Visual - Between Connect directly and bottom */}
        {sourceShortName && (
          <div className="flex items-center justify-center gap-8 pt-12 pb-4">
            {/* Left side - Icons and animations */}
            <div className="flex flex-col items-center gap-3">
              {/* Airweave Logo */}
              <div className={cn(
                "w-20 h-20 rounded-xl flex items-center justify-center p-2",
                isDark ? "bg-gray-800/50" : "bg-white/80",
                "shadow-lg"
              )}>
                <img
                  src={isDark ? "/airweave-logo-svg-white-darkbg.svg" : "/airweave-logo-svg-lightbg-blacklogo.svg"}
                  alt="Airweave"
                  className="w-10 h-10 object-contain"
                />
              </div>

              {/* Animated Connection Lines */}
              <div className="relative flex flex-col items-center gap-2">
                {/* Connection container with overflow hidden for animation */}
                <div className="relative w-2 h-16 overflow-hidden">
                  {/* Static background lines */}
                  <div className={cn(
                    "absolute inset-0 w-0.5 left-1/2 transform -translate-x-1/2",
                    isDark ? "bg-gray-600/30" : "bg-gray-300/50"
                  )} />

                  {/* Animated data packet going up (Source to Airweave) */}
                  <div
                    className={cn(
                      "absolute w-1 h-3 left-1/2 transform -translate-x-1/2 rounded-full",
                      "shadow-sm",
                      isDark
                        ? "bg-gradient-to-t from-white to-gray-200 shadow-white/50"
                        : "bg-gradient-to-t from-gray-100 to-gray-300 shadow-gray-400/50"
                    )}
                    style={{
                      animationDelay: '0s',
                      transform: 'translateX(-50%) translateY(0px)',
                      animation: 'slideUp 2s ease-in-out infinite'
                    }}
                  />
                </div>
              </div>

              {/* Source Icon */}
              <div className={cn(
                "w-16 h-16 rounded-xl flex items-center justify-center p-3",
                isDark ? "bg-gray-800/50" : "bg-white/80",
                "shadow-lg"
              )}>
                <img
                  src={getAppIconUrl(sourceShortName, resolvedTheme)}
                  alt={sourceName}
                  className="w-full h-full object-contain"
                  onError={(e) => {
                    e.currentTarget.style.display = 'none';
                  }}
                />
              </div>
            </div>

            {/* Right side - Waiting text */}
            <div className="flex items-center justify-center">
              <p className={cn(
                "text-sm font-medium relative",
                "bg-clip-text text-transparent",
                "animate-[textShimmer_2.5s_ease-in-out_infinite]",
                isDark
                  ? "bg-gradient-to-r from-gray-400 via-white to-gray-400"
                  : "bg-gradient-to-r from-gray-500 via-gray-900 to-gray-500"
              )}
                style={{
                  backgroundSize: '200% 100%',
                  animation: 'textShimmer 2.5s ease-in-out infinite'
                }}>
                Waiting for connection...
              </p>
            </div>
          </div>
        )}

      </div>
    </div>
  );
};
