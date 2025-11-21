/**
 * ConnectionErrorView.tsx
 *
 * This component displays error details when a connection attempt fails.
 * It provides users with:
 * 1. Clear visual indication of the error
 * 2. Detailed error message and technical details if available
 * 3. Options to retry the connection or cancel the flow
 *
 * The UI includes a distinctive "red dots" design to indicate error state.
 */

import React, { useEffect, useState } from "react";
import { DialogTitle, DialogDescription, DialogFooter } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { RefreshCw, Copy, Check } from "lucide-react";
import { cn } from "@/lib/utils";
import { useTheme } from "@/lib/theme-provider";
import type { DialogViewProps } from "@/components/types/dialog";
import { getAppIconUrl } from "@/lib/utils/icons";

/**
 * Props for the ConnectionErrorView component
 * Extends DialogViewProps with error-specific fields
 */
export interface ConnectionErrorViewProps extends DialogViewProps {
    viewData?: {
        /** Name of the service that failed to connect */
        serviceName?: string;
        /** Short name for source icon display */
        sourceShortName?: string;
        /** User-friendly error message */
        errorMessage?: string;
        /** Technical error details for debugging */
        errorDetails?: string;
        /** Optional function to retry the failed operation */
        retryAction?: () => void;
        /** Indicates if retry is possible */
        canRetry?: boolean;
    };
}

/**
 * ConnectionErrorView Component
 *
 * Displays connection errors with a visual indicator and options to retry or cancel.
 */
