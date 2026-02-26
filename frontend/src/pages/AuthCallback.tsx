/**
 * AuthCallback.tsx
 *
 * This component handles the OAuth callback process after a user authorizes
 * an external service. It's the final leg of the OAuth flow, where we:
 *
 * 1. Receive the authorization code from the OAuth provider
 * 2. Exchange the code for a connection via the backend
 * 3. Create the collection (using previously stored details)
 * 4. Create the source connection with the OAuth credentials
 * 5. Redirect the user to the appropriate page
 *
 * Flow context:
 * - This page is loaded when returning from an OAuth provider (like Google, GitHub, etc.)
 * - The user previously started in ConnectFlow, which stored collection details
 * - After processing, the user is redirected to the collection detail page
 */

import React, { useEffect, useState, useRef } from "react";
import { useSearchParams } from "react-router-dom";
import { apiClient } from "@/lib/api";
import { CONNECTION_ERROR_STORAGE_KEY } from "@/lib/error-utils";
import { useAuth } from "@/lib/auth-context";
import { safeLogDialogState } from "@/lib/auth-utils";

/** ------------------------------------------------------------------
 * Helpers to decode/parse `state` from the OAuth redirect
 * ------------------------------------------------------------------ */

type OAuthStatePayload = {
  short_name?: string;
  shortName?: string;
  nonce?: string;
  [k: string]: any;
};

function base64UrlDecode(input: string | null): string {
  if (!input) return "";
  let b64 = input.replace(/-/g, "+").replace(/_/g, "/");
  while (b64.length % 4 !== 0) b64 += "=";
  try {
    return atob(b64);
  } catch {
    return "";
  }
}

/**
 * Attempt to parse the OAuth `state` value.
 * Supports:
 * - JWT: use payload (segment 2)
 * - base64url(JSON)
 * - raw JSON string
 */
function parseStateParam(value: string | null): OAuthStatePayload | null {
  if (!value) return null;

  // JWT?
  const parts = value.split(".");
  if (parts.length === 3) {
    const payloadJson = base64UrlDecode(parts[1]);
    try {
      return JSON.parse(payloadJson);
    } catch {
      // fall through
    }
  }

  // base64url(JSON)?
  const asJson = base64UrlDecode(value);
  if (asJson) {
    try {
      return JSON.parse(asJson);
    } catch {
      // fall through
    }
  }

  // raw JSON?
  try {
    return JSON.parse(value);
  } catch {
    // not parseable
  }

  return null;
}

function deriveShortName(
  statePayload: OAuthStatePayload | null,
  savedState: any
): string | undefined {
  return (
    statePayload?.short_name ||
    statePayload?.shortName ||
    savedState?.sourceShortName ||
    savedState?.short_name ||
    savedState?.sourceDetails?.short_name ||
    savedState?.sourceDetails?.shortName
  );
}

/**
 * Shared function to exchange OAuth code for credentials
 */
async function exchangeCodeForCredentials(
  code: string,
  shortName: string,
  savedState: any
): Promise<{ id: string }> {
  console.log(`🔄 Exchanging code for credentials for ${shortName}`);

  // Define interface for type safety
  interface CredentialRequestData {
    credential_name: string;
    credential_description: string;
    client_id?: string;
    client_secret?: string;
  }

  const requestData: CredentialRequestData = {
    credential_name: `${savedState.sourceDetails?.name || savedState.detailedSource?.name || shortName
      } OAuth Credential`,
    credential_description: `OAuth credential for ${savedState.sourceDetails?.name || savedState.detailedSource?.name || shortName
      }`,
  };

  // Add client_id and client_secret from authValues if they exist
  if (savedState.authValues?.client_id) {
    requestData.client_id = savedState.authValues.client_id;
  }
  if (savedState.authValues?.client_secret) {
    requestData.client_secret = savedState.authValues.client_secret;
  }

  console.log("📋 Credential request data:", requestData);

  const response = await apiClient.post(
    `/source-connections/${shortName}/code_to_token_credentials?code=${encodeURIComponent(code)}`,
    requestData
  );

  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(`Failed to exchange code: ${errorText}`);
  }

  // Get credential data
  const credential = await response.json();
  console.log("✅ Credentials created:", credential.id);

  return credential;
}

/**
 * Handles OAuth callback specifically for SemanticMcp flow
 */
