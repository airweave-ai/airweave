/**
 * error-utils.ts
 *
 * Utility functions for handling connection errors consistently across the application.
 * Uses localStorage to store error details and URL parameter just for signaling.
 */

import { NavigateFunction } from "react-router-dom";
import { protectedPaths } from "@/constants/paths";

// Storage key for error data
export const CONNECTION_ERROR_STORAGE_KEY = "airweave_connection_error";

/**
 * ErrorDetails interface
 * Defines the structure of error information stored in localStorage
 */
export interface ErrorDetails {
    serviceName?: string;
    sourceShortName?: string;    // Add source short name for proper image display
    errorMessage: string;
    errorDetails?: string;
    timestamp: number;
    canRetry?: boolean;     // Whether this error can be retried
    dialogState?: any;      // Store dialog state for potential retry
    dialogId?: string;      // Identify which dialog should handle the error
}

/**
 * Stores error details in localStorage and redirects to dashboard
 *
 * @param navigate - React Router navigate function or window.location
 * @param error - Error object or message
 * @param serviceName - Name of the service that failed (optional)
 */
export const redirectWithError = (
    navigateOrLocation: NavigateFunction | typeof window.location | Location,
    error: Error | string | ErrorDetails,
    serviceName?: string
) => {
    // Extract error information
    let errorData: ErrorDetails;

    if (typeof error === 'string') {
        errorData = {
            serviceName,
            errorMessage: error,
            errorDetails: error,
            timestamp: Date.now()
        };
    } else if (error instanceof Error) {
        errorData = {
            serviceName,
            errorMessage: error.message || "Connection failed",
            errorDetails: error.stack || error.message,
            timestamp: Date.now()
        };
    } else {
        // It's already an ErrorDetails object
        errorData = {
            ...error,
            serviceName: error.serviceName || serviceName,
            timestamp: Date.now()
        };
    }

    // Log more detailed information for debugging
    console.error(`❌ [ErrorUtils] Error details:`, {
        message: errorData.errorMessage,
        details: errorData.errorDetails,
        service: errorData.serviceName
    });

    // Store in localStorage with more reliable stringify
    try {
        localStorage.setItem(CONNECTION_ERROR_STORAGE_KEY, JSON.stringify(errorData));
        console.log(`🔔 [ErrorUtils] Stored error details in localStorage`);
    } catch (e) {
        console.error("Failed to store error details:", e);
    }

    // Create URL with just the error flag (no sensitive data)
    const targetUrl = `${protectedPaths.dashboard}?connected=error`;
    console.log(`🧭 [ErrorUtils] Redirecting to error page: ${targetUrl}`);

    // Use appropriate navigation method based on type
    if (typeof navigateOrLocation === 'function') {
        // React Router navigate function
        navigateOrLocation(targetUrl, { replace: true });
    } else {
        // Window.location or Location object
        try {
            // Check if it's window.location (has href property)
            if ('href' in navigateOrLocation) {
                navigateOrLocation.href = targetUrl;
            } else {
                console.error('[ErrorUtils] Invalid navigation object:', navigateOrLocation);
                // Fallback to window.location
                window.location.href = targetUrl;
            }
        } catch (e) {
            console.error('[ErrorUtils] Navigation error:', e);
            // Absolute fallback
            window.location.href = targetUrl;
        }
    }
};

/**
 * Stores error details in localStorage and redirects to dashboard
 *
 * @param error - Error object or message
 * @param serviceName - Name of the service that failed (optional)
 */
export const storeErrorDetails = (error: ErrorDetails) => {
    try {
        console.log('🔔 [ErrorUtils] Storing error details in localStorage');
        localStorage.setItem(CONNECTION_ERROR_STORAGE_KEY, JSON.stringify({
            ...error,
            timestamp: Date.now()
        }));
    } catch (e) {
        console.error('❌ [ErrorUtils] Could not store error details:', e);
    }
};

/**
 * Retrieves error details from localStorage
 *
 * @returns Error details or null if none found
 */
export const getStoredErrorDetails = (): ErrorDetails | null => {
    try {
        const rawData = localStorage.getItem(CONNECTION_ERROR_STORAGE_KEY);
        console.log('📋 Raw error data from localStorage:', rawData);

        if (!rawData) {
            console.log('❌ [ErrorUtils] No error data found in localStorage');
            return null;
        }

        const data = JSON.parse(rawData);
        console.log('✅ [ErrorUtils] Retrieved error data:', data);
        return data;
    } catch (e) {
        console.error('❌ [ErrorUtils] Error retrieving stored error details:', e);
        return null;
    }
};

/**
 * Clears error details from localStorage
 */
export const clearStoredErrorDetails = () => {
    try {
        localStorage.removeItem(CONNECTION_ERROR_STORAGE_KEY);
        console.log('🧹 [ErrorUtils] Cleared error details from localStorage');
    } catch (e) {
        console.error('❌ [ErrorUtils] Error clearing stored error details:', e);
    }
};
