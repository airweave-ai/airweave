import { useQuery } from '@tanstack/react-query';
import { IconBulb } from '@tabler/icons-react';
import { ProvidersSection } from './components';
import { PageHeader, PageLayout } from '@/app/pages/components';
import {
  AvailableProvidersList,
  ConnectedProvidersList,
  useListAuthProviderConnectionsQueryOptions,
  useListAuthProvidersQueryOptions,
} from '@/features/auth-providers';
import { Button } from '@/shared/ui/button';
import { Separator } from '@/shared/ui/separator';

export function AuthProvidersPage() {
  const authProvidersQueryOptions = useListAuthProvidersQueryOptions();
  const authProviderConnectionsQueryOptions =
    useListAuthProviderConnectionsQueryOptions();
  const {
    data: authProviderConnections,
    error: authProviderConnectionsError,
    refetch: refetchAuthProviderConnections,
  } = useQuery(authProviderConnectionsQueryOptions);
  const {
    data: authProviders,
    error: authProvidersError,
    refetch: refetchAuthProviders,
  } = useQuery(authProvidersQueryOptions);

  return (
    <PageLayout className="gap-13">
      <PageHeader
        title="Auth Providers"
        description="Authenticate data sources through third-party applications."
        actions={
          <Button asChild data-icon="inline-start" variant="secondary">
            <a
              href="https://docs.airweave.ai/auth-providers"
              rel="noreferrer"
              target="_blank"
            >
              <IconBulb className="size-4" />
              Learn More
            </a>
          </Button>
        }
      />

      <div className="flex flex-col gap-8">
        <ProvidersSection
          count={authProviderConnections?.length ?? 0}
          title="Connected Providers"
        >
          <ConnectedProvidersList
            connections={authProviderConnections}
            error={authProviderConnectionsError}
            onRetry={() => {
              void refetchAuthProviderConnections();
            }}
          />
        </ProvidersSection>

        <Separator className="w-full" />

        <ProvidersSection
          count={authProviders?.length ?? 0}
          title="Available Providers"
        >
          <AvailableProvidersList
            error={authProvidersError}
            onRetry={() => {
              void refetchAuthProviders();
            }}
            providers={authProviders}
          />
        </ProvidersSection>
      </div>
    </PageLayout>
  );
}
