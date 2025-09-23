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
  HelpCircle,
  Settings,
  UserCheck,
  Puzzle,
  Server,
  Shield
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
  payment_method_added?: boolean;
  has_yearly_prepay?: boolean;
  yearly_prepay_started_at?: string;
  yearly_prepay_expires_at?: string;
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
    price: 'Free',
    description: 'Perfect for personal agents and side projects.',
    features: [
      { icon: Database, label: '10 source connections' },
      { icon: Zap, label: '500 queries / month' },
      { icon: Zap, label: '50K entities synced / month' },
      { icon: Users, label: '1 team member' },
      { icon: MessageCircle, label: 'Community support' }
    ]
  },
  pro: {
    name: 'Pro',
    price: 20,
    description: 'Take your agent to the next level.',
    features: [
      { icon: Database, label: '50 source connections' },
      { icon: Zap, label: '2K queries / month' },
      { icon: Zap, label: '100K entities synced / month' },
      { icon: Users, label: '2 team members' },
      { icon: MessageCircle, label: 'Email support' }
    ]
  },
  team: {
    name: 'Team',
    price: 299,
    description: 'For fast-moving teams that need scale and control.',
    features: [
      { icon: Database, label: '1000 source connections' },
      { icon: Zap, label: '10K queries / month' },
      { icon: Zap, label: '1M entities synced / month' },
      { icon: Users, label: '10 team members' },
      { icon: MessageCircle, label: 'Dedicated Slack support' },
      { icon: MessageCircle, label: 'Dedicated onboarding' }
    ]
  },
  enterprise: {
    name: 'Enterprise',
    price: 'Custom Pricing',
    description: 'Tailored solutions for large organizations.',
    features: [
      { icon: Database, label: 'Unlimited source connections' },
      { icon: Settings, label: 'Custom usage limits' },
      { icon: UserCheck, label: 'Tailored onboarding' },
      { icon: Headphones, label: 'Dedicated priority support' },
      { icon: Puzzle, label: 'Custom integrations (Optional)' },
      { icon: Server, label: 'On-premise deployment (Optional)' },
      { icon: Shield, label: 'SLAs (Optional)' }
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
  const [billingPeriod, setBillingPeriod] = useState<'monthly' | 'yearly'>('monthly');

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

  const handleUpgrade = async (plan: 'developer' | 'pro' | 'team') => {
    try {
      setIsCheckoutLoading(true);

      const isTargetPaid = plan === 'pro' || plan === 'team';
      const targetPeriod: 'monthly' | 'yearly' = isTargetPaid ? billingPeriod : 'monthly';
      const isCurrentPlan = plan === subscription?.plan;
      const isPeriodChangeOnly = isCurrentPlan && targetPeriod !== (subscription?.has_yearly_prepay ? 'yearly' : 'monthly');
      const needsCheckoutForPaid = isTargetPaid && !subscription?.payment_method_added;

      // Unsupported cross paths messaging (frontend UX only)
      if (targetPeriod === 'yearly' && !isCurrentPlan) {
        // team monthly -> pro yearly is not allowed directly
        if (subscription?.plan === 'team' && plan === 'pro' && !subscription?.has_yearly_prepay) {
          toast.info(
            'To get Pro yearly: Switch to Pro monthly now. After your current Team billing period ends, you can upgrade to Pro yearly with the 20% discount.',
            { duration: 7000 }
          );
          return;
        }
        // team yearly -> pro yearly: suggest the fair path
        if (subscription?.plan === 'team' && subscription?.has_yearly_prepay && plan === 'pro') {
          toast.info(
            'To switch to Pro yearly: Schedule a downgrade to Pro monthly now. When your Team yearly ends, you can then upgrade to Pro yearly with the 20% discount.',
            { duration: 7000 }
          );
          return;
        }
      }

      if (!isTargetPaid) {
        // Developer (always monthly)
        const response = await apiClient.post('/billing/update-plan', { plan: 'developer', period: 'monthly' });
        if (response.ok) {
          const data = await response.json();
          toast.success(data.message || 'Switched to Developer plan');
          await fetchSubscription();
        } else {
          const error = await response.json().catch(() => ({}));
          throw new Error(error.detail || 'Failed to switch to Developer plan');
        }
        return;
      }

      if (targetPeriod === 'yearly') {
        // For same-plan period changes (e.g., Team monthly → Team yearly), always use update-plan if payment method exists
        // For plan changes to yearly, use checkout if no payment method
        if (isPeriodChangeOnly && subscription?.payment_method_added) {
          // Same plan, just changing period - use update endpoint
          const response = await apiClient.post('/billing/update-plan', { plan, period: 'yearly' });
          if (response.ok) {
            const data = await response.json();
            toast.success(data.message || 'Switched to yearly billing');
            await fetchSubscription();
          } else {
            const error = await response.json().catch(() => ({}));
            throw new Error(error.detail || 'Failed to switch to yearly billing');
          }
          return;
        }

        // No payment method → use checkout
        if (!subscription?.payment_method_added) {
          const response = await apiClient.post('/billing/yearly/checkout-session', {
            plan,
            success_url: `${window.location.origin}/organization/settings?tab=billing&success=true`,
            cancel_url: `${window.location.origin}/organization/settings?tab=billing`
          });
          if (response.ok) {
            const { checkout_url } = await response.json();
            window.location.href = checkout_url;
          } else {
            const err = await response.json().catch(() => ({}));
            throw new Error(err.detail || 'Failed to create yearly checkout session');
          }
          return;
        }

        // Has PM and upgrading to different yearly plan → backend handles coupon+credit
        const response = await apiClient.post('/billing/update-plan', { plan, period: 'yearly' });
        if (response.ok) {
          const data = await response.json();
          toast.success(data.message || 'Subscription updated');
          await fetchSubscription();
        } else {
          const error = await response.json().catch(() => ({}));
          throw new Error(error.detail || 'Failed to update to yearly plan');
        }
        return;
      }

      // Monthly path
      if (isTargetPaid && !needsCheckoutForPaid) {
        const response = await apiClient.post('/billing/update-plan', { plan, period: 'monthly' });
        if (response.ok) {
          const data = await response.json();
          toast.success(data.message);
          await fetchSubscription();
        } else {
          const error = await response.json();
          throw new Error(error.detail || 'Failed to update plan');
        }
      } else if (isTargetPaid && needsCheckoutForPaid) {
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

      {/* Yearly prepay indicator */}
      {subscription.has_yearly_prepay && subscription.yearly_prepay_expires_at && (
        <div className="flex items-center justify-between border border-border/50 rounded-lg p-3 bg-muted/40">
          <div className="flex items-center gap-2 text-xs">
            <CalendarDays className="w-3.5 h-3.5 text-muted-foreground" />
            <span className="text-muted-foreground">
              Yearly prepay active • Expires {format(new Date(subscription.yearly_prepay_expires_at), 'MMMM d, yyyy')}
            </span>
          </div>
          <div className="text-[11px] text-muted-foreground">
            Plan downgrades will take effect at yearly expiry
          </div>
        </div>
      )}

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

      {/* Alerts for plan changes and cancellation */}
      {subscription.pending_plan_change && subscription.pending_plan_change_at && (
        <Alert className="border-blue-200 bg-blue-50">
          <div className="flex items-start justify-between">
            <div className="flex items-start gap-2">
              <ArrowDownCircle className="w-4 h-4 text-blue-600 mt-0.5" />
              <AlertDescription className="text-blue-800">
                <span className="font-medium">Plan change scheduled</span>
                <br />
                {subscription.has_yearly_prepay ? (
                  <>
                    Changing to {getPlanDisplayName(subscription.pending_plan_change)} at end of yearly prepay on{' '}
                    {format(new Date(subscription.pending_plan_change_at), 'MMMM d, yyyy')}
                  </>
                ) : (
                  <>
                    Changing to {getPlanDisplayName(subscription.pending_plan_change)} on{' '}
                    {format(new Date(subscription.pending_plan_change_at), 'MMMM d, yyyy')}
                  </>
                )}
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

      {!subscription.pending_plan_change && subscription.cancel_at_period_end && subscription.current_period_end && (
        <Alert className="border-amber-200 bg-amber-50">
          <AlertCircle className="h-4 w-4 text-amber-600" />
          <AlertDescription className="text-amber-800">
            Subscription will cancel on {format(new Date(subscription.current_period_end), 'MMMM d, yyyy')}
          </AlertDescription>
        </Alert>
      )}

      {/* Available Plans & Period Toggle */}
      {(!subscription.cancel_at_period_end || subscription.pending_plan_change) && (
        <div>
          <div className="flex items-center justify-between mb-8">
            <h3 className="text-sm font-medium">Available Plans</h3>
            <div className="relative">
              <div className="relative inline-flex items-center p-1 bg-muted rounded-lg shadow-sm border">
                {/* Sliding background indicator - dynamically sized */}
                <div
                  className={cn(
                    'absolute top-1 h-[calc(100%-8px)] rounded-md bg-blue/20 shadow-sm transition-all duration-200',
                    billingPeriod === 'monthly' ? 'left-1 w-[80px]' : 'left-[80px] w-[140px]'
                  )}
                />
                <button
                  type="button"
                  onClick={() => setBillingPeriod('monthly')}
                  className={cn(
                    'relative z-10 px-4 py-2 text-sm rounded-md transition-all w-[80px]',
                    billingPeriod === 'monthly'
                      ? 'text-foreground'
                      : 'text-muted-foreground hover:text-foreground'
                  )}
                >
                  Monthly
                </button>
                <button
                  type="button"
                  onClick={() => setBillingPeriod('yearly')}
                  className={cn(
                    'relative z-10 px-4 py-2 text-sm rounded-md transition-all flex items-center gap-2 w-[140px] justify-center',
                    billingPeriod === 'yearly'
                      ? 'text-foreground'
                      : 'text-muted-foreground hover:text-foreground'
                  )}
                >
                  Yearly
                  <span className="text-xs bg-primary/10 text-primary px-1.5 py-0.5 rounded">
                    Save 20%
                  </span>
                </button>
              </div>
              {/* Absolute positioned message - doesn't affect layout */}
              <div className={cn(
                "absolute top-full mt-1 right-0 max-w-sm transition-opacity duration-200",
                billingPeriod === 'yearly' ? 'opacity-100' : 'opacity-0 pointer-events-none'
              )}>
                <p className="text-xs text-muted-foreground text-right whitespace-nowrap">
                  {subscription.has_yearly_prepay && subscription.yearly_prepay_expires_at
                    ? `Your yearly discount expires ${format(new Date(subscription.yearly_prepay_expires_at), 'MMM d, yyyy')}. Renew to keep saving 20%.`
                    : 'Yearly plans renew at monthly rates after 12 months. Renew yearly anytime to keep the 20% discount.'}
                </p>
              </div>
            </div>
          </div>
          <div className="grid gap-4 md:grid-cols-4">
            {Object.entries(plans).map(([key, plan]) => {
              // Check if this is the current plan AND period
              const isCurrentPlan = key === subscription.plan;
              const isCurrentPeriod = subscription.has_yearly_prepay ? billingPeriod === 'yearly' : billingPeriod === 'monthly';
              const isCurrentPlanAndPeriod = isCurrentPlan && isCurrentPeriod;

              const planRank: Record<string, number> = { developer: 0, pro: 1, team: 2, enterprise: 3 };
              const currentRank = planRank[subscription.plan] ?? -1;
              const targetRank = planRank[key] ?? -1;
              const isUpgrade = targetRank > currentRank;
              const isDowngrade = targetRank < currentRank;
              const isEnterprise = key === 'enterprise';
              const isEligibleYearly = key === 'pro' || key === 'team';

              // Same plan but different period is also a valid change
              const isPeriodChange = isCurrentPlan && !isCurrentPlanAndPeriod && isEligibleYearly;

              return (
                <div
                  key={key}
                  className={cn(
                    "relative border rounded-lg p-6 transition-all h-full flex flex-col",
                    isCurrentPlan ? "border-primary/50 bg-primary/5" : "border-border hover:border-border/80"
                  )}
                >
                  {isCurrentPlanAndPeriod && (
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
                        <span className="text-2xl font-semibold">
                          {billingPeriod === 'yearly' && isEligibleYearly
                            ? (key === 'pro' ? '$16' : '$239')
                            : `$${plan.price}`}
                        </span>
                        <span className="text-sm text-muted-foreground">
                          {billingPeriod === 'yearly' && isEligibleYearly ? (
                            <>
                              /month<br />
                              (billed yearly)
                            </>
                          ) : '/month'}
                        </span>
                      </div>
                    ) : (
                      <div className="flex items-center gap-2">
                        <span className="text-lg font-semibold">{plan.price}</span>
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

                  {isCurrentPlanAndPeriod ? (
                    <Button variant="outline" disabled className="w-full h-9 text-xs border-border mt-auto">
                      Current Plan
                    </Button>
                  ) : isPeriodChange ? (
                    <Button
                      onClick={() => handleUpgrade(key as 'developer' | 'pro' | 'team')}
                      disabled={isCheckoutLoading}
                      variant="outline"
                      className="w-full h-9 text-xs mt-auto border-primary text-primary hover:border-primary/80 hover:bg-primary/10"
                    >
                      {isCheckoutLoading && <RefreshCw className="w-3 h-3 mr-1 animate-spin" />}
                      {billingPeriod === 'yearly' ? 'Switch to Yearly' : 'Switch to Monthly'}
                    </Button>
                  ) : isEnterprise ? (
                    <Button
                      onClick={() => window.open('https://cal.com/lennert-airweave/airweave-demo', '_blank')}
                      variant="outline"
                      className="w-full h-9 text-xs border-border mt-auto hover:border-primary/80 hover:bg-primary/10 hover:text-primary"
                    >
                      <MessageSquare className="w-3 h-3 mr-1" />
                      Book a Call
                    </Button>
                  ) : (
                    <Button
                      onClick={() => handleUpgrade(key as 'developer' | 'pro' | 'team')}
                      disabled={isCheckoutLoading}
                      variant="outline"
                      className={cn(
                        "w-full h-9 text-xs mt-auto",
                        isUpgrade ? "border-primary text-primary hover:border-primary/80 hover:bg-primary/10" : "border-border"
                      )}
                    >
                      {isCheckoutLoading && <RefreshCw className="w-3 h-3 mr-1 animate-spin" />}
                      {isUpgrade && <ArrowUpCircle className="w-3 h-3 mr-1" />}
                      {isDowngrade && <ArrowDownCircle className="w-3 h-3 mr-1" />}
                      {isUpgrade ? (billingPeriod === 'yearly' && isEligibleYearly ? 'Upgrade' : 'Upgrade') : isDowngrade ? 'Downgrade' : 'Switch'}
                    </Button>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}

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
