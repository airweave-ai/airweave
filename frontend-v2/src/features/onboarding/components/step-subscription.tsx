import { Check } from "lucide-react";

import { cn } from "@/lib/utils";

import { SUBSCRIPTION_PLANS } from "../utils/constants";

interface StepSubscriptionProps {
  value: string;
  onChange: (value: string) => void;
  billingPeriod: "monthly" | "yearly";
  onBillingPeriodChange: (period: "monthly" | "yearly") => void;
  authEnabled?: boolean;
}

export function StepSubscription({
  value,
  onChange,
  billingPeriod,
  onBillingPeriodChange,
  authEnabled = true,
}: StepSubscriptionProps) {
  return (
    <div className="space-y-8">
      <div className="space-y-2">
        <h2 className="text-2xl font-normal">Choose your plan</h2>
        <p className="text-muted-foreground">
          You can always upgrade or downgrade later
        </p>
        {!authEnabled && (
          <div className="bg-amber-500/10 border-amber-500/20 mt-2 rounded-lg border p-3">
            <p className="text-xs text-amber-600 dark:text-amber-400">
              <strong>Local Development Mode:</strong> Billing is disabled.
              You'll go straight to the dashboard after setup.
            </p>
          </div>
        )}
      </div>

      {/* Monthly/Yearly Toggle */}
      {authEnabled && (
        <div className="relative flex justify-center">
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
                onClick={() => onBillingPeriodChange("monthly")}
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
                onClick={() => onBillingPeriodChange("yearly")}
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
            {/* Yearly discount message */}
            <div
              className={cn(
                "absolute top-full left-1/2 mt-1 -translate-x-1/2 transition-opacity duration-200",
                billingPeriod === "yearly"
                  ? "opacity-100"
                  : "pointer-events-none opacity-0"
              )}
            >
              <p className="text-muted-foreground text-center text-xs whitespace-nowrap">
                After 12 months, your plan will renew at monthly rates.
              </p>
            </div>
          </div>
        </div>
      )}

      <div className="grid gap-4">
        {SUBSCRIPTION_PLANS.map((plan) => (
          <button
            key={plan.value}
            type="button"
            onClick={() => {
              if (plan.value === "enterprise") {
                window.open(
                  "https://cal.com/lennert-airweave/airweave-demo",
                  "_blank",
                  "noopener,noreferrer"
                );
                return;
              }
              onChange(plan.value);
            }}
            className={cn(
              "relative rounded-lg border p-6 text-left transition-all",
              "hover:border-primary/50",
              value === plan.value
                ? "border-primary bg-primary/5"
                : "border-border"
            )}
          >
            <div className="mb-4 flex items-start justify-between">
              <div>
                <div className="mb-1 flex items-center gap-2">
                  <h3 className="text-lg font-medium">{plan.label}</h3>
                </div>
                <p className="text-muted-foreground text-sm">
                  {plan.description}
                </p>
              </div>
              <div className="text-right">
                <div className="text-2xl font-light">
                  {!authEnabled
                    ? "Free"
                    : billingPeriod === "yearly" && plan.yearlyPrice
                      ? plan.yearlyPrice
                      : plan.price}
                </div>
                {plan.period && !authEnabled && (
                  <div className="text-muted-foreground text-xs">local dev</div>
                )}
                {plan.period && authEnabled && (
                  <div className="text-muted-foreground text-xs">
                    {billingPeriod === "yearly" && plan.yearlyPrice
                      ? "per month (billed yearly)"
                      : plan.period}
                  </div>
                )}
                {plan.recommended && (
                  <div className="text-primary mt-1 text-xs">Recommended</div>
                )}
              </div>
            </div>

            <div className="text-muted-foreground grid grid-cols-2 gap-x-4 gap-y-2 text-xs">
              {plan.features.map((feature, index) => (
                <div key={index} className="flex items-center">
                  <Check className="text-primary mr-2 h-3 w-3 flex-shrink-0" />
                  {feature}
                </div>
              ))}
            </div>
          </button>
        ))}
      </div>
    </div>
  );
}

