import React from 'react';
import { AlertCircle, CreditCard, ArrowRight } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useTheme } from '@/lib/theme-provider';
import { DESIGN_SYSTEM } from '@/lib/design-system';

interface BillingPauseCardProps {
  pauseReason: 'usage_exhausted' | 'payment_required';
}

const REASON_CONFIG: Record<string, {
  icon: React.ElementType;
  title: string;
  description: string;
  ctaLabel: string;
  ctaUrl: string;
}> = {
  usage_exhausted: {
    icon: AlertCircle,
    title: 'Usage Limit Reached',
    description: 'Syncing is paused because your plan\'s usage limit has been reached. It will resume automatically when your billing period resets, or you can upgrade now.',
    ctaLabel: 'Upgrade Plan',
    ctaUrl: '/organization/settings?tab=billing',
  },
  payment_required: {
    icon: CreditCard,
    title: 'Payment Required',
    description: 'Syncing is paused due to a billing issue. Please update your payment method to resume.',
    ctaLabel: 'Update Billing',
    ctaUrl: '/organization/settings?tab=billing',
  },
};

export const BillingPauseCard: React.FC<BillingPauseCardProps> = ({ pauseReason }) => {
  const { resolvedTheme } = useTheme();
  const isDark = resolvedTheme === 'dark';
  const config = REASON_CONFIG[pauseReason];

  if (!config) return null;

  const Icon = config.icon;

  return (
    <div className={cn(
      'rounded-xl border p-5 space-y-4',
      isDark ? 'border-amber-800/30 bg-amber-900/10' : 'border-amber-200 bg-amber-50',
    )}>
      <div className="flex items-start gap-3">
        <div className={cn(
          'flex-shrink-0 w-9 h-9 rounded-lg flex items-center justify-center',
          isDark ? 'bg-gray-800/60' : 'bg-white shadow-sm',
        )}>
          <Icon className={cn('h-5 w-5', isDark ? 'text-amber-400' : 'text-amber-600')} />
        </div>
        <div className="flex-1 min-w-0">
          <h3 className={cn(
            DESIGN_SYSTEM.typography.sizes.header,
            DESIGN_SYSTEM.typography.weights.semibold,
            'mb-1',
            isDark ? 'text-gray-100' : 'text-gray-900',
          )}>
            {config.title}
          </h3>
          <p className={cn(
            DESIGN_SYSTEM.typography.sizes.body,
            isDark ? 'text-gray-400' : 'text-gray-600',
          )}>
            {config.description}
          </p>
        </div>
      </div>
      <div className="flex items-center gap-2 pt-1">
        <a
          href={config.ctaUrl}
          className={cn(
            'inline-flex items-center gap-2 px-4 py-2 rounded-lg shadow-sm',
            DESIGN_SYSTEM.typography.sizes.body,
            DESIGN_SYSTEM.typography.weights.medium,
            'transition-all duration-200',
            'bg-primary text-primary-foreground hover:bg-primary/90',
          )}
        >
          {config.ctaLabel}
          <ArrowRight className="h-3.5 w-3.5" />
        </a>
      </div>
    </div>
  );
};
