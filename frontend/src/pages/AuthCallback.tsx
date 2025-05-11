import React, { useEffect, useRef } from "react";
import { useSearchParams, useNavigate, useParams } from "react-router-dom";
import { apiClient } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";

/**
 * This page handles the final leg of the OAuth2 flow:
 * 1) Reads ?code= from the URL
 * 2) Sends it to /connections/oauth2/source/code
 * 3) Redirects back to the stored return URL or defaults to /sync/create with a success or error flag
 */
export function AuthCallback() {
  const [searchParams] = useSearchParams();
  const { short_name } = useParams();
  const navigate = useNavigate();
  const exchangeAttempted = useRef(false);
  const exchangePromise = useRef(null);
  const auth = useAuth();

  useEffect(() => {
    const doExchange = async () => {
      console.log(`Starting OAuth code exchange for ${short_name}. exchangeAttempted: ${exchangeAttempted.current}`);

      if (exchangeAttempted.current) {
        console.log('Exchange already attempted, skipping duplicate call');
        return;
      }

      const code = searchParams.get("code");
      if (!code || !short_name) {
        // Handle missing parameters
        const returnUrl = localStorage.getItem("oauth_return_url") || "/sync/create";
        navigate(`${returnUrl}?connected=error`, { replace: true });
        localStorage.removeItem("oauth_return_url");
        return;
      }

      try {
        // Wait for auth to be ready and get a token
        if (auth.isLoading) {
          // Delay the exchange if auth is still loading
          setTimeout(doExchange, 500);
          return;
        }

        // Ensure we have a token before proceeding
        await auth.getToken();

        // Now we can make the API call
        exchangeAttempted.current = true;

        // Check for stored OAuth2 config data
        const storedConfigKey = `oauth2_config_${short_name}`;
        const storedConfigJson = sessionStorage.getItem(storedConfigKey);
        let storedConfig = null;

        if (storedConfigJson) {
          try {
            storedConfig = JSON.parse(storedConfigJson);
            // Clean up after retrieving
            sessionStorage.removeItem(storedConfigKey);
          } catch (err) {
            console.error('Failed to parse stored OAuth2 config:', err);
          }
        }

        // Prepare request payload with config fields if available
        const payload = {
          short_name,
          code,
          ...(storedConfig ? { auth_fields: storedConfig.auth_fields, connection_name: storedConfig.connection_name } : {})
        };

        // Use a Promise ref to ensure only one request is made
        if (!exchangePromise.current) {
          exchangePromise.current = apiClient.post(`/connections/oauth2/source/code`, payload);
        }

        const response = await exchangePromise.current;

        if (!response.ok) {
          throw new Error("OAuth code exchange failed.");
        }

        // Handle success
        const returnUrl = localStorage.getItem("oauth_return_url") || "/sync/create";
        navigate(`${returnUrl}?connected=success`, { replace: true });
        localStorage.removeItem("oauth_return_url");
      } catch (err) {
        console.error('OAuth exchange error:', err);
        const returnUrl = localStorage.getItem("oauth_return_url") || "/sync/create";
        navigate(`${returnUrl}?connected=error`, { replace: true });
        localStorage.removeItem("oauth_return_url");
      }
    };

    doExchange();
  }, [searchParams, short_name, navigate, auth]);

  return (
    <div className="flex items-center justify-center h-screen">
      <div className="text-center">
        <p className="text-muted-foreground">Completing connection...</p>
      </div>
    </div>
  );
}
