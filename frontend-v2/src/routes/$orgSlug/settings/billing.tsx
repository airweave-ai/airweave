import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { createFileRoute } from "@tanstack/react-router";
import {
  AlertCircle,
  ArrowDownCircle,
  ArrowUpCircle,
  CalendarDays,
  CheckCircle,
  Clock,
  CreditCard,
  Database,
  HelpCircle,
  Headphones,
  Loader2,
  MessageCircle,
  MessageSquare,
  Puzzle,
  RefreshCw,
  Server,
  Settings,
  Shield,
  UserCheck,
  Users,
  XCircle,
  Zap,
} from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { SettingsLayout } from "@/components/settings-layout";
import { Alert, AlertDescription } from "@/components/ui/alert";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { usePageHeader } from "@/components/ui/page-header";
import {
  cancelPlanChange,
  cancelSubscription,
  createCheckoutSession,
  createPortalSession,
  createYearlyCheckoutSession,
  fetchSubscription,
  reactivateSubscription,
  updatePlan,
  type SubscriptionInfo,
} from "@/lib/api";
import { useAuth0 } from "@/lib/auth-provider";
import { formatDate } from "@/lib/date";
import { useOrg } from "@/lib/org-context";
import { queryKeys } from "@/lib/query-keys";
import { cn } from "@/lib/utils";

/**
 * Calculate difference in days between two dates
 */
function differenceInDays(dateA: Date, dateB: Date): number {
  const diffTime = dateA.getTime() - dateB.getTime();
  return Math.ceil(diffTime / (1000 * 60 * 60 * 24));
}

export const Route = createFileRoute("/$orgSlug/settings/billing")({
  component: BillingSettingsPage,
});

type PlanKey = "developer" | "pro" | "team" | "enterprise";

const plans: Record<
  PlanKey,
  {
    name: string;
    price: number | string;
    description: string;
    features: { icon: typeof Database; label: string }[];
  }
> = {
  developer: {
    name: "Developer",
    price: "Free",
    description: "Perfect for personal agents and side projects.",
    features: [
      { icon: Database, label: "10 source connections" },
      { icon: Zap, label: "500 queries / month" },
      { icon: Zap, label: "50K entities synced / month" },
      { icon: Users, label: "1 team member" },
      { icon: MessageCircle, label: "Community support" },
    ],
  },
  pro: {
    name: "Pro",
    price: 20,
    description: "Take your agent to the next level.",
    features: [
      { icon: Database, label: "50 source connections" },
      { icon: Zap, label: "2K queries / month" },
      { icon: Zap, label: "100K entities synced / month" },
      { icon: Users, label: "2 team members" },
      { icon: MessageCircle, label: "Email support" },
    ],
  },
  team: {
    name: "Team",
    price: 299,
    description: "For fast-moving teams that need scale and control.",
    features: [
      { icon: Database, label: "1000 source connections" },
      { icon: Zap, label: "10K queries / month" },
      { icon: Zap, label: "1M entities synced / month" },
      { icon: Users, label: "10 team members" },
      { icon: MessageCircle, label: "Dedicated Slack support" },
      { icon: MessageCircle, label: "Dedicated onboarding" },
    ],
  },
  enterprise: {
    name: "Enterprise",
    price: "Custom Pricing",
    description: "Tailored solutions for large organizations.",
    features: [
      { icon: Database, label: "Unlimited source connections" },
      { icon: Settings, label: "Custom usage limits" },
      { icon: UserCheck, label: "Tailored onboarding" },
      { icon: Headphones, label: "Dedicated priority support" },
      { icon: Puzzle, label: "Custom integrations (Optional)" },
      { icon: Server, label: "On-premise deployment (Optional)" },
      { icon: Shield, label: "SLAs (Optional)" },
    ],
  },
};

const planRank: Record<string, number> = {
  developer: 0,
  pro: 1,
  team: 2,
  enterprise: 3,
};

