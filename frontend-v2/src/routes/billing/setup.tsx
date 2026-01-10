import { useQuery } from "@tanstack/react-query";
import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { AlertCircle, Check, ChevronRight, Loader2 } from "lucide-react";
import { useEffect, useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { authConfig } from "@/config/auth";
import { useIsDark } from "@/hooks/use-is-dark";
import { createCheckoutSession, fetchSubscription } from "@/lib/api/billing";
import { useAuth0 } from "@/lib/auth-provider";
import { queryKeys } from "@/lib/query-keys";

export const Route = createFileRoute("/billing/setup")({
  component: BillingSetupPage,
});

function BillingSetupPage() {
  const navigate = useNavigate();
  const isDark = useIsDark();
  const {
    isAuthenticated,
    isLoading: authLoading,
    getAccessTokenSilently,
  } = useAuth0();
  const [isRedirecting, setIsRedirecting] = useState(false);
  const [isPolling, setIsPolling] = useState(false);

  // Fetch subscription info
  const { data: subscription, isLoading: subscriptionLoading } = useQuery({
    queryKey: queryKeys.billing.currentSubscription,
    queryFn: async () => {
      const token = await getAccessTokenSilently();
      return fetchSubscription(token);
    },
    enabled: isAuthenticated && !authLoading && authConfig.authEnabled,
    refetchInterval: isPolling ? 2000 : false,
    staleTime: 0,
  });

  // Redirect if auth is disabled
  useEffect(() => {
    if (!authConfig.authEnabled) {
      navigate({ to: "/" });
    }
  }, [navigate]);

  // Check if subscription became active and redirect
  useEffect(() => {
    if (
      subscription?.has_active_subscription &&
      subscription?.status === "active"
    ) {
      toast.success("Subscription activated");
      navigate({ to: "/billing/success" });
    }
  }, [subscription, navigate]);

  // Start polling when not active
  useEffect(() => {
    if (subscription && !subscription.has_active_subscription && !isPolling) {
      setIsPolling(true);
      // Stop polling after 30 seconds
      const timeout = setTimeout(() => {
        setIsPolling(false);
      }, 30000);
      return () => clearTimeout(timeout);
    }
  }, [subscription, isPolling]);

  const handleSetupPayment = async () => {
    if (!subscription) {
      toast.error("Unable to load subscription info");
      return;
    }

    // Developer plan doesn't need checkout - it activates via webhook
    if (subscription.plan === "developer") {
      toast.error(
        "Awaiting activation for Developer plan. Please ensure webhooks are configured."
      );
      return;
    }

    setIsRedirecting(true);
    try {
      const token = await getAccessTokenSilently();
      const plan = subscription.plan || "pro";
      const successUrl = `${window.location.origin}/billing/success?session_id={CHECKOUT_SESSION_ID}`;
      const cancelUrl = `${window.location.origin}/billing/setup`;

      const { checkout_url } = await createCheckoutSession(
        token,
        plan,
        successUrl,
        cancelUrl
      );

      window.location.href = checkout_url;
    } catch (error) {
      console.error("Failed to setup payment:", error);
      toast.error("Failed to setup payment. Please try again.");
      setIsRedirecting(false);
    }
  };

  const handleManageSubscription = () => {
    navigate({ to: "/billing/portal" });
  };

  const isCheckingStatus = authLoading || subscriptionLoading;
  const hasActiveSubscription = subscription?.has_active_subscription;
  const isInitialSetup = !hasActiveSubscription;
  const selectedPlan = subscription?.plan || "pro";
  const isPastDue = subscription?.status === "past_due";

  if (isCheckingStatus) {
    return (
      <div className="bg-background flex min-h-screen items-center justify-center">
        <Loader2 className="text-primary/60 h-6 w-6 animate-spin" />
      </div>
    );
  }

  return (
    <div className="bg-background flex min-h-screen items-center justify-center p-4">
      <div className="w-full max-w-xl">
        {/* Header with logo */}
        <div className="mb-12 text-center">
          <img
            src={
              isDark
                ? "/airweave-logo-svg-white-darkbg.svg"
                : "/airweave-logo-svg-lightbg-blacklogo.svg"
            }
            alt="Airweave"
            className="mx-auto mb-2 h-8 w-auto"
            style={{ maxWidth: "180px" }}
          />
          <p className="text-muted-foreground text-xs">Build smarter agents</p>
        </div>

        {/* Main content */}
        <div className="space-y-8">
          <div className="space-y-2 text-center">
            <h1 className="text-2xl font-normal">
              {isInitialSetup ? "Complete Your Setup" : "Update Payment Method"}
            </h1>
            <p className="text-muted-foreground">
              {isInitialSetup
                ? "Add a payment method to activate your subscription"
                : "Update your payment method to continue using Airweave"}
            </p>
          </div>

          {/* Status Alert */}
          {isPastDue && (
            <div className="rounded-lg border border-amber-200 bg-amber-50 p-4 dark:border-amber-900/50 dark:bg-amber-950/20">
              <div className="flex gap-3">
                <AlertCircle className="mt-0.5 h-5 w-5 flex-shrink-0 text-amber-600 dark:text-amber-500" />
                <div className="text-sm text-amber-800 dark:text-amber-200">
                  <p className="mb-1 font-medium">Payment failed</p>
                  <p>
                    Your last payment failed. Please update your payment method
                    to continue.
                  </p>
                </div>
              </div>
            </div>
          )}

          {/* Plan Details */}
          <PlanDetails plan={selectedPlan} />

          {/* Action Button */}
          <div className="pt-4">
            {hasActiveSubscription && isPastDue ? (
              <Button
                onClick={handleManageSubscription}
                disabled={isRedirecting}
                className="w-full"
              >
                <span>Update Payment Method</span>
                <ChevronRight className="ml-2 h-4 w-4" />
              </Button>
            ) : (
              <div className="flex w-full justify-center">
                <Button
                  onClick={handleSetupPayment}
                  disabled={isRedirecting}
                  className="px-6"
                >
                  {isRedirecting ? (
                    <>
                      <span>Setting up payment</span>
                      <Loader2 className="ml-2 h-4 w-4 animate-spin" />
                    </>
                  ) : (
                    <>
                      <span>
                        {isInitialSetup
                          ? "Complete Setup"
                          : "Update Payment Method"}
                      </span>
                      <ChevronRight className="ml-2 h-4 w-4" />
                    </>
                  )}
                </Button>
              </div>
            )}
          </div>

          {/* Polling state */}
          {isPolling && (
            <p className="text-muted-foreground mt-2 text-center text-xs">
              Waiting for Stripe confirmation... this may take a few seconds.
            </p>
          )}

          {/* Additional Info */}
          <p className="text-muted-foreground/70 text-center text-xs">
            {isInitialSetup
              ? "Your subscription will start immediately."
              : "Update your payment method to continue your subscription."}
          </p>
        </div>
      </div>
    </div>
  );
}

interface PlanDetailsProps {
  plan: string;
}

function PlanDetails({ plan }: PlanDetailsProps) {
  const isTeam = plan === "team";

  return (
    <div className="border-border/50 space-y-4 rounded-lg border p-6">
      <div className="space-y-1">
        <h3 className="text-lg font-normal">{isTeam ? "Team" : "Pro"} Plan</h3>
        <p className="text-muted-foreground text-sm">
          {isTeam
            ? "For fast-moving teams that need scale and control"
            : "Take your agent to the next level"}
        </p>
      </div>

      <div className="space-y-3">
        {isTeam ? (
          <>
            <PlanFeature>$299 per month</PlanFeature>
            <PlanFeature>1000 sources</PlanFeature>
            <PlanFeature>10K queries per month</PlanFeature>
            <PlanFeature>1M entities synced per month</PlanFeature>
            <PlanFeature>Up to 10 team members</PlanFeature>
            <PlanFeature>Dedicated Slack support</PlanFeature>
            <PlanFeature>Dedicated onboarding</PlanFeature>
          </>
        ) : (
          <>
            <PlanFeature>$20 per month</PlanFeature>
            <PlanFeature>50 sources</PlanFeature>
            <PlanFeature>2K queries per month</PlanFeature>
            <PlanFeature>100K entities synced per month</PlanFeature>
            <PlanFeature>Up to 2 team members</PlanFeature>
            <PlanFeature>Email support</PlanFeature>
          </>
        )}
      </div>
    </div>
  );
}

function PlanFeature({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex items-center gap-3">
      <Check className="text-primary/70 h-4 w-4 flex-shrink-0" />
      <span className="text-sm">{children}</span>
    </div>
  );
}
