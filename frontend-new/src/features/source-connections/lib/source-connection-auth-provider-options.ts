import type {
  AuthProviderConnection,
  AuthProviderMetadata,
  ConfigField,
  Source,
} from '@/shared/api';

export type SourceConnectionAuthProviderOption = {
  readableId: string;
  connectionName: string;
  providerName: string;
  providerShortName: string;
  configFields: Array<ConfigField>;
};

export function getSourceConnectionAuthProviderOptions({
  authProviderConnections,
  authProviders,
  source,
}: {
  authProviderConnections: Array<AuthProviderConnection>;
  authProviders: Array<AuthProviderMetadata>;
  source: Source;
}): Array<SourceConnectionAuthProviderOption> {
  const supportedProviderShortNames = new Set(
    source.supported_auth_providers ?? [],
  );

  if (supportedProviderShortNames.size === 0) {
    return [];
  }

  return authProviderConnections
    .filter((connection) =>
      supportedProviderShortNames.has(connection.short_name),
    )
    .flatMap((connection) => {
      const provider = authProviders.find(
        (authProvider) => authProvider.short_name === connection.short_name,
      );

      if (!provider) {
        return [];
      }

      return [
        {
          readableId: connection.readable_id,
          connectionName: connection.name,
          providerName: provider.name,
          providerShortName: connection.short_name,
          configFields: provider.config_fields?.fields ?? [],
        },
      ];
    });
}
