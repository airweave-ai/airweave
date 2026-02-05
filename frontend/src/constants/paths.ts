export const protectedPaths = {
    dashboard: "/",
    collections: "/collections",
    collectionDetail: "/collections/:readable_id",
    collectionNew: "/collections/:readable_id/new",
    apiKeys: "/api-keys",
    authProviders: "/auth-providers",
    authCallback: "/auth/callback/:short_name",
    webhooks: "/webhooks",
}

export const publicPaths = {
    login: "/login",
    callback: "/callback",
    semanticMcp: "/semantic-mcp",
    onboarding: "/onboarding",
    billingSuccess: "/billing/success",
    billingCancel: "/billing/cancel",
}
