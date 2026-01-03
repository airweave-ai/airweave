/**
 * Centralized query key factory for TanStack Query.
 *
 * All org-scoped queries include the orgId as the first element,
 * ensuring cache isolation when switching between organizations.
 */

export const queryKeys = {
  // User-level queries (not org-scoped)
  organizations: {
    all: ["organizations"] as const,
  },

  // Org-scoped queries
  apiKeys: {
    all: (orgId: string) => [orgId, "api-keys"] as const,
    list: (orgId: string) => [orgId, "api-keys", "list"] as const,
  },

  authProviders: {
    all: (orgId: string) => [orgId, "auth-providers"] as const,
    list: (orgId: string) => [orgId, "auth-providers", "list"] as const,
    detail: (orgId: string, shortName: string) =>
      [orgId, "auth-providers", "detail", shortName] as const,
    connections: (orgId: string) =>
      [orgId, "auth-provider-connections"] as const,
    connection: (orgId: string, id: string) =>
      [orgId, "auth-provider-connections", id] as const,
  },
};
