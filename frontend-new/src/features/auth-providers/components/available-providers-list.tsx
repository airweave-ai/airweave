import { Link } from '@tanstack/react-router';
import { IconArrowRight } from '@tabler/icons-react';
import { ProvidersListEmptyState } from './providers-list-empty-state';
import type { AuthProviderMetadata } from '@/shared/api';
import { AuthProviderIcon } from '@/shared/components/auth-provider-icon';
import { ErrorState } from '@/shared/components/error-state';
import { Button } from '@/shared/ui/button';
import { Skeleton } from '@/shared/ui/skeleton';

type AvailableProvidersListProps = {
  providers?: Array<AuthProviderMetadata>;
  error?: unknown;
  onRetry?: () => void;
};

export function AvailableProvidersList({
  providers,
  error,
  onRetry,
}: AvailableProvidersListProps) {
  if (error) {
    return (
      <ErrorState
        description="There was a problem loading available auth providers for this organization."
        onRetry={onRetry}
        retryLabel="Reload available providers"
        title="We couldn't load available providers"
      />
    );
  }

  if (!providers) {
    return (
      <div className="space-y-2">
        <Skeleton className="h-14 rounded-sm bg-muted/60" />
        <Skeleton className="h-14 rounded-sm bg-muted/40" />
        <Skeleton className="h-14 rounded-sm bg-muted/20" />
      </div>
    );
  }

  if (providers.length === 0) {
    return (
      <ProvidersListEmptyState message="Available providers will appear here." />
    );
  }

  return (
    <div className="space-y-2">
      {providers.map((provider) => (
        <AvailableProviderRow key={provider.short_name} provider={provider} />
      ))}
    </div>
  );
}

function AvailableProviderRow({
  provider,
}: {
  provider: AuthProviderMetadata;
}) {
  return (
    <div className="flex min-h-14 items-center justify-between gap-3 rounded-sm border bg-foreground/5 px-3 py-2">
      <div className="flex min-w-0 items-center gap-2">
        <AuthProviderIcon
          name={provider.name}
          shortName={provider.short_name}
        />
        <p className="truncate text-sm font-medium text-foreground">
          {provider.name}
        </p>
      </div>

      <Button asChild className="shrink-0" variant="outline">
        <Link
          params={{ shortName: provider.short_name }}
          to="/auth-providers/$shortName/connect"
        >
          Connect
          <IconArrowRight className="size-4" />
        </Link>
      </Button>
    </div>
  );
}