function getStatusBadge(status: string) {
  const statusConfig: Record<
    string,
    { icon: typeof CheckCircle; label: string; className: string }
  > = {
    active: {
      icon: CheckCircle,
      label: "ACTIVE",
      className:
        "text-emerald-600 dark:text-emerald-400 bg-emerald-500/10 dark:bg-emerald-400/10 border-emerald-500/20 dark:border-emerald-400/20",
    },
    trialing: {
      icon: Clock,
      label: "TRIAL",
      className:
        "text-blue-600 dark:text-blue-400 bg-blue-500/10 dark:bg-blue-400/10 border-blue-500/20 dark:border-blue-400/20",
    },
    past_due: {
      icon: AlertCircle,
      label: "PAST DUE",
      className:
        "text-red-600 dark:text-red-400 bg-red-500/10 dark:bg-red-400/10 border-red-500/20 dark:border-red-400/20",
    },
    canceled: {
      icon: XCircle,
      label: "CANCELED",
      className:
        "text-gray-600 dark:text-gray-400 bg-gray-500/10 dark:bg-gray-400/10 border-gray-500/20 dark:border-gray-400/20",
    },
    trial_expired: {
      icon: AlertCircle,
      label: "TRIAL EXPIRED",
      className:
        "text-red-600 dark:text-red-400 bg-red-500/10 dark:bg-red-400/10 border-red-500/20 dark:border-red-400/20",
    },
  };

  const config = statusConfig[status] || {
    icon: AlertCircle,
    label: status.toUpperCase(),
    className:
      "text-gray-600 dark:text-gray-400 bg-gray-500/10 dark:bg-gray-400/10 border-gray-500/20 dark:border-gray-400/20",
  };
  const Icon = config.icon;

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-md border px-2 py-0.5 text-[10px] font-medium tracking-wider",
        config.className
      )}
    >
      <Icon className="size-3" />
      {config.label}
    </span>
  );
}

function getPlanDisplayName(plan: string) {
  return (
    plans[plan as PlanKey]?.name || plan.charAt(0).toUpperCase() + plan.slice(1)
  );
}

function getBillingInfo(subscription: SubscriptionInfo) {
  if (!subscription.current_period_start || !subscription.current_period_end) {
    return null;
  }

  const startDate = new Date(subscription.current_period_start);
  const endDate = new Date(subscription.current_period_end);
  const daysRemaining = differenceInDays(endDate, new Date());
  const isMonthly = differenceInDays(endDate, startDate) < 35;

  return {
    startDate,
    endDate,
    daysRemaining: Math.max(0, daysRemaining),
    billingCycle: isMonthly ? "Monthly" : "Annual",
    nextBillingDate: subscription.cancel_at_period_end ? null : endDate,
  };
}

