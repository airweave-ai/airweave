import { createFileRoute, useNavigate, useSearch } from "@tanstack/react-router";
import { AlertTriangle, HelpCircle, Loader2, Mail } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import {
  Auth0ConflictError,
  createOrUpdateUser,
} from "@/lib/api/users";
import { useAuth0 } from "@/lib/auth-provider";

export const Route = createFileRoute("/callback")({
  component: CallbackPage,
  validateSearch: (search: Record<string, unknown>) => ({
    organizationName: (search.organizationName as string) || undefined,
  }),
});

function CallbackPage() {
  const { isAuthenticated, isLoading, user, logout, getAccessTokenSilently } =
    useAuth0();
  const navigate = useNavigate();
  const search = useSearch({ from: "/callback" });

  const syncAttempted = useRef(false);
  const [authConflictError, setAuthConflictError] =
    useState<Auth0ConflictError | null>(null);

  // Sync user with backend after Auth0 authentication
  useEffect(() => {
    const syncUser = async () => {
      if (
        isAuthenticated &&
        user &&
        !isLoading &&
        !syncAttempted.current &&
        !authConflictError
      ) {
        syncAttempted.current = true;

        try {
          const token = await getAccessTokenSilently();

          if (!token) {
            console.error("No token available for API call");
            navigate({ to: "/" });
            return;
          }

          const result = await createOrUpdateUser(token, {
            email: user.email || "",
            full_name: user.name,
            picture: user.picture,
            auth0_id: user.sub,
            email_verified: user.email_verified,
          });

          if (result.success) {
            navigate({ to: "/" });
          } else if (result.conflictError) {
            setAuthConflictError(result.conflictError);
          } else {
            console.error("Failed to sync user:", result.error);
            // Redirect anyway on other errors
            navigate({ to: "/" });
          }
        } catch (err) {
          console.error("Error syncing user with backend:", err);
          navigate({ to: "/" });
        }
      }
    };

    syncUser();
  }, [
    isAuthenticated,
    user,
    isLoading,
    authConflictError,
    getAccessTokenSilently,
    navigate,
  ]);

  // Auto-logout after showing Auth0 conflict error
  useEffect(() => {
    if (authConflictError) {
      const timer = setTimeout(() => {
        logout();
      }, 10000);

      return () => clearTimeout(timer);
    }
  }, [authConflictError, logout]);

  // Handle logout
  const handleLogout = () => {
    logout();
  };

  // Show Auth0 ID conflict error
  if (authConflictError) {
    return (
      <div className="bg-background flex h-screen w-full items-center justify-center">
        <div className="border-border bg-card mx-4 w-full max-w-md rounded-lg border p-6 shadow-lg">
          <div className="mb-4 flex items-center space-x-3">
            <AlertTriangle className="text-destructive h-8 w-8" />
            <h1 className="text-foreground text-xl font-semibold">
              Account Conflict
            </h1>
          </div>

          <div className="space-y-4">
            <p className="text-muted-foreground">
              This email is already associated with a different Auth0 account.
              Please try a different sign-in method or contact support.
            </p>

            <div className="bg-muted rounded-md p-4">
              <h2 className="text-foreground mb-2 flex items-center font-medium">
                <HelpCircle className="mr-2 h-4 w-4" />
                What happened?
              </h2>
              <p className="text-muted-foreground text-sm">
                You previously signed up using a different authentication method
                (Google, GitHub, or email/password).
              </p>
            </div>

            <div className="bg-muted rounded-md p-4">
              <h2 className="text-foreground mb-2 flex items-center font-medium">
                <Mail className="mr-2 h-4 w-4" />
                Next steps
              </h2>
              <ul className="text-muted-foreground space-y-1 text-sm">
                <li>• Try a different sign-in method</li>
                <li>• Contact support to merge accounts</li>
                <li>• Use a different email address</li>
              </ul>
            </div>

            <div className="flex space-x-3">
              <Button onClick={handleLogout} className="flex-1">
                Try Different Login
              </Button>
              <Button
                variant="secondary"
                onClick={() =>
                  window.open(
                    "mailto:support@airweave.ai?subject=Auth0 Account Conflict",
                    "_blank"
                  )
                }
                className="flex-1"
              >
                Contact Support
              </Button>
            </div>

            {import.meta.env.DEV && (
              <details className="mt-4">
                <summary className="text-muted-foreground cursor-pointer text-xs">
                  Debug Information (Development Only)
                </summary>
                <pre className="bg-background text-muted-foreground mt-2 overflow-x-auto rounded border p-2 text-xs">
                  {JSON.stringify(
                    {
                      existingAuth0Id: authConflictError.existing_auth0_id,
                      incomingAuth0Id: authConflictError.incoming_auth0_id,
                      userEmail: user?.email,
                    },
                    null,
                    2
                  )}
                </pre>
              </details>
            )}
          </div>
        </div>
      </div>
    );
  }

  // Loading state
  return (
    <div className="bg-background flex h-screen w-full items-center justify-center">
      <div className="flex flex-col items-center justify-center space-y-4">
        <Loader2 className="text-primary h-10 w-10 animate-spin" />
        {search.organizationName ? (
          <p className="text-muted-foreground">
            Finalizing your membership for {search.organizationName}...
          </p>
        ) : (
          <p className="text-muted-foreground">Finalizing authentication...</p>
        )}
      </div>
    </div>
  );
}
