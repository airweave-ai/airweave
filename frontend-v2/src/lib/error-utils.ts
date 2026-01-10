export const CONNECTION_ERROR_STORAGE_KEY = "airweave_connection_error";

export interface ErrorDetails {
  serviceName?: string;
  sourceShortName?: string;
  errorMessage: string;
  errorDetails?: string;
  timestamp: number;
  canRetry?: boolean;
  dialogState?: unknown;
  dialogId?: string;
}

export type NavigateFunction = (options: {
  to: string;
  replace?: boolean;
  search?: Record<string, string>;
}) => void;

export function redirectWithError(
  navigateOrLocation: NavigateFunction | typeof window.location | Location,
  error: Error | string | ErrorDetails,
  targetPath: string = "/",
  serviceName?: string
): void {
  let errorData: ErrorDetails;

  if (typeof error === "string") {
    errorData = {
      serviceName,
      errorMessage: error,
      errorDetails: error,
      timestamp: Date.now(),
    };
  } else if (error instanceof Error) {
    errorData = {
      serviceName,
      errorMessage: error.message || "Connection failed",
      errorDetails: error.stack || error.message,
      timestamp: Date.now(),
    };
  } else {
    errorData = {
      ...error,
      serviceName: error.serviceName || serviceName,
      timestamp: Date.now(),
    };
  }

  console.error(`[ErrorUtils] Error details:`, {
    message: errorData.errorMessage,
    details: errorData.errorDetails,
    service: errorData.serviceName,
  });

  try {
    localStorage.setItem(
      CONNECTION_ERROR_STORAGE_KEY,
      JSON.stringify(errorData)
    );
    console.debug(`[ErrorUtils] Stored error details in localStorage`);
  } catch (e) {
    console.error("[ErrorUtils] Failed to store error details:", e);
  }

  if (typeof navigateOrLocation === "function") {
    navigateOrLocation({
      to: targetPath,
      replace: true,
      search: { connected: "error" },
    });
  } else {
    const targetUrl = `${targetPath}?connected=error`;
    try {
      if ("href" in navigateOrLocation) {
        navigateOrLocation.href = targetUrl;
      } else {
        console.error(
          "[ErrorUtils] Invalid navigation object:",
          navigateOrLocation
        );
        window.location.href = targetUrl;
      }
    } catch (e) {
      console.error("[ErrorUtils] Navigation error:", e);
      window.location.href = targetUrl;
    }
  }
}

export function storeErrorDetails(error: ErrorDetails): void {
  try {
    console.debug("[ErrorUtils] Storing error details in localStorage");
    localStorage.setItem(
      CONNECTION_ERROR_STORAGE_KEY,
      JSON.stringify({
        ...error,
        timestamp: Date.now(),
      })
    );
  } catch (e) {
    console.error("[ErrorUtils] Could not store error details:", e);
  }
}

export function getStoredErrorDetails(): ErrorDetails | null {
  try {
    const rawData = localStorage.getItem(CONNECTION_ERROR_STORAGE_KEY);
    if (!rawData) return null;
    return JSON.parse(rawData) as ErrorDetails;
  } catch (e) {
    console.error("[ErrorUtils] Error retrieving stored error details:", e);
    return null;
  }
}

export function clearStoredErrorDetails(): void {
  try {
    localStorage.removeItem(CONNECTION_ERROR_STORAGE_KEY);
    console.debug("[ErrorUtils] Cleared error details from localStorage");
  } catch (e) {
    console.error("[ErrorUtils] Error clearing stored error details:", e);
  }
}

export function hasStoredError(): boolean {
  return localStorage.getItem(CONNECTION_ERROR_STORAGE_KEY) !== null;
}

export async function createErrorFromResponse(
  response: Response,
  fallbackMessage: string = "An error occurred"
): Promise<ErrorDetails> {
  let errorMessage = fallbackMessage;
  let errorDetails: string | undefined;

  try {
    const data = await response.json();
    errorMessage = data.message || data.detail || data.error || fallbackMessage;
    errorDetails = JSON.stringify(data, null, 2);
  } catch {
    errorDetails = `HTTP ${response.status}: ${response.statusText}`;
  }

  return {
    errorMessage,
    errorDetails,
    timestamp: Date.now(),
  };
}
