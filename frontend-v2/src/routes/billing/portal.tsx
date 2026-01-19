import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { Loader2 } from "lucide-react";
import { useEffect, useState } from "react";
import { toast } from "sonner";

import { createPortalSession } from "@/lib/api/billing";
import { useAuth0 } from "@/lib/auth-provider";
import { authConfig } from "@/config/auth";

export const Route = createFileRoute("/billing/portal")({
  component: BillingPortalPage,
});

function BillingPortalPage() {
  const navigate = useNavigate();
  const {
    getAccessTokenSilently,
    isAuthenticated,
    isLoading: authLoading,
  } = useAuth0();
  const [hasRedirected, setHasRedirected] = useState(false);

  useEffect(() => {
    // If auth is disabled (local OSS/dev), redirect to home
    if (!authConfig.authEnabled) {
      navigate({ to: "/" });
      return;
    }

    if (authLoading || !isAuthenticated || hasRedirected) {
      return;
    }

    const redirectToPortal = async () => {
      setHasRedirected(true);
      try {
        const token = await getAccessTokenSilently();
        const returnUrl = `${window.location.origin}/`;
        const { portal_url } = await createPortalSession(token, returnUrl);

        // Redirect to Stripe Customer Portal
        window.location.href = portal_url;
      } catch (error) {
        console.error("Failed to create portal session:", error);
        toast.error("Failed to open billing portal. Please try again.");
        navigate({ to: "/" });
      }
    };

    redirectToPortal();
  }, [
    authLoading,
    isAuthenticated,
    hasRedirected,
    getAccessTokenSilently,
    navigate,
  ]);

  return (
    <div className="bg-background flex min-h-screen items-center justify-center">
      <div className="text-center">
        <Loader2 className="text-primary mx-auto mb-4 h-8 w-8 animate-spin" />
        <p className="text-muted-foreground">
          Redirecting to billing portal...
        </p>
      </div>
    </div>
  );
}
