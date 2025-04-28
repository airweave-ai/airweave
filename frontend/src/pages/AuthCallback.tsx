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
  const auth = useAuth();

  useEffect(() => {
    const doExchange = async () => {
      if (exchangeAttempted.current) return;

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
        const response = await apiClient.post(`/connections/oauth2/source/code`, {
          short_name,
          code,
        });

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