async function handleSemanticMcpOAuthCallback(
  code: string,
  shortName: string,
  savedState: any,
  setIsProcessing: (value: boolean) => void
): Promise<void> {
  try {
    console.log("🎯 [AuthCallback] Handling SemanticMcp OAuth callback");
    console.log("📋 Code:", code);
    console.log("📋 Short name:", shortName);
    console.log("📋 Saved state:", savedState);

    // Keep processing state true to maintain loading screen
    setIsProcessing(true);

    // Exchange code for credentials using shared function
    const credential = await exchangeCodeForCredentials(code, shortName, savedState);

    // Update saved state with credential info
    const updatedState = {
      ...savedState,
      credentialId: credential.id,
      isAuthenticated: true,
    };

    safeLogDialogState(updatedState, '📊 [AuthCallback SemanticMcp]');
    sessionStorage.setItem("oauth_dialog_state", JSON.stringify(updatedState));

    // Redirect back to SemanticMcp with restore flag
    const returnPath = savedState.originPath || "/semantic-mcp";
    window.location.href = `${returnPath}?restore_dialog=true`;
  } catch (error) {
    console.error("❌ Error in SemanticMcp OAuth callback:", error);
    const errorMessage = error instanceof Error ? error.message : String(error);

    // Store error details in sessionStorage
    const errorDetails = {
      type: "oauth_error",
      source: "semantic-mcp",
      sourceName: savedState.detailedSource?.name || shortName,
      shortName,
      message: errorMessage,
      details: error instanceof Error ? error.stack : undefined,
      timestamp: Date.now(),
    };

    sessionStorage.setItem("semantic_mcp_error", JSON.stringify(errorDetails));

    // Clear the oauth dialog state since we're erroring out
    sessionStorage.removeItem("oauth_dialog_state");

    // Redirect back to SemanticMcp with error flag
    const returnPath = savedState.originPath || "/semantic-mcp";
    window.location.href = `${returnPath}?error=oauth`;
  }
}

/**
 * Handles OAuth callback for the original flow (ConnectFlow, etc.)
 * (short name is now derived from the `state` param or saved dialog state)
 */
async function handleOriginalOAuthCallback(
  searchParams: URLSearchParams,
  statePayload: OAuthStatePayload | null,
  hasProcessedRef: React.MutableRefObject<boolean>,
  setIsProcessing: (value: boolean) => void
): Promise<void> {
  try {
    // Set the ref immediately to prevent duplicate processing
    hasProcessedRef.current = true;

    // Get code from URL
    const code = searchParams.get("code");
    const errorParam = searchParams.get("error");

    // Retrieve saved dialog state (for CSRF-ish check + fallbacks)
    const savedStateJson = sessionStorage.getItem("oauth_dialog_state");
    const savedState = savedStateJson ? JSON.parse(savedStateJson) : {};

    const shortName = deriveShortName(statePayload, savedState);

    // Check for OAuth provider errors
    if (errorParam) {
      console.error(`OAuth provider returned error: ${errorParam}`);
      const errorDesc = searchParams.get("error_description") || "Authorization denied";

      // Set processing to false
      setIsProcessing(false);

      // Create error data and store it
      const errorData = {
        serviceName: savedState.sourceName || shortName,
        sourceShortName: savedState.sourceShortName || shortName,
        errorMessage: `OAuth error: ${errorParam} - ${errorDesc}`,
        errorDetails: `The OAuth provider rejected the authorization request with error: ${errorParam}`,
        dialogId: savedState.dialogId, // Include the dialogId
        timestamp: Date.now(),
      };

      // Store in localStorage without risk of exception
      localStorage.setItem(CONNECTION_ERROR_STORAGE_KEY, JSON.stringify(errorData));

      // Immediate redirect to dashboard with error flag
      const returnPath = savedState.originPath || "/";
      window.location.href = `${returnPath}?connected=error`;
      return;
    }

    if (!code) {
      throw new Error("Missing authorization code");
    }
    if (!shortName) {
      throw new Error("Missing short_name in state and no saved fallback");
    }

    console.log("📋 Retrieved saved state");
    safeLogDialogState(savedState, '📊 [AuthCallback Original]');

    // Exchange code for credentials using the shared function
    const credential = await exchangeCodeForCredentials(code, shortName, savedState);

    // Update saved state with credential info
    const updatedState = {
      ...savedState,
      credentialId: credential.id,
      isAuthenticated: true,
    };
    safeLogDialogState(updatedState, '📊 [AuthCallback Original] Updated');
    sessionStorage.setItem("oauth_dialog_state", JSON.stringify(updatedState));

    // Redirect back to original page with flag to restore dialog
    const returnPath = savedState.originPath || "/";
    window.location.href = `${returnPath}?restore_dialog=true`;
  } catch (error) {
    console.error("❌ Error processing OAuth callback:", error);
    setIsProcessing(false);

    // Store error details using error-utils before redirecting
    const errorMessage = error instanceof Error ? error.message : String(error);
    const errorDetails = error instanceof Error ? error.stack : undefined;

    // Get the saved state to extract dialogId
    const savedState = sessionStorage.getItem("oauth_dialog_state");
    const parsedState = savedState ? JSON.parse(savedState) : {};

    // Re-parse state to attempt deriving short name for error context
    const parsedStatePayload = parseStateParam(new URLSearchParams(window.location.search).get("state"));
    const shortName = deriveShortName(parsedStatePayload, parsedState) || "unknown";

    // Create error details object INCLUDING dialogId
    const errorData = {
      serviceName: parsedState.sourceName || shortName,
      sourceShortName: parsedState.sourceShortName || shortName,
      errorMessage,
      errorDetails,
      dialogId: parsedState.dialogId, // Include the dialogId so DialogFlow can match it
      timestamp: Date.now(),
    };

    // Store in localStorage
    localStorage.setItem(CONNECTION_ERROR_STORAGE_KEY, JSON.stringify(errorData));

    // Redirect with error flag - this will trigger the error UI
    const returnPath = parsedState.originPath || "/dashboard";
    window.location.href = `${returnPath}?connected=error`;
  }
}

