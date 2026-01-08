/**
 * Centralized query key factory for TanStack Query.
 *
 * All org-scoped queries include the orgId as the first element,
 * ensuring cache isolation when switching between organizations.
 */

export const queryKeys = {
  organizations: {
    all: ["organizations"] as const,
    members: (orgId: string) => [orgId, "organizations", "members"] as const,
    invitations: (orgId: string) =>
      [orgId, "organizations", "invitations"] as const,
  },

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

  collections: {
    all: (orgId: string) => [orgId, "collections"] as const,
    list: (orgId: string) => [orgId, "collections", "list"] as const,
    detail: (orgId: string, readableId: string) =>
      [orgId, "collections", "detail", readableId] as const,
    count: (orgId: string) => [orgId, "collections", "count"] as const,
  },

  sources: {
    all: (orgId: string) => [orgId, "sources"] as const,
    list: (orgId: string) => [orgId, "sources", "list"] as const,
    detail: (orgId: string, shortName: string) =>
      [orgId, "sources", "detail", shortName] as const,
  },

  sourceConnections: {
    all: (orgId: string, collectionId?: string) =>
      collectionId
        ? ([orgId, "source-connections", collectionId] as const)
        : ([orgId, "source-connections"] as const),
    list: (orgId: string, collectionId?: string) =>
      collectionId
        ? ([orgId, "source-connections", collectionId, "list"] as const)
        : ([orgId, "source-connections", "list"] as const),
    detail: (orgId: string, id: string) =>
      [orgId, "source-connections", "detail", id] as const,
  },
};
