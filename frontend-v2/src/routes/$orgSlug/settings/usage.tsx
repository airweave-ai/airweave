import { useQuery } from "@tanstack/react-query";
import { createFileRoute } from "@tanstack/react-router";
import { AlertCircle, Database, Link2, Search, Users } from "lucide-react";

import { SettingsLayout } from "@/components/settings-layout";
import { Skeleton } from "@/components/ui/skeleton";
import { usePageHeader } from "@/components/ui/page-header";
import { fetchUsageDashboard, type UsageData } from "@/lib/api";
import { useAuth0 } from "@/lib/auth-provider";
import { useOrg } from "@/lib/org-context";
import { queryKeys } from "@/lib/query-keys";
import { cn } from "@/lib/utils";

export const Route = createFileRoute("/$orgSlug/settings/usage")({
  component: UsageSettingsPage,
});

type MetricKey = "source_connections" | "queries" | "entities" | "team_members";

const metricConfig: {
  key: MetricKey;
  maxKey: keyof UsageData;
  label: string;
  icon: typeof Link2;
}[] = [
  {
    key: "source_connections",
    maxKey: "max_source_connections",
    label: "Source connections",
    icon: Link2,
  },
  {
    key: "queries",
    maxKey: "max_queries",
    label: "Queries",
    icon: Search,
  },
  {
    key: "entities",
    maxKey: "max_entities",
    label: "Entities synced",
    icon: Database,
  },
  {
    key: "team_members",
    maxKey: "max_team_members",
    label: "Team members",
    icon: Users,
  },
];

interface UsageMetricProps {
  icon: typeof Link2;
  label: string;
  current: number;
  limit: number | null;
}

function UsageMetric({ icon: Icon, label, current, limit }: UsageMetricProps) {
  const percentage = limit ? (current / limit) * 100 : 0;
  const isUnlimited = !limit;
  const isAtLimit = limit && current >= limit;
  const isNearLimit = limit && percentage >= 80;

  const hasUsage = current > 0;
  const fillWidthPercentage = (() => {
    if (isAtLimit) return 100;
    if (!hasUsage) return 0;
    if (isUnlimited) return 2;
    return Math.max(2, Math.min(100, percentage));
  })();

  const formatNumber = (num: number) => {
    if (num >= 1000000) return `${Math.floor(num / 1000000)}M`;
    if (num >= 1000) return `${Math.floor(num / 1000)}k`;
    return num.toString();
  };

  return (
    <div className="py-2">
      <div className="flex items-center gap-3">
        <Icon className="text-muted-foreground size-4 shrink-0" />
        <span className="w-40 shrink-0 text-sm font-medium">{label}</span>
        <div className="border-border bg-muted h-4 max-w-[400px] flex-1 overflow-hidden rounded border-2">
          <div
            className={cn(
              "h-full rounded-sm transition-all",
              isAtLimit ? "bg-destructive" : "bg-primary"
            )}
            style={{ width: `${fillWidthPercentage}%` }}
          />
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <span
            className={cn(
              "text-sm font-medium tabular-nums",
              isAtLimit && "text-destructive",
              isNearLimit && !isAtLimit && "text-amber-600 dark:text-amber-400"
            )}
          >
            {current.toLocaleString()}
          </span>
          {!isUnlimited && (
            <span className="text-muted-foreground text-sm">
              / {formatNumber(limit)}
            </span>
          )}
          {isUnlimited && (
            <span className="text-muted-foreground text-sm">Unlimited</span>
          )}
        </div>
      </div>
    </div>
  );
}

function UsageSettingsPage() {
  const { getAccessTokenSilently } = useAuth0();
  const { organization } = useOrg();

  usePageHeader({
    title: "Settings",
    description: "Manage organization settings, preferences, and configuration",
  });

  const {
    data: usageData,
    isLoading,
    error,
  } = useQuery({
    queryKey: queryKeys.usage.dashboard(organization?.id ?? ""),
    queryFn: async () => {
      const token = await getAccessTokenSilently();
      return fetchUsageDashboard(token);
    },
    enabled: !!organization?.id,
  });

  if (!organization) {
    return null;
  }

  if (isLoading) {
    return (
      <SettingsLayout organization={organization}>
        <div className="space-y-6">
          <div>
            <h3 className="text-sm font-medium">Current Usage</h3>
            <p className="text-muted-foreground mt-0.5 text-xs">
              Track your organization's resource usage
            </p>
          </div>
          <div className="space-y-4">
            {[...Array(4)].map((_, i) => (
              <div key={i} className="flex items-center gap-3">
                <Skeleton className="size-4" />
                <Skeleton className="h-4 w-40" />
                <Skeleton className="h-4 max-w-[400px] flex-1" />
                <Skeleton className="h-4 w-24" />
              </div>
            ))}
          </div>
        </div>
      </SettingsLayout>
    );
  }

  if (error || !usageData) {
    return (
      <SettingsLayout organization={organization}>
        <div className="border-destructive/20 bg-destructive/5 rounded-lg border p-4">
          <div className="flex items-center gap-2">
            <AlertCircle className="text-destructive size-4" />
            <p className="text-destructive text-sm">
              {error instanceof Error
                ? error.message
                : "Unable to load usage data"}
            </p>
          </div>
        </div>
      </SettingsLayout>
    );
  }

  const { current_period } = usageData;

  return (
    <SettingsLayout organization={organization}>
      <div className="space-y-8">
        {/* Usage Overview */}
        <section className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-sm font-medium">Current Usage</h3>
              <p className="text-muted-foreground mt-0.5 text-xs">
                Track your organization's resource usage
              </p>
            </div>
            {current_period.plan && (
              <div className="text-muted-foreground text-xs">
                Plan:{" "}
                <span className="text-foreground font-medium capitalize">
                  {current_period.plan}
                </span>
              </div>
            )}
          </div>

          <div className="border-border rounded-lg border p-4">
            <div className="space-y-1">
              {metricConfig.map((metric) => {
                const currentValue = current_period.usage[metric.key] as number;
                const limitValue = current_period.usage[metric.maxKey] as
                  | number
                  | null;

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
        </section>

        {/* Billing Period Info */}
        {current_period.period_start && (
          <section className="border-border border-t pt-6">
            <div className="space-y-3">
              <h3 className="text-sm font-medium">Billing Period</h3>
              <div className="text-muted-foreground grid gap-2 text-xs">
                <div className="flex items-center justify-between">
                  <span>Period start</span>
                  <span className="text-foreground">
                    {new Date(current_period.period_start).toLocaleDateString()}
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <span>Period end</span>
                  <span className="text-foreground">
                    {new Date(current_period.period_end).toLocaleDateString()}
                  </span>
                </div>
                {current_period.days_remaining != null && (
                  <div className="flex items-center justify-between">
                    <span>Days remaining</span>
                    <span className="text-foreground">
                      {current_period.days_remaining}
                    </span>
                  </div>
                )}
              </div>
            </div>
          </section>
        )}
      </div>
    </SettingsLayout>
  );
}
