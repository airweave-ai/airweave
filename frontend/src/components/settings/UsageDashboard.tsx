import { useState, useEffect } from 'react';
import { cn } from '@/lib/utils';
import { apiClient } from '@/lib/api';
import { Skeleton } from '@/components/ui/skeleton';
import {
  AlertCircle,
  Database,
  Search,
  Link2,
  Users,
} from 'lucide-react';

interface UsageDashboardData {
  current_period: {
    period_id: string;
    period_start: string;
    period_end: string;
    status: string;
    plan: string;
    usage: {
      entities: number;
      queries: number;
      source_connections: number;
      max_entities: number | null;
      max_queries: number | null;
      max_source_connections: number | null;
      team_members: number;
      max_team_members: number | null;
    };
    days_remaining?: number | null;
    is_current: boolean;
  };
}

interface UsageDashboardProps {
  organizationId: string;
}

const metricConfig = [
  {
    key: 'source_connections',
    label: 'Source connections',
    icon: Link2,
  },
  {
    key: 'queries',
    label: 'Queries',
    icon: Search,
  },
  {
    key: 'entities',
    label: 'Entities synced',
    icon: Database,
  },
  {
    key: 'team_members',
    label: 'Team members',
    icon: Users,
  },
];

const UsageMetric: React.FC<{
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  current: number;
  limit: number | null;
}> = ({ icon: Icon, label, current, limit }) => {
  const percentage = limit ? (current / limit) * 100 : 0;
  const isUnlimited = !limit;
  const isAtLimit = limit && current >= limit;
  const isNearLimit = limit && percentage >= 80;

  const hasUsage = current > 0;
  const fillWidthPercentage = (() => {
    if (isAtLimit) return 100;
    if (!hasUsage) return 0; // show empty track with visible border when no usage
    if (isUnlimited) return 2; // minimal indicator when unlimited plan and some usage
    return Math.max(2, Math.min(100, percentage));
  })();

  // Format numbers compactly
  const formatNumber = (num: number) => {
    if (num >= 1000000) return `${Math.floor(num / 1000000)}M`;
    if (num >= 1000) return `${Math.floor(num / 1000)}k`;
    return num.toString();
  };

  return (
    <div className="py-1.5">
      <div className="flex items-center gap-3">
        <Icon className="w-4 h-4 text-muted-foreground" />
        <span className="text-sm font-medium whitespace-nowrap w-48 shrink-0">{label}</span>
        <div className="h-4 w-full flex-1 max-w-[560px] rounded bg-muted overflow-hidden border-2 border-border">
          <div
            className={cn(
              "h-full rounded",
              isAtLimit ? "bg-red-500" : "bg-blue-500"
            )}
            style={{ width: `${fillWidthPercentage}%` }}
          />
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <span className={cn(
            "text-sm font-medium",
            isAtLimit && "text-red-600",
            isNearLimit && !isAtLimit && "text-amber-600"
          )}>
            {current.toLocaleString()}
          </span>
          {!isUnlimited && (
            <span className="text-sm text-muted-foreground">/ {formatNumber(limit)}</span>
          )}
          {isUnlimited && (
            <span className="text-sm text-muted-foreground">Unlimited</span>
          )}
        </div>
      </div>
    </div>
  );
};

export const UsageDashboard: React.FC<UsageDashboardProps> = ({
  organizationId,
}) => {
  const [dashboardData, setDashboardData] = useState<UsageDashboardData | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchDashboard = async () => {
    try {
      setIsLoading(true);
      setError(null);

      const response = await apiClient.get('/usage/dashboard');

      if (!response.ok) {
        throw new Error('Failed to fetch usage data');
      }

      const data = await response.json();
      setDashboardData(data);
    } catch (err) {
      console.error('Error fetching usage dashboard:', err);
      setError('Failed to load usage data');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchDashboard();
  }, [organizationId]);

  if (isLoading) {
    return (
      <div className="border border-border/50 rounded-lg p-4">
        <Skeleton className="h-4 w-24 mb-4" />
        <div className="space-y-3">
          {[...Array(5)].map((_, i) => (
            <Skeleton key={i} className="h-6 w-full" />
          ))}
        </div>
      </div>
    );
  }

  if (error || !dashboardData) {
    return (
      <div className="rounded-lg border border-red-200 dark:border-red-900 bg-red-50 dark:bg-red-950/20 p-4">
        <div className="flex items-center gap-2">
          <AlertCircle className="h-4 w-4 text-red-600 dark:text-red-400" />
          <p className="text-sm text-red-800 dark:text-red-200">
            {error || 'Unable to load usage data'}
          </p>
        </div>
      </div>
    );
  }

  const { current_period } = dashboardData;

  return (
    <div className="border border-border/50 rounded-lg p-4">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-medium">Current Usage</h3>

      </div>

      <div className="space-y-1">
        {metricConfig.map((metric) => {
          const currentValue = current_period.usage[metric.key as keyof typeof current_period.usage] as number;
          const limitValue = current_period.usage[`max_${metric.key}` as keyof typeof current_period.usage] as number | null;

          return (
            <UsageMetric
              key={metric.key}
              icon={metric.icon}
              label={metric.label}
              current={currentValue}
              limit={limitValue}
            />
          );
        })}
      </div>
    </div>
  );
};