function BillingSettingsPage() {
  const { getAccessTokenSilently } = useAuth0();
  const { organization } = useOrg();
  const queryClient = useQueryClient();

  const [showCancelDialog, setShowCancelDialog] = useState(false);
  const [billingPeriod, setBillingPeriod] = useState<"monthly" | "yearly">(
    "monthly"
  );

  usePageHeader({
    title: "Settings",
    description: "Manage organization settings, preferences, and configuration",
  });

  const {
    data: subscription,
    isLoading,
    error,
  } = useQuery({
    queryKey: queryKeys.billing.subscription(organization?.id ?? ""),
    queryFn: async () => {
      const token = await getAccessTokenSilently();
      return fetchSubscription(token);
    },
    enabled: !!organization?.id,
  });

  const portalMutation = useMutation({
    mutationFn: async () => {
      const token = await getAccessTokenSilently();
      const returnUrl = window.location.href;
      return createPortalSession(token, returnUrl);
    },
    onSuccess: (data) => {
      window.location.href = data.portal_url;
    },
    onError: (error) => {
      toast.error(
        error instanceof Error ? error.message : "Failed to open billing portal"
      );
    },
  });

  const upgradeMutation = useMutation({
    mutationFn: async ({
      plan,
      period,
    }: {
      plan: "developer" | "pro" | "team";
      period: "monthly" | "yearly";
    }) => {
      const token = await getAccessTokenSilently();

      const isTargetPaid = plan === "pro" || plan === "team";
      const isCurrentPlan = plan === subscription?.plan;
      const isPeriodChangeOnly =
        isCurrentPlan &&
        period !== (subscription?.has_yearly_prepay ? "yearly" : "monthly");
      const needsCheckoutForPaid =
        isTargetPaid && !subscription?.payment_method_added;

      // Handle period changes for same plan
      if (isPeriodChangeOnly && subscription?.payment_method_added) {
        return updatePlan(token, plan, period);
      }

      // Developer plan (always monthly)
      if (!isTargetPaid) {
        return updatePlan(token, "developer", "monthly");
      }

      // Yearly billing
      if (period === "yearly") {
        if (!subscription?.payment_method_added) {
          const successUrl = `${window.location.origin}${window.location.pathname}?success=true`;
          const cancelUrl = window.location.href;
          const result = await createYearlyCheckoutSession(
            token,
            plan,
            successUrl,
            cancelUrl
          );
          window.location.href = result.checkout_url;
          return { message: "Redirecting to checkout..." };
        }
        return updatePlan(token, plan, "yearly");
      }

      // Monthly billing
      if (needsCheckoutForPaid) {
        const successUrl = `${window.location.origin}${window.location.pathname}?success=true`;
        const cancelUrl = window.location.href;
        const result = await createCheckoutSession(
          token,
          plan,
          successUrl,
          cancelUrl
        );
        window.location.href = result.checkout_url;
        return { message: "Redirecting to checkout..." };
      }

      return updatePlan(token, plan, "monthly");
    },
    onSuccess: (data) => {
      if (data.message && !data.message.includes("Redirecting")) {
        toast.success(data.message);
      }
      queryClient.invalidateQueries({
        queryKey: queryKeys.billing.subscription(organization?.id ?? ""),
      });
    },
    onError: (error) => {
      toast.error(
        error instanceof Error
          ? error.message
          : "Failed to process subscription change"
      );
    },
  });

  const cancelMutation = useMutation({
    mutationFn: async () => {
      const token = await getAccessTokenSilently();
      return cancelSubscription(token, false);
    },
    onSuccess: (data) => {
      toast.success(data.message);
      setShowCancelDialog(false);
      queryClient.invalidateQueries({
        queryKey: queryKeys.billing.subscription(organization?.id ?? ""),
      });
    },
    onError: (error) => {
      toast.error(
        error instanceof Error ? error.message : "Failed to cancel subscription"
      );
    },
  });

  const reactivateMutation = useMutation({
    mutationFn: async () => {
      const token = await getAccessTokenSilently();
      return reactivateSubscription(token);
    },
    onSuccess: (data) => {
      toast.success(data.message);
      queryClient.invalidateQueries({
        queryKey: queryKeys.billing.subscription(organization?.id ?? ""),
      });
    },
    onError: (error) => {
      toast.error(
        error instanceof Error
          ? error.message
          : "Failed to reactivate subscription"
      );
    },
  });

  const cancelPlanChangeMutation = useMutation({
    mutationFn: async () => {
      const token = await getAccessTokenSilently();
      return cancelPlanChange(token);
    },
    onSuccess: (data) => {
      toast.success(data.message);
      queryClient.invalidateQueries({
        queryKey: queryKeys.billing.subscription(organization?.id ?? ""),
      });
    },
    onError: (error) => {
      toast.error(
        error instanceof Error ? error.message : "Failed to cancel plan change"
      );
    },
  });

  const handleUpgrade = (plan: "developer" | "pro" | "team") => {
    const isTargetPaid = plan === "pro" || plan === "team";
    const targetPeriod = isTargetPaid ? billingPeriod : "monthly";
    const isCurrentPlan = plan === subscription?.plan;

    // Handle unsupported cross paths
    if (targetPeriod === "yearly" && !isCurrentPlan) {
      if (
        subscription?.plan === "team" &&
        plan === "pro" &&
        !subscription?.has_yearly_prepay
      ) {
        toast.info(
          "To get Pro yearly: Switch to Pro monthly now. After your current Team billing period ends, you can upgrade to Pro yearly with the 20% discount.",
          { duration: 7000 }
        );
        return;
      }
      if (
        subscription?.plan === "team" &&
        subscription?.has_yearly_prepay &&
        plan === "pro"
      ) {
        toast.info(
          "To switch to Pro yearly: Schedule a downgrade to Pro monthly now. When your Team yearly ends, you can then upgrade to Pro yearly with the 20% discount.",
          { duration: 7000 }
        );
        return;
      }
    }

    upgradeMutation.mutate({ plan, period: targetPeriod });
  };

  if (!organization) {
    return null;
  }

  if (isLoading) {
    return (
      <SettingsLayout organization={organization}>
        <div className="max-w-5xl space-y-8">
          <Skeleton className="h-24 w-full rounded-lg" />
          <div className="grid gap-4 md:grid-cols-4">
            <Skeleton className="h-72 rounded-lg" />
            <Skeleton className="h-72 rounded-lg" />
            <Skeleton className="h-72 rounded-lg" />
            <Skeleton className="h-72 rounded-lg" />
          </div>
        </div>
      </SettingsLayout>
    );
  }

  if (error || !subscription) {
    return (
      <SettingsLayout organization={organization}>
        <Alert className="border-red-200 bg-red-50">
          <AlertCircle className="size-4 text-red-600" />
          <AlertDescription className="text-red-800">
            {error instanceof Error
              ? error.message
              : "Unable to load billing information. Please try again later."}
          </AlertDescription>
        </Alert>
      </SettingsLayout>
    );
  }

  const isInitialSetup =
    !subscription.has_active_subscription && subscription.status === "trialing";
  const needsSetup = isInitialSetup || subscription.status === "trial_expired";
  const billingInfo = getBillingInfo(subscription);

  // Initial setup view
  if (needsSetup) {
    return (
      <SettingsLayout organization={organization}>
        <div className="max-w-2xl">
          <div className="mb-8">
            <h2 className="mb-1 text-xl font-semibold">
              Complete Your Billing Setup
            </h2>
            <p className="text-muted-foreground text-sm">
              Choose a plan to activate your subscription
            </p>
          </div>

          <div className="mb-8 rounded-lg border border-amber-200 bg-amber-50 p-4 dark:border-amber-900/50 dark:bg-amber-950/20">
            <div className="flex gap-3">
              <AlertCircle className="mt-0.5 size-5 shrink-0 text-amber-600 dark:text-amber-500" />
              <div className="text-sm text-amber-800 dark:text-amber-200">
                <p className="mb-1 font-medium">Billing setup required</p>
                <p>
                  Please complete your billing setup to start using this
                  organization.
                </p>
              </div>
            </div>
          </div>

          <div className="border-border rounded-lg border p-6">
            <h3 className="mb-4 font-medium">
              {getPlanDisplayName(subscription.plan)} Plan Selected
            </h3>
            <div className="mb-6 grid grid-cols-2 gap-4">
              {plans[subscription.plan as PlanKey]?.features
                .slice(0, 4)
                .map((feature, index) => {
                  const Icon = feature.icon;
                  return (
                    <div key={index} className="flex items-center gap-3">
                      <Icon className="text-muted-foreground size-4" />
                      <span className="text-sm">{feature.label}</span>
                    </div>
                  );
                })}
            </div>
            <Button
              onClick={() =>
                handleUpgrade(subscription.plan as "developer" | "pro" | "team")
              }
              disabled={upgradeMutation.isPending}
              size="lg"
              className="w-full"
            >
              {upgradeMutation.isPending && (
                <RefreshCw className="mr-2 size-4 animate-spin" />
              )}
              Complete Billing Setup
            </Button>
          </div>
        </div>
      </SettingsLayout>
    );
  }

  return (
    <SettingsLayout organization={organization}>
      <div className="max-w-5xl space-y-8">
        {/* Current Plan Header */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <h2 className="text-xl font-semibold">
              {getPlanDisplayName(subscription.plan)} Plan
            </h2>
            {getStatusBadge(subscription.status)}
          </div>

          <div className="flex gap-2">
            {subscription.cancel_at_period_end &&
              subscription.current_period_end && (
                <Button
                  onClick={() => reactivateMutation.mutate()}
                  disabled={reactivateMutation.isPending}
                  size="sm"
                  className="bg-primary hover:bg-primary/90 border-0 text-white"
                >
                  {reactivateMutation.isPending && (
                    <RefreshCw className="mr-2 size-4 animate-spin" />
                  )}
                  Reactivate
                </Button>
              )}

            {subscription.has_active_subscription && (
              <Button
                onClick={() => portalMutation.mutate()}
                variant="ghost"
                disabled={portalMutation.isPending}
                size="sm"
                className="text-muted-foreground hover:text-foreground"
              >
                {portalMutation.isPending ? (
                  <RefreshCw className="mr-1.5 size-3.5 animate-spin" />
                ) : (
                  <CreditCard className="mr-1.5 size-3.5" />
                )}
                Manage Billing
              </Button>
            )}

            {subscription.has_active_subscription &&
              !subscription.cancel_at_period_end && (
                <Button
                  onClick={() => setShowCancelDialog(true)}
                  variant="ghost"
                  size="sm"
                  className="text-destructive hover:bg-destructive/10 hover:text-destructive"
                >
                  Cancel
                </Button>
              )}
          </div>
        </div>

        {/* Yearly prepay indicator */}
        {subscription.has_yearly_prepay &&
          subscription.yearly_prepay_expires_at && (
            <div className="bg-muted/40 border-border/50 flex items-center justify-between rounded-lg border p-3">
              <div className="flex items-center gap-2 text-xs">
                <CalendarDays className="text-muted-foreground size-3.5" />
                <span className="text-muted-foreground">
                  Yearly prepay active &bull; Expires{" "}
                  {formatDate(subscription.yearly_prepay_expires_at, "long")}
                </span>
              </div>
              <div className="text-muted-foreground text-[11px]">
                Plan downgrades will take effect at yearly expiry
              </div>
            </div>
          )}

        {/* Billing Information Card */}
        {billingInfo &&
          subscription.has_active_subscription &&
          !subscription.status.includes("trial") && (
            <div className="border-border/50 rounded-lg border p-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-6">
                  <div>
                    <p className="text-foreground text-sm font-medium">
                      {billingInfo.billingCycle} billing
                    </p>
                    <p className="text-muted-foreground text-xs">
                      Started{" "}
                      {formatDate(billingInfo.startDate.toISOString(), "long")}
                    </p>
                  </div>
                </div>
                {!subscription.cancel_at_period_end &&
                  billingInfo.nextBillingDate && (
                    <div className="text-right">
                      <p className="text-foreground text-sm font-medium">
                        Renews in {billingInfo.daysRemaining} days
                      </p>
                      <p className="text-muted-foreground text-xs">
                        {formatDate(
                          billingInfo.nextBillingDate.toISOString(),
                          "long"
                        )}
                      </p>
                    </div>
                  )}
              </div>
            </div>
          )}

        {/* Trial Information */}
        {subscription.status === "trialing" && subscription.trial_ends_at && (
          <div className="rounded-lg bg-blue-50 p-4 dark:bg-blue-950/20">
            <div className="flex items-center gap-2">
              <Clock className="size-4 text-blue-600 dark:text-blue-400" />
              <p className="text-sm text-blue-900 dark:text-blue-100">
                Trial ends {formatDate(subscription.trial_ends_at, "long")}
              </p>
            </div>
          </div>
        )}

        {/* Alerts for plan changes and cancellation */}
        {subscription.pending_plan_change &&
          subscription.pending_plan_change_at && (
            <Alert className="border-blue-200 bg-blue-50 dark:border-blue-900/50 dark:bg-blue-950/20">
              <div className="flex items-start justify-between">
                <div className="flex items-start gap-2">
                  <ArrowDownCircle className="mt-0.5 size-4 text-blue-600 dark:text-blue-400" />
                  <AlertDescription className="text-blue-800 dark:text-blue-200">
                    <span className="font-medium">Plan change scheduled</span>
                    <br />
                    {subscription.has_yearly_prepay ? (
                      <>
                        Changing to{" "}
                        {getPlanDisplayName(subscription.pending_plan_change)}{" "}
                        at end of yearly prepay on{" "}
                        {formatDate(
                          subscription.pending_plan_change_at,
                          "long"
                        )}
                      </>
                    ) : (
                      <>
                        Changing to{" "}
                        {getPlanDisplayName(subscription.pending_plan_change)}{" "}
                        on{" "}
                        {formatDate(
                          subscription.pending_plan_change_at,
                          "long"
                        )}
                      </>
                    )}
                  </AlertDescription>
                </div>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => cancelPlanChangeMutation.mutate()}
                  disabled={cancelPlanChangeMutation.isPending}
                  className="-mt-1 text-blue-700 hover:bg-blue-100 hover:text-blue-800 dark:text-blue-300 dark:hover:bg-blue-900/50"
                >
                  Cancel change
                </Button>
              </div>
            </Alert>
          )}

        {!subscription.pending_plan_change &&
          subscription.cancel_at_period_end &&
          subscription.current_period_end && (
            <Alert className="border-amber-200 bg-amber-50 dark:border-amber-900/50 dark:bg-amber-950/20">
              <AlertCircle className="size-4 text-amber-600 dark:text-amber-500" />
              <AlertDescription className="text-amber-800 dark:text-amber-200">
                Subscription will cancel on{" "}
                {formatDate(subscription.current_period_end, "long")}
              </AlertDescription>
            </Alert>
          )}

        {/* Available Plans & Period Toggle */}
        {(!subscription.cancel_at_period_end ||
          subscription.pending_plan_change) && (
          <div>
            <div className="mb-8 flex items-center justify-between">
              <h3 className="text-sm font-medium">Available Plans</h3>
              <div className="relative">
                <div className="bg-muted relative inline-flex items-center rounded-lg border p-1 shadow-sm">
                  {/* Sliding background indicator */}
                  <div
                    className={cn(
                      "bg-blue/20 absolute top-1 h-[calc(100%-8px)] rounded-md shadow-sm transition-all duration-200",
                      billingPeriod === "monthly"
                        ? "left-1 w-[80px]"
                        : "left-[80px] w-[140px]"
                    )}
                  />
                  <button
                    type="button"
                    onClick={() => setBillingPeriod("monthly")}
                    className={cn(
                      "relative z-10 w-[80px] rounded-md px-4 py-2 text-sm transition-all",
                      billingPeriod === "monthly"
                        ? "text-foreground"
                        : "text-muted-foreground hover:text-foreground"
                    )}
                  >
                    Monthly
                  </button>
                  <button
                    type="button"
                    onClick={() => setBillingPeriod("yearly")}
                    className={cn(
                      "relative z-10 flex w-[140px] items-center justify-center gap-2 rounded-md px-4 py-2 text-sm transition-all",
                      billingPeriod === "yearly"
                        ? "text-foreground"
                        : "text-muted-foreground hover:text-foreground"
                    )}
                  >
                    Yearly
                    <span className="bg-primary/10 text-primary rounded px-1.5 py-0.5 text-xs">
                      Save 20%
                    </span>
                  </button>
                </div>
                {/* Info message */}
                <div
                  className={cn(
                    "absolute top-full right-0 mt-1 max-w-sm transition-opacity duration-200",
                    billingPeriod === "yearly"
                      ? "opacity-100"
                      : "pointer-events-none opacity-0"
                  )}
                >
                  <p className="text-muted-foreground text-right text-xs whitespace-nowrap">
                    {subscription.has_yearly_prepay &&
                    subscription.yearly_prepay_expires_at
                      ? `Your yearly discount expires ${formatDate(subscription.yearly_prepay_expires_at, "short")}. Renew to keep saving 20%.`
                      : "Yearly plans renew at monthly rates after 12 months. Renew yearly anytime to keep the 20% discount."}
                  </p>
                </div>
              </div>
            </div>

            <div className="grid gap-4 md:grid-cols-4">
              {(Object.keys(plans) as PlanKey[]).map((key) => {
                const plan = plans[key];
                const isCurrentPlan = key === subscription.plan;
                const isCurrentPeriod = subscription.has_yearly_prepay
                  ? billingPeriod === "yearly"
                  : billingPeriod === "monthly";
                const isCurrentPlanAndPeriod = isCurrentPlan && isCurrentPeriod;

                const currentRank = planRank[subscription.plan] ?? -1;
                const targetRank = planRank[key] ?? -1;
                const isUpgrade = targetRank > currentRank;
                const isDowngrade = targetRank < currentRank;
                const isEnterprise = key === "enterprise";
                const isEligibleYearly = key === "pro" || key === "team";
                const isPeriodChange =
                  isCurrentPlan && !isCurrentPlanAndPeriod && isEligibleYearly;

                return (
                  <div
                    key={key}
                    className={cn(
                      "border-border relative flex h-full flex-col rounded-lg border p-6 transition-all",
                      isCurrentPlan
                        ? "border-primary/50 bg-primary/5"
                        : "hover:border-border/80"
                    )}
                  >
                    {isCurrentPlanAndPeriod && (
                      <span className="bg-background text-primary absolute -top-2.5 left-4 rounded-md px-2 text-xs font-medium">
                        Current Plan
                      </span>
                    )}

                    <div className="mb-4">
                      <h4 className="mb-1 font-semibold">{plan.name}</h4>
                      <p className="text-muted-foreground text-xs">
                        {plan.description}
                      </p>
                    </div>

                    <div className="mb-6">
                      {typeof plan.price === "number" ? (
                        <div className="flex items-baseline gap-1">
                          <span className="text-2xl font-semibold">
                            {billingPeriod === "yearly" && isEligibleYearly
                              ? key === "pro"
                                ? "$16"
                                : "$239"
                              : `$${plan.price}`}
                          </span>
                          <span className="text-muted-foreground text-sm">
                            {billingPeriod === "yearly" && isEligibleYearly ? (
                              <>
                                /month
                                <br />
                                (billed yearly)
                              </>
                            ) : (
                              "/month"
                            )}
                          </span>
                        </div>
                      ) : (
                        <div className="flex items-center gap-2">
                          <span className="text-lg font-semibold">
                            {plan.price}
                          </span>
                        </div>
                      )}
                    </div>

                    <ul className="mb-6 space-y-2.5">
                      {plan.features.map((feature, index) => {
                        const Icon = feature.icon;
                        return (
                          <li
                            key={index}
                            className="flex items-center gap-2 text-xs"
                          >
                            <Icon className="text-muted-foreground size-3.5" />
                            <span>{feature.label}</span>
                          </li>
                        );
                      })}
                    </ul>

                    {isCurrentPlanAndPeriod ? (
                      <Button
                        variant="outline"
                        disabled
                        className="border-border mt-auto h-9 w-full text-xs"
                      >
                        Current Plan
                      </Button>
                    ) : isPeriodChange ? (
                      <Button
                        onClick={() =>
                          handleUpgrade(key as "developer" | "pro" | "team")
                        }
                        disabled={upgradeMutation.isPending}
                        variant="outline"
                        className="border-primary text-primary hover:border-primary/80 hover:bg-primary/10 mt-auto h-9 w-full text-xs"
                      >
                        {upgradeMutation.isPending && (
                          <RefreshCw className="mr-1 size-3 animate-spin" />
                        )}
                        {billingPeriod === "yearly"
                          ? "Switch to Yearly"
                          : "Switch to Monthly"}
                      </Button>
                    ) : isEnterprise ? (
                      <Button
                        onClick={() =>
                          window.open(
                            "https://cal.com/lennert-airweave/airweave-demo",
                            "_blank"
                          )
                        }
                        variant="outline"
                        className="border-border hover:border-primary/80 hover:bg-primary/10 hover:text-primary mt-auto h-9 w-full text-xs"
                      >
                        <MessageSquare className="mr-1 size-3" />
                        Book a Call
                      </Button>
                    ) : (
                      <Button
                        onClick={() =>
                          handleUpgrade(key as "developer" | "pro" | "team")
                        }
                        disabled={upgradeMutation.isPending}
                        variant="outline"
                        className={cn(
                          "mt-auto h-9 w-full text-xs",
                          isUpgrade
                            ? "border-primary text-primary hover:border-primary/80 hover:bg-primary/10"
                            : "border-border"
                        )}
                      >
                        {upgradeMutation.isPending && (
                          <RefreshCw className="mr-1 size-3 animate-spin" />
                        )}
                        {isUpgrade && <ArrowUpCircle className="mr-1 size-3" />}
                        {isDowngrade && (
                          <ArrowDownCircle className="mr-1 size-3" />
                        )}
                        {isUpgrade
                          ? "Upgrade"
                          : isDowngrade
                            ? "Downgrade"
                            : "Switch"}
                      </Button>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* Support Contact */}
        <div className="border-border border-t pt-6">
          <div className="text-muted-foreground flex items-center gap-2 text-xs">
            <HelpCircle className="size-3.5" />
            <span>
              Questions about billing? Contact us at{" "}
              <a
                href="mailto:hello@airweave.ai"
                className="text-foreground hover:underline"
              >
                hello@airweave.ai
              </a>
            </span>
          </div>
        </div>
      </div>

      {/* Cancel Subscription Dialog */}
      <AlertDialog open={showCancelDialog} onOpenChange={setShowCancelDialog}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Cancel Subscription</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to cancel your subscription? Your
              subscription will remain active until the end of your current
              billing period.
              {subscription.current_period_end && (
                <p className="mt-2 font-medium">
                  You will have access until{" "}
                  {formatDate(subscription.current_period_end, "long")}
                </p>
              )}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Keep Subscription</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => cancelMutation.mutate()}
              disabled={cancelMutation.isPending}
              className="bg-destructive hover:bg-destructive/90"
            >
              {cancelMutation.isPending && (
                <Loader2 className="mr-2 size-4 animate-spin" />
              )}
              Cancel Subscription
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </SettingsLayout>
  );
}
