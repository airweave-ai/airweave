import { useState, useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { UsageDashboard } from './UsageDashboard';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog';

import {
  CreditCard,
  Calendar,
  AlertCircle,
  ExternalLink,
  CheckCircle,
  Clock,
  XCircle,
  Zap,
  Users,
  Database,
  RefreshCw,
  ArrowUpCircle,
  ArrowDownCircle,
  MessageSquare,
  Building2,
  Mail,
  Headphones,
  MessageCircle,
  Slack,
  CalendarDays,
  Receipt,
  HelpCircle
} from 'lucide-react';
import { apiClient } from '@/lib/api';
import { toast } from 'sonner';
import { format, differenceInDays, addMonths, startOfMonth } from 'date-fns';
import { cn } from '@/lib/utils';

interface SubscriptionInfo {
  plan: string;
  status: string;
  trial_ends_at?: string;
  current_period_start?: string;
  current_period_end?: string;
  cancel_at_period_end: boolean;
  limits: {
    source_connections: number;
    entities_per_month: number;
    sync_frequency_minutes: number;
    team_members: number;
  };
  is_oss: boolean;
  has_active_subscription: boolean;
  grace_period_ends_at?: string;
  pending_plan_change?: string;
  pending_plan_change_at?: string;
}

interface BillingSettingsProps {
  organizationId: string;
}

const plans = {
  developer: {
    name: 'Developer',
    price: 89,
    description: 'Perfect for small teams and projects',
    features: [
      { icon: Database, label: '10 source connections' },
      { icon: Zap, label: '100K entities/month' },
      { icon: RefreshCw, label: 'Hourly sync' },
      { icon: Users, label: '5 team members' },
      { icon: MessageCircle, label: 'Community support' }
    ]
  },
  startup: {
    name: 'Startup',
    price: 299,
    description: 'For growing teams with higher demands',
    features: [
      { icon: Database, label: '50 source connections' },
      { icon: Zap, label: '1M entities/month' },
      { icon: RefreshCw, label: '15-min sync' },
      { icon: Users, label: '20 team members' },
      { icon: MessageCircle, label: 'Community support' }
    ]
  },
  enterprise: {
    name: 'Enterprise',
    price: 'Custom',
    description: 'Tailored solutions for large organizations',
    features: [
      { icon: Database, label: 'Unlimited connections' },
      { icon: Zap, label: 'Unlimited entities' },
      { icon: RefreshCw, label: 'Instant sync' },
      { icon: Users, label: 'Unlimited team' },
      { icon: Slack, label: 'Slack channel support' }
    ]
  }
};

export const BillingSettings = ({ organizationId }: BillingSettingsProps) => {
  const [searchParams, setSearchParams] = useSearchParams();
  const [subscription, setSubscription] = useState<SubscriptionInfo | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isCheckoutLoading, setIsCheckoutLoading] = useState(false);
  const [isPortalLoading, setIsPortalLoading] = useState(false);
  const [isCancelLoading, setIsCancelLoading] = useState(false);
  const [isReactivateLoading, setIsReactivateLoading] = useState(false);
  const [showCancelDialog, setShowCancelDialog] = useState(false);

  useEffect(() => {
    fetchSubscription();
  }, [organizationId]);

  useEffect(() => {
    if (searchParams.get('success') === 'true') {
      toast.success('Payment method added successfully! Your subscription is now active.');
      searchParams.delete('success');
      setSearchParams(searchParams);
    }
  }, []);

  const fetchSubscription = async () => {
    try {
      setIsLoading(true);
      const response = await apiClient.get('/billing/subscription');
      if (response.ok) {
        const data = await response.json();
        setSubscription(data);
      } else {
        throw new Error('Failed to fetch subscription');
      }
    } catch (error) {
      console.error('Error fetching subscription:', error);
      toast.error('Failed to load billing information');
    } finally {
      setIsLoading(false);
    }
  };

  const handleUpgrade = async (plan: 'developer' | 'startup') => {
    try {
      setIsCheckoutLoading(true);

      if (subscription?.has_active_subscription && subscription.plan !== 'trial') {
        const response = await apiClient.post('/billing/update-plan', { plan });

        if (response.ok) {
          const data = await response.json();
          if (data.message && data.message.includes('checkout at:')) {
            const urlMatch = data.message.match(/checkout at: (.+)$/);
            if (urlMatch && urlMatch[1]) {
              window.location.href = urlMatch[1];
            } else {
              throw new Error('Failed to get checkout URL');
            }
          } else {
            toast.success(data.message);
            await fetchSubscription();
          }
        } else {
          const error = await response.json();
          throw new Error(error.detail || 'Failed to update plan');
        }
      } else {
        const response = await apiClient.post('/billing/checkout-session', {
          plan,
          success_url: `${window.location.origin}/organization/settings?tab=billing&success=true`,
          cancel_url: `${window.location.origin}/organization/settings?tab=billing`
        });

        if (response.ok) {
          const { checkout_url } = await response.json();
          window.location.href = checkout_url;
        } else {
          throw new Error('Failed to create checkout session');
        }
      }
    } catch (error) {
      console.error('Error with subscription change:', error);
      toast.error(error instanceof Error ? error.message : 'Failed to process subscription change');
    } finally {
      setIsCheckoutLoading(false);
    }
  };

  const handleManageBilling = async () => {
    try {
      setIsPortalLoading(true);
      const response = await apiClient.post('/billing/portal-session', {
        return_url: `${window.location.origin}/organization/settings?tab=billing`
      });

      if (response.ok) {
        const { portal_url } = await response.json();
        window.location.href = portal_url;
      } else {
        throw new Error('Failed to create portal session');
      }
    } catch (error) {
      console.error('Error creating portal session:', error);
      toast.error('Failed to open billing portal');
    } finally {
      setIsPortalLoading(false);
    }
  };

  const handleCancelSubscription = async () => {
    try {
      setIsCancelLoading(true);
      const response = await apiClient.post('/billing/cancel', {
        immediate: false
      });

      if (response.ok) {
        const { message } = await response.json();
        toast.success(message);
        await fetchSubscription();
        setShowCancelDialog(false);
      } else {
        throw new Error('Failed to cancel subscription');
      }
    } catch (error) {
      console.error('Error canceling subscription:', error);
      toast.error('Failed to cancel subscription');
    } finally {
      setIsCancelLoading(false);
    }
  };

  const handleReactivateSubscription = async () => {
    try {
      setIsReactivateLoading(true);
      const response = await apiClient.post('/billing/reactivate');

      if (response.ok) {
        const { message } = await response.json();
        toast.success(message);
        await fetchSubscription();
      } else {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to reactivate subscription');
      }
    } catch (error) {
      console.error('Error reactivating subscription:', error);
      toast.error(error instanceof Error ? error.message : 'Failed to reactivate subscription');
    } finally {
      setIsReactivateLoading(false);
    }
  };

  const handleCancelPlanChange = async () => {
    try {
      setIsCancelLoading(true);
      const response = await apiClient.post('/billing/cancel-plan-change');

      if (response.ok) {
        const { message } = await response.json();
        toast.success(message);
        await fetchSubscription();
      } else {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to cancel plan change');
      }
    } catch (error) {
      console.error('Error canceling plan change:', error);
      toast.error(error instanceof Error ? error.message : 'Failed to cancel plan change');
    } finally {
      setIsCancelLoading(false);
    }
  };



  const getStatusBadge = (status: string) => {
    const statusConfig = {
      active: {
        icon: CheckCircle,
        label: 'ACTIVE',
        className: 'text-emerald-600 dark:text-emerald-400 bg-emerald-500/10 dark:bg-emerald-400/10 border-emerald-500/20 dark:border-emerald-400/20'
      },
      trialing: {
        icon: Clock,
        label: 'TRIAL',
        className: 'text-blue-600 dark:text-blue-400 bg-blue-500/10 dark:bg-blue-400/10 border-blue-500/20 dark:border-blue-400/20'
      },
      past_due: {
        icon: AlertCircle,
        label: 'PAST DUE',
        className: 'text-red-600 dark:text-red-400 bg-red-500/10 dark:bg-red-400/10 border-red-500/20 dark:border-red-400/20'
      },
      canceled: {
        icon: XCircle,
        label: 'CANCELED',
        className: 'text-gray-600 dark:text-gray-400 bg-gray-500/10 dark:bg-gray-400/10 border-gray-500/20 dark:border-gray-400/20'
      },
      trial_expired: {
        icon: AlertCircle,
        label: 'TRIAL EXPIRED',
        className: 'text-red-600 dark:text-red-400 bg-red-500/10 dark:bg-red-400/10 border-red-500/20 dark:border-red-400/20'
      }
    };

    const config = statusConfig[status] || {
      icon: AlertCircle,
      label: status.toUpperCase(),
      className: 'text-gray-600 dark:text-gray-400 bg-gray-500/10 dark:bg-gray-400/10 border-gray-500/20 dark:border-gray-400/20'
    };
    const Icon = config.icon;

    return (
      <span className={cn('inline-flex items-center gap-1.5 px-2 py-0.5 rounded-md border text-[10px] font-medium tracking-wider', config.className)}>
        <Icon className="w-3 h-3" />
        {config.label}
      </span>
    );
  };

  const getPlanDisplayName = (plan: string) => {
    return plans[plan]?.name || plan.charAt(0).toUpperCase() + plan.slice(1);
  };

  const getBillingInfo = () => {
    if (!subscription || !subscription.current_period_start || !subscription.current_period_end) {
      return null;
    }

    const startDate = new Date(subscription.current_period_start);
    const endDate = new Date(subscription.current_period_end);
    const daysRemaining = differenceInDays(endDate, new Date());
    const isMonthly = differenceInDays(endDate, startDate) < 35; // Roughly a month

    return {
      startDate,
      endDate,
      daysRemaining: Math.max(0, daysRemaining),
      billingCycle: isMonthly ? 'Monthly' : 'Annual',
      nextBillingDate: subscription.cancel_at_period_end ? null : endDate
    };
  };

  if (isLoading) {
    return (
      <div className="space-y-8 max-w-5xl">
        <Skeleton className="h-24 w-full rounded-lg" />
        <div className="grid gap-4 md:grid-cols-3">
          <Skeleton className="h-72 rounded-lg" />
          <Skeleton className="h-72 rounded-lg" />
          <Skeleton className="h-72 rounded-lg" />
        </div>
      </div>
    );
  }

  if (!subscription) {
    return (
      <Alert className="border-red-200 bg-red-50">
        <AlertCircle className="h-4 w-4 text-red-600" />
        <AlertDescription className="text-red-800">
          Unable to load billing information. Please try again later.
        </AlertDescription>
      </Alert>
    );
  }

  const isInitialSetup = !subscription.has_active_subscription && subscription.status === 'trialing';
  const needsSetup = isInitialSetup || subscription.status === 'trial_expired';
  const billingInfo = getBillingInfo();

  if (needsSetup) {
    return (
      <div className="max-w-2xl">
        <div className="mb-8">
          <h2 className="text-xl font-semibold mb-1">Complete Your Billing Setup</h2>
          <p className="text-sm text-muted-foreground">Choose a plan to activate your subscription</p>
        </div>

        <div className="bg-amber-50 border border-amber-200 rounded-lg p-4 mb-8">
          <div className="flex gap-3">
            <AlertCircle className="h-5 w-5 text-amber-600 flex-shrink-0 mt-0.5" />
            <div className="text-sm text-amber-800">
              <p className="font-medium mb-1">Billing setup required</p>
              <p>Please complete your billing setup to start using this organization.</p>
            </div>
          </div>
        </div>

        <div className="border border-border rounded-lg p-6">
          <h3 className="font-medium mb-4">
            {subscription.plan === 'startup' ? 'Startup' : 'Developer'} Plan Selected
          </h3>
          <div className="grid grid-cols-2 gap-4 mb-6">
            {plans[subscription.plan]?.features.slice(0, 4).map((feature, index) => {
              const Icon = feature.icon;
              return (
                <div key={index} className="flex items-center gap-3">
                  <Icon className="w-4 h-4 text-muted-foreground" />
                  <span className="text-sm">{feature.label}</span>
                </div>
              );
            })}
          </div>
          <Button
            onClick={() => window.location.href = '/billing/setup'}
            size="lg"
            className="w-full"
          >
            Complete Billing Setup
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-8 max-w-5xl">
      {/* Current Plan Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <h2 className="text-xl font-semibold">{getPlanDisplayName(subscription.plan)} Plan</h2>
          {getStatusBadge(subscription.status)}
        </div>

        <div className="flex gap-2">
          {subscription.cancel_at_period_end && subscription.current_period_end && (
            <Button
              onClick={handleReactivateSubscription}
              disabled={isReactivateLoading}
              size="sm"
              className="bg-primary hover:bg-primary/90 text-white border-0"
            >
              {isReactivateLoading && <RefreshCw className="w-4 h-4 mr-2 animate-spin" />}
              Reactivate
            </Button>
          )}

          {subscription.has_active_subscription && (
            <Button
              onClick={handleManageBilling}
              variant="ghost"
              disabled={isPortalLoading}
              size="sm"
              className="text-muted-foreground hover:text-foreground"
            >
              {isPortalLoading ? (
                <RefreshCw className="w-3.5 h-3.5 mr-1.5 animate-spin" />
              ) : (
                <CreditCard className="w-3.5 h-3.5 mr-1.5" />
              )}
              Manage Billing
            </Button>
          )}

          {subscription.has_active_subscription && !subscription.cancel_at_period_end && (
            <Button
              onClick={() => setShowCancelDialog(true)}
              variant="ghost"
              size="sm"
              className="text-destructive hover:text-destructive hover:bg-destructive/10"
            >
              Cancel
            </Button>
          )}
        </div>
      </div>

      {/* Billing Information Card */}
      {billingInfo && subscription.has_active_subscription && !subscription.status.includes('trial') && (
        <div className="border border-border/50 rounded-lg p-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-6">
              <div>
                <p className="text-sm font-medium text-foreground">{billingInfo.billingCycle} billing</p>
                <p className="text-xs text-muted-foreground">
                  Started {format(billingInfo.startDate, 'MMMM d, yyyy')}
                </p>
              </div>
            </div>
            {!subscription.cancel_at_period_end && billingInfo.nextBillingDate && (
              <div className="text-right">
                <p className="text-sm font-medium text-foreground">Renews in {billingInfo.daysRemaining} days</p>
                <p className="text-xs text-muted-foreground">
                  {format(billingInfo.nextBillingDate, 'MMMM d, yyyy')}
                </p>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Trial Information */}
      {subscription.status === 'trialing' && subscription.trial_ends_at && (
        <div className="bg-blue-50 rounded-lg p-4">
          <div className="flex items-center gap-2">
            <Clock className="w-4 h-4 text-blue-600" />
            <p className="text-sm text-blue-900">
              Trial ends {format(new Date(subscription.trial_ends_at), 'MMMM d, yyyy')}
            </p>
          </div>
        </div>
      )}

      {/* Alerts for cancellation and plan changes */}
      {subscription.cancel_at_period_end && subscription.current_period_end && (
        <Alert className="border-amber-200 bg-amber-50">
          <AlertCircle className="h-4 w-4 text-amber-600" />
          <AlertDescription className="text-amber-800">
            Subscription will cancel on {format(new Date(subscription.current_period_end), 'MMMM d, yyyy')}
          </AlertDescription>
        </Alert>
      )}

      {subscription.pending_plan_change && subscription.pending_plan_change_at && !subscription.cancel_at_period_end && (
        <Alert className="border-blue-200 bg-blue-50">
          <div className="flex items-start justify-between">
            <div className="flex items-start gap-2">
              <ArrowDownCircle className="w-4 h-4 text-blue-600 mt-0.5" />
              <AlertDescription className="text-blue-800">
                <span className="font-medium">Plan change scheduled</span>
                <br />
                Changing to {getPlanDisplayName(subscription.pending_plan_change)} on{' '}
                {format(new Date(subscription.pending_plan_change_at), 'MMMM d, yyyy')}
              </AlertDescription>
            </div>
            <Button
              variant="ghost"
              size="sm"
              onClick={handleCancelPlanChange}
              disabled={isCancelLoading}
              className="text-blue-700 hover:text-blue-800 hover:bg-blue-100 -mt-1"
            >
              Cancel change
            </Button>
          </div>
        </Alert>
      )}

      {/* Available Plans */}
      {!subscription.cancel_at_period_end && (
        <div>
          <h3 className="text-sm font-medium mb-4">Available Plans</h3>
          <div className="grid gap-4 md:grid-cols-3">
            {Object.entries(plans).map(([key, plan]) => {
              const isCurrentPlan = key === subscription.plan;
              const isUpgrade = key === 'startup' && subscription.plan === 'developer';
              const isDowngrade = key === 'developer' && subscription.plan === 'startup';
              const isEnterprise = key === 'enterprise';

              return (
                <div
                  key={key}
                  className={cn(
                    "relative border rounded-lg p-6 transition-all",
                    isCurrentPlan ? "border-primary/50 bg-primary/5" : "border-border hover:border-border/80"
                  )}
                >
                  {isCurrentPlan && (
                    <span className="absolute -top-2.5 left-4 px-2 bg-background rounded-md text-xs font-medium text-primary">
                      Current Plan
                    </span>
                  )}

                  <div className="mb-4">
                    <h4 className="font-semibold mb-1">{plan.name}</h4>
                    <p className="text-xs text-muted-foreground">{plan.description}</p>
                  </div>

                  <div className="mb-6">
                    {typeof plan.price === 'number' ? (
                      <div className="flex items-baseline gap-1">
                        <span className="text-2xl font-semibold">${plan.price}</span>
                        <span className="text-sm text-muted-foreground">/month</span>
                      </div>
                    ) : (
                      <div className="flex items-center gap-2">
                        <Building2 className="w-4 h-4 text-muted-foreground" />
                        <span className="text-lg font-semibold">Custom Pricing</span>
                      </div>
                    )}
                  </div>

                  <ul className="space-y-2.5 mb-6">
                    {plan.features.map((feature, index) => {
                      const Icon = feature.icon;
                      return (
                        <li key={index} className="flex items-center gap-2 text-xs">
                          <Icon className="w-3.5 h-3.5 text-muted-foreground" />
                          <span>{feature.label}</span>
                        </li>
                      );
                    })}
                  </ul>

                  {isCurrentPlan ? (
                    <Button variant="outline" disabled className="w-full h-9 text-sm border-border">
                      Current Plan
                    </Button>
                  ) : isEnterprise ? (
                    <Button
                      onClick={() => window.open('https://cal.com/lennert-airweave/airweave-q-a-demo', '_blank')}
                      variant="outline"
                      className="w-full h-9 text-sm border-border"
                    >
                      <MessageSquare className="w-3.5 h-3.5 mr-1.5" />
                      Talk to Founder
                    </Button>
                  ) : (
                    <Button
                      onClick={() => handleUpgrade(key as 'developer' | 'startup')}
                      disabled={isCheckoutLoading || (isDowngrade && subscription.pending_plan_change === 'developer')}
                      variant={isUpgrade ? "default" : "outline"}
                      className={cn(
                        "w-full h-9 text-sm",
                        isUpgrade ? "bg-primary hover:bg-primary/90 text-white border-0" : "border-border"
                      )}
                    >
                      {isCheckoutLoading && <RefreshCw className="w-3.5 h-3.5 mr-1.5 animate-spin" />}
                      {isUpgrade && <ArrowUpCircle className="w-3.5 h-3.5 mr-1.5" />}
                      {isDowngrade && <ArrowDownCircle className="w-3.5 h-3.5 mr-1.5" />}
                      {isUpgrade ? 'Upgrade' : isDowngrade ? 'Downgrade' : 'Switch'} to {plan.name}
                    </Button>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Usage Dashboard */}
      <UsageDashboard organizationId={organizationId} />

      {/* Support Contact */}
      <div className="border-t border-border pt-6">
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <HelpCircle className="w-3.5 h-3.5" />
          <span>Questions about billing? Contact us at <a href="mailto:hello@airweave.ai" className="text-foreground hover:underline">hello@airweave.ai</a></span>
        </div>
      </div>

      {/* Cancel Subscription Dialog */}
      <AlertDialog open={showCancelDialog} onOpenChange={setShowCancelDialog}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Cancel Subscription</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to cancel your subscription? Your subscription will remain active until the end of your current billing period.
              {subscription.current_period_end && (
                <p className="mt-2 font-medium">
                  You will have access until {format(new Date(subscription.current_period_end), 'MMMM d, yyyy')}
                </p>
              )}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Keep Subscription</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleCancelSubscription}
              disabled={isCancelLoading}
              className="bg-destructive hover:bg-destructive/90"
            >
              {isCancelLoading && <RefreshCw className="w-4 h-4 mr-2 animate-spin" />}
              Cancel Subscription
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
};