/**
 * AuthCallback Component
 *
 * This component handles the final leg of the OAuth2 flow:
 * 1) Receives code from OAuth provider in URL
 * 2) Exchanges code for connection via /connections/oauth2/source/code
 * 3) Creates source connection using our custom endpoint
 * 4) Redirects to collection page with success/error status
 */
export function AuthCallback() {
  const [searchParams] = useSearchParams();
  const [isProcessing, setIsProcessing] = useState(true);
  const [isSemanticMcpFlow, setIsSemanticMcpFlow] = useState(false);
  const hasProcessedRef = useRef(false);
  const auth = useAuth();

  useEffect(() => {
    // We must wait for our auth context to be ready and the user to be authenticated
    // before making an authenticated API call.
    if (!auth.isReady() || !auth.isAuthenticated) {
      console.log("[AuthCallback] Waiting for authentication to be ready...");
      setIsProcessing(true); // Ensure loading indicator is shown
      return;
    }

    const processCallback = async () => {
      // Skip if we've already processed this code
      if (hasProcessedRef.current) return;

      // Parse state sent by OAuth provider
      const statePayload = parseStateParam(searchParams.get("state"));

      // FIRST: Check where we came from
      const savedStateJson = sessionStorage.getItem("oauth_dialog_state");

      if (savedStateJson) {
        try {
          const savedState = JSON.parse(savedStateJson);

          // Check if this is from SemanticMcp
          if (savedState.source === "semantic-mcp") {
            console.log("🔍 [AuthCallback] Detected SemanticMcp OAuth flow");
            hasProcessedRef.current = true; // Prevent duplicate processing
            setIsSemanticMcpFlow(true); // Set the flag

            const code = searchParams.get("code");
            const errorParam = searchParams.get("error");
            const shortName = deriveShortName(statePayload, savedState) || "unknown";

            if (errorParam) {
              // Handle OAuth provider error for SemanticMcp
              const errorDesc = searchParams.get("error_description") || "Authorization denied";

              // Store error details in sessionStorage
              const errorDetails = {
                type: "oauth_provider_error",
                source: "semantic-mcp",
                sourceName:
                  savedState.detailedSource?.name || savedState.selectedSource?.name || "Unknown",
                shortName,
                message: `OAuth provider error: ${errorParam} - ${errorDesc}`,
                details: `The OAuth provider rejected the authorization request with error: ${errorParam}`,
                timestamp: Date.now(),
              };

              sessionStorage.setItem("semantic_mcp_error", JSON.stringify(errorDetails));
              sessionStorage.removeItem("oauth_dialog_state");

              // Redirect back with error flag
              const returnPath = savedState.originPath || "/semantic-mcp";
              window.location.href = `${returnPath}?error=oauth`;
              return;
            }

            if (!code || !shortName || shortName === "unknown") {
              // Store error for missing parameters
              const errorDetails = {
                type: "missing_parameters",
                source: "semantic-mcp",
                sourceName: savedState.detailedSource?.name || "Unknown",
                shortName,
                message: "Missing authorization code or source name",
                details: "The OAuth callback did not receive the required parameters",
                timestamp: Date.now(),
              };

              sessionStorage.setItem("semantic_mcp_error", JSON.stringify(errorDetails));
              sessionStorage.removeItem("oauth_dialog_state");

              const returnPath = savedState.originPath || "/semantic-mcp";
              window.location.href = `${returnPath}?error=oauth`;
              return;
            }

            // Call the SemanticMcp-specific handler with state setters
            await handleSemanticMcpOAuthCallback(code, shortName, savedState, setIsProcessing);
            return;
          }
        } catch (e) {
          console.error("Failed to parse saved state:", e);
        }
      }

      // If we get here, it's not from SemanticMcp, so use the original flow (short_name via state)
      console.log("🔍 [AuthCallback] Using original OAuth flow");
      await handleOriginalOAuthCallback(searchParams, statePayload, hasProcessedRef, setIsProcessing);
    };

    processCallback();

  }, [searchParams, auth.isReady, auth.isAuthenticated]);

  // For the small UI text, try to show the provider short name based on state/fallback
  const statePayloadForDisplay = parseStateParam(searchParams.get("state"));
  let displayShortName: string | undefined;
  try {
    const savedStateJson = sessionStorage.getItem("oauth_dialog_state");
    const saved = savedStateJson ? JSON.parse(savedStateJson) : undefined;
    displayShortName = deriveShortName(statePayloadForDisplay, saved);
  } catch {
    displayShortName = deriveShortName(statePayloadForDisplay, undefined);
  }

  // Simple loading UI - errors are handled by redirecting back to source page
  return (
    <div className="flex items-center justify-center h-screen">
      <div className="text-center">
        <p className="text-sm text-muted-foreground">
          {`Processing OAuth response${displayShortName ? ` from ${displayShortName}` : ""}...`}
        </p>
      </div>
    </div>
  );
}
