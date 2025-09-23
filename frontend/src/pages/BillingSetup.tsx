import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useOrganizationStore } from '@/lib/stores/organizations';
import { apiClient } from '@/lib/api';
import { toast } from 'sonner';
import { Loader2, CreditCard, AlertCircle, Check, ChevronRight } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useTheme } from '@/lib/theme-provider';

export default function BillingSetup() {
  const navigate = useNavigate();
  const { resolvedTheme } = useTheme();
  const { currentOrganization, billingInfo, fetchBillingInfo } = useOrganizationStore();
  const [isLoading, setIsLoading] = useState(false);
  const [isCheckingStatus, setIsCheckingStatus] = useState(true);
  const [isPolling, setIsPolling] = useState(false);

  const isDark = resolvedTheme === 'dark';

  useEffect(() => {
    // Check current billing status
    checkBillingStatus();
  }, []);

  const checkBillingStatus = async () => {
    setIsCheckingStatus(true);
    try {
      const info = await fetchBillingInfo();

      // If subscription is active (paid or developer), go to success page
      if (info && info.has_active_subscription && info.status === 'active') {
        toast.success('Subscription activated');
        navigate('/billing/success');
        return;
      }

      // If not active yet, start a short poll to wait for Stripe webhooks
      if (info && !info.has_active_subscription && !isPolling) {
        setIsPolling(true);
        const startedAt = Date.now();
        const poll = async () => {
          const refreshed = await fetchBillingInfo();
          if (refreshed && refreshed.has_active_subscription && refreshed.status === 'active') {
            toast.success('Subscription activated');
            setIsPolling(false);
            navigate('/billing/success');
            return;
          }
          if (Date.now() - startedAt < 30000) {
            setTimeout(poll, 2000);
          } else {
            setIsPolling(false);
          }
        };
        setTimeout(poll, 1500);
      }
    } catch (error) {
      console.error('Failed to check billing status:', error);
    } finally {
      setIsCheckingStatus(false);
    }
  };

  const handleSetupPayment = async () => {
    if (!currentOrganization) {
      toast.error('No organization selected');
      return;
    }

    setIsLoading(true);
    try {
      // If current plan is developer, do not go to checkout. Require webhook activation.
      if (billingInfo?.plan === 'developer') {
        toast.error('Stripe listener error: awaiting activation for Developer plan. Please ensure webhooks are configured.');
        setIsLoading(false);
        return;
      }

      const response = await apiClient.post('/billing/checkout-session', {
        plan: billingInfo?.plan || 'pro', // Use their selected plan or default to pro
        success_url: `${window.location.origin}/billing/success?session_id={CHECKOUT_SESSION_ID}`,
        cancel_url: `${window.location.origin}/billing/setup`
      });

      if (!response.ok) {
        throw new Error('Failed to create checkout session');
      }

      const data = await response.json();

      // Redirect to Stripe Checkout
      window.location.href = data.checkout_url;
    } catch (error) {
      console.error('Failed to setup payment:', error);
      toast.error('Failed to setup payment. Please try again.');
      setIsLoading(false);
    }
  };

  const handleManageSubscription = () => {
    navigate('/organization/settings?tab=billing');
  };

  if (isCheckingStatus) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <Loader2 className="h-6 w-6 animate-spin text-primary/60" />
      </div>
    );
  }

  const hasActiveSubscription = billingInfo?.has_active_subscription;
  const needsPaymentMethod = billingInfo?.requires_payment_method && !billingInfo?.payment_method_added;
  const isInitialSetup = !hasActiveSubscription;
  const selectedPlan = billingInfo?.plan || 'pro';

  return (
    <div className="min-h-screen bg-background flex items-center justify-center p-4">
      <div className="w-full max-w-xl">
        {/* Header with logo */}
        <div className="mb-12 text-center">
          <img
            src={isDark ? "/logo-airweave-darkbg.svg" : "/logo-airweave-lightbg.svg"}
            alt="Airweave"
            className="h-8 w-auto mx-auto mb-2"
            style={{ maxWidth: '180px' }}
          />
          <p className="text-xs text-muted-foreground">
            Build smarter agents
          </p>
        </div>

        {/* Main content */}
        <div className="space-y-8">
          <div className="text-center space-y-2">
            <h1 className="text-2xl font-normal">
              {isInitialSetup ? 'Complete Your Setup' : 'Update Payment Method'}
            </h1>
            <p className="text-muted-foreground">
              {isInitialSetup
                ? 'Add a payment method to activate your subscription'
                : 'Update your payment method to continue using Airweave'}
            </p>
          </div>

          {/* Status Alert */}
          {billingInfo?.status === 'past_due' && (
            <div className="bg-amber-50 dark:bg-amber-950/20 border border-amber-200 dark:border-amber-900/50 rounded-lg p-4">
              <div className="flex gap-3">
                <AlertCircle className="h-5 w-5 text-amber-600 dark:text-amber-500 flex-shrink-0 mt-0.5" />
                <div className="text-sm text-amber-800 dark:text-amber-200">
                  <p className="font-medium mb-1">Payment failed</p>
                  <p>Your last payment failed. Please update your payment method to continue.</p>
                </div>
              </div>
            </div>
          )}

          {/* Plan Details */}
          <div className="border border-border/50 rounded-lg p-6 space-y-4">
            <div className="space-y-1">
              <h3 className="text-lg font-normal">
                {selectedPlan === 'team' ? 'Team' : 'Pro'} Plan
              </h3>
              <p className="text-sm text-muted-foreground">
                {selectedPlan === 'team'
                  ? 'For fast-moving teams that need scale and control'
                  : 'Take your agent to the next level'}
              </p>
            </div>

            <div className="space-y-3">
              {selectedPlan === 'team' ? (
                <>
                  <div className="flex items-center gap-3">
                    <Check className="h-4 w-4 text-primary/70 flex-shrink-0" />
                    <span className="text-sm">$299 per month</span>
                  </div>
                  <div className="flex items-center gap-3">
                    <Check className="h-4 w-4 text-primary/70 flex-shrink-0" />
                    <span className="text-sm">1000 sources</span>
                  </div>
                  <div className="flex items-center gap-3">
                    <Check className="h-4 w-4 text-primary/70 flex-shrink-0" />
                    <span className="text-sm">10K queries per month</span>
                  </div>
                  <div className="flex items-center gap-3">
                    <Check className="h-4 w-4 text-primary/70 flex-shrink-0" />
                    <span className="text-sm">1M entities synced per month</span>
                  </div>
                  <div className="flex items-center gap-3">
                    <Check className="h-4 w-4 text-primary/70 flex-shrink-0" />
                    <span className="text-sm">Up to 10 team members</span>
                  </div>
                  <div className="flex items-center gap-3">
                    <Check className="h-4 w-4 text-primary/70 flex-shrink-0" />
                    <span className="text-sm">Dedicated Slack support</span>
                  </div>
                  <div className="flex items-center gap-3">
                    <Check className="h-4 w-4 text-primary/70 flex-shrink-0" />
                    <span className="text-sm">Dedicated onboarding</span>
                  </div>
                </>
              ) : (
                <>
                  <div className="flex items-center gap-3">
                    <Check className="h-4 w-4 text-primary/70 flex-shrink-0" />
                    <span className="text-sm">$20 per month</span>
                  </div>
                  <div className="flex items-center gap-3">
                    <Check className="h-4 w-4 text-primary/70 flex-shrink-0" />
                    <span className="text-sm">50 sources</span>
                  </div>
                  <div className="flex items-center gap-3">
                    <Check className="h-4 w-4 text-primary/70 flex-shrink-0" />
                    <span className="text-sm">2K queries per month</span>
                  </div>
                  <div className="flex items-center gap-3">
                    <Check className="h-4 w-4 text-primary/70 flex-shrink-0" />
                    <span className="text-sm">100K entities synced per month</span>
                  </div>
                  <div className="flex items-center gap-3">
                    <Check className="h-4 w-4 text-primary/70 flex-shrink-0" />
                    <span className="text-sm">Up to 2 team members</span>
                  </div>
                  <div className="flex items-center gap-3">
                    <Check className="h-4 w-4 text-primary/70 flex-shrink-0" />
                    <span className="text-sm">Email support</span>
                  </div>
                </>
              )}
            </div>
          </div>

          {/* Action Button */}
          <div className="pt-4">
            {hasActiveSubscription && billingInfo?.status === 'past_due' ? (
              <button
                onClick={handleManageSubscription}
                disabled={isLoading}
                className={cn(
                  "w-full flex items-center justify-center space-x-2 px-6 py-3 rounded-lg transition-all",
                  "bg-primary text-primary-foreground hover:bg-primary/90",
                  isLoading && "opacity-50 cursor-not-allowed"
                )}
              >
                <span>Update Payment Method</span>
                <ChevronRight className="w-4 h-4" />
              </button>
            ) : (
              <div className="w-full flex justify-center">
                <button
                  onClick={handleSetupPayment}
                  disabled={isLoading}
                  className={cn(
                    "flex items-center justify-center space-x-2 px-6 py-3 rounded-lg transition-all",
                    "bg-primary text-primary-foreground hover:bg-primary/90",
                    isLoading && "opacity-50 cursor-not-allowed"
                  )}
                >
                  {isLoading ? (
                    <>
                      <span>Setting up payment</span>
                      <Loader2 className="w-4 h-4 animate-spin" />
                    </>
                  ) : (
                    <>
                      <span>{isInitialSetup ? 'Complete Setup' : 'Update Payment Method'}</span>
                      <ChevronRight className="w-4 h-4" />
                    </>
                  )}
                </button>
              </div>
            )}
          </div>

          {/* Polling state */}
          {isPolling && (
            <p className="text-center text-xs text-muted-foreground mt-2">
              Waiting for Stripe confirmation... this may take a few seconds.
            </p>
          )}

          {/* Additional Info */}
          <p className="text-center text-xs text-muted-foreground">
            {isInitialSetup ? 'Your subscription will start immediately.' : 'Update your payment method to continue your subscription.'}
          </p>
        </div>
      </div>
    </div>
  );
}