export const ConnectionErrorView: React.FC<ConnectionErrorViewProps> = ({
    onCancel,
    viewData = {},
}) => {
    const { resolvedTheme } = useTheme();
    const isDark = resolvedTheme === "dark";
    const [isDetailsCopied, setIsDetailsCopied] = useState(false);

    // Destructure error information from viewData
    const {
        serviceName = "Unknown service",
        sourceShortName = serviceName?.toLowerCase() || "unknown-service",
        errorMessage = "Connection failed",
        errorDetails,
        retryAction,
        canRetry
    } = viewData || {};

    // Log when this component is rendered with data
    useEffect(() => {
        console.log("🔔 [ConnectionErrorView] Rendered with data:", {
            serviceName,
            sourceShortName,
            errorMessage: errorMessage?.substring(0, 100), // Truncate for logging
            hasErrorDetails: !!errorDetails,
            errorDetailsLength: errorDetails?.length,
            hasRetryAction: !!retryAction
        });
    }, [serviceName, sourceShortName, errorMessage, errorDetails, retryAction]);

    // Format error details section to handle nested JSON strings
    let displayedDetails = errorDetails;
    if (errorDetails && typeof errorDetails === 'string') {
        // Extract JSON if the error is a stringified object
        if (errorDetails.includes('{') && errorDetails.includes('}')) {
            try {
                // Try to extract JSON from error string (handles cases like "Error: {"detail":"..."}")
                const jsonStart = errorDetails.indexOf('{');
                const jsonEnd = errorDetails.lastIndexOf('}') + 1;
                if (jsonStart > -1 && jsonEnd > jsonStart) {
                    const jsonStr = errorDetails.substring(jsonStart, jsonEnd);
                    const parsed = JSON.parse(jsonStr);
                    // Display the detail from JSON if available
                    if (parsed.detail) {
                        displayedDetails = parsed.detail;
                    }
                }
            } catch (e) {
                console.warn("Could not parse error JSON:", e);
                // Fall back to the original error details
                displayedDetails = errorDetails;
            }
        }
    }

    // Copy technical details to clipboard
    const handleCopyDetails = () => {
        if (displayedDetails) {
            navigator.clipboard.writeText(displayedDetails);
            setIsDetailsCopied(true);

            // Reset after animation completes
            setTimeout(() => {
                setIsDetailsCopied(false);
            }, 1500);
        }
    };

    // IMPORTANT: We do NOT clear error state on component mount
    // Only clear it when the user clicks the "Go back" button
    const handleCancel = () => {
        if (onCancel) {
            onCancel();
        }
    };

    return (
        <div className="flex flex-col h-full">
            {/* Content area - scrollable */}
            <div className="flex-grow overflow-y-auto">
                <div className="p-8 flex flex-col items-center h-full">
                    {/* Title */}
                    <DialogTitle className="text-4xl font-semibold text-left self-start mb-8 text-red-600">
                        Connection failed
                    </DialogTitle>

                    {/* Source Icon */}
                    <div className="flex justify-center items-center mb-6" style={{ minHeight: "20%" }}>
                        <div className={cn(
                            "w-64 h-64 flex items-center justify-center border border-black rounded-lg p-2",
                            isDark ? "border-gray-700" : "border-gray-800"
                        )}>
                            <img
                                src={getAppIconUrl(sourceShortName, resolvedTheme)}
                                alt={`${serviceName} icon`}
                                className="w-full h-full object-contain"
                                onError={(e) => {
                                    e.currentTarget.style.display = 'none';
                                    const parent = e.currentTarget.parentElement!;

                                    // Create elements safely without innerHTML to prevent XSS
                                    const wrapper = document.createElement('div');
                                    wrapper.className = `w-full h-full rounded-lg flex items-center justify-center ${isDark ? 'bg-blue-900' : 'bg-blue-100'}`;

                                    const span = document.createElement('span');
                                    span.className = `text-5xl font-bold ${isDark ? 'text-blue-400' : 'text-blue-600'}`;
                                    span.textContent = sourceShortName.substring(0, 2).toUpperCase();

                                    wrapper.appendChild(span);
                                    parent.appendChild(wrapper);
                                }}
                            />
                        </div>
                    </div>

                    {/* Error description */}
                    <DialogDescription className="text-center text-lg mb-6 max-w-md">
                        Airweave wasn't able to connect to <span className="font-semibold">{serviceName}</span>.
                    </DialogDescription>

                    {/* Spacer to push error box down */}
                    <div className="flex-grow" style={{ minHeight: "5%" }}></div>

                    {/* Error message in black box with red border - full width and taller */}
                    <div className={cn(
                        "w-full rounded-lg p-6 pb-8 mb-2 text-sm",
                        "min-h-[220px] flex flex-col",
                        isDark
                            ? "bg-black border-2 text-gray-300"
                            : "bg-gray-900 border-2 text-gray-100"
                    )}>
                        <p className="font-medium mb-3 text-base">Error: {errorMessage}</p>

                        {displayedDetails && (
                            <div className="mt-1 pt-3 border-t border-gray-700 flex-grow flex flex-col">
                                <div className="flex items-center justify-between mb-2">
                                    <p className="text-xs text-gray-400 font-medium">Technical details:</p>
                                    <button
                                        className="flex items-center text-xs text-gray-400 hover:text-gray-200 focus:outline-none group"
                                        onClick={handleCopyDetails}
                                        title="Copy technical details"
                                    >
                                        {isDetailsCopied ? (
                                            <span className="flex items-center">
                                                <Check className="h-3.5 w-3.5 mr-1" />
                                                Copied
                                            </span>
                                        ) : (
                                            <span className="flex items-center">
                                                <Copy className="h-3.5 w-3.5 mr-1" />
                                                Copy
                                            </span>
                                        )}
                                    </button>
                                </div>
                                <div className="flex-grow flex flex-col mb-4 rounded overflow-hidden">
                                    <pre className={cn(
                                        "text-xs p-4 bg-black/50 overflow-y-auto whitespace-pre-wrap break-words",
                                        "h-full min-h-[120px] flex-grow"
                                    )}>
                                        {displayedDetails}
                                    </pre>
                                </div>
                            </div>
                        )}
                    </div>
                </div>
            </div>

            {/* Footer - fixed at bottom */}
            <div className="flex-shrink-0 border-t">
                <DialogFooter className="flex justify-between p-6">
                    <Button
                        variant="outline"
                        onClick={handleCancel}
                        className={cn(
                            isDark ? "border-gray-700 hover:bg-gray-800" : "border-gray-300 hover:bg-gray-100"
                        )}
                    >
                        Go back
                    </Button>

                    {(retryAction || canRetry === true) && (
                        <Button
                            onClick={retryAction || (() => console.log("No retry action defined"))}
                            className="bg-blue-600 hover:bg-blue-700 text-white"
                            disabled={!retryAction && canRetry}
                        >
                            <RefreshCw className="mr-2 h-4 w-4" />
                            Try again
                        </Button>
                    )}
                </DialogFooter>
            </div>
        </div>
    );
};

export default ConnectionErrorView;
