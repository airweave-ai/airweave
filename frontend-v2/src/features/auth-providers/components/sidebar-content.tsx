import { DocsContent } from "@/hooks/use-docs-content";

export function AuthProvidersDocs() {
  return <DocsContent docPath="auth-providers/overview.mdx" />;
}

export function AuthProvidersCode() {
  return (
    <div className="space-y-4">
      <h3 className="font-semibold text-base">Auth Provider Setup</h3>
      <p className="text-sm text-muted-foreground">
        Configure authentication for your source connections:
      </p>
      <pre className="bg-muted p-3 rounded-lg text-xs overflow-auto">
        <code>{`// Using OAuth flow with Composio
const connection = await client.sourceConnections.create({
  name: 'My Notion Connection',
  short_name: 'notion',
  collection_id: collection.readable_id,
  authentication: {
    auth_provider: 'composio',
    // OAuth flow handled automatically
  }
});

// Using OAuth flow with Pipedream
const connection = await client.sourceConnections.create({
  name: 'My Slack Connection',
  short_name: 'slack',
  collection_id: collection.readable_id,
  authentication: {
    auth_provider: 'pipedream',
  }
});`}</code>
      </pre>
    </div>
  );
}

export function AuthProvidersHelp() {
  return (
    <div className="space-y-4">
      <h3 className="font-semibold text-base">About Auth Providers</h3>
      <p className="text-sm text-muted-foreground">
        Auth providers help manage OAuth connections to external services,
        allowing Airweave to securely authenticate with your data sources.
      </p>
      <div className="space-y-3">
        <div className="p-3 bg-muted rounded-lg">
          <h4 className="font-medium text-sm">Supported Providers</h4>
          <ul className="text-xs text-muted-foreground mt-2 space-y-1.5">
            <li className="flex items-start gap-2">
              <span className="font-medium text-foreground">Composio</span>
              <span>- Multi-app OAuth with 100+ integrations</span>
            </li>
            <li className="flex items-start gap-2">
              <span className="font-medium text-foreground">Pipedream</span>
              <span>- Workflow automation with OAuth support</span>
            </li>
            <li className="flex items-start gap-2">
              <span className="font-medium text-foreground text-muted-foreground">
                Klavis
              </span>
              <span className="text-muted-foreground/70">
                - MCP-native authentication (coming soon)
              </span>
            </li>
          </ul>
        </div>

        <div className="p-3 bg-muted rounded-lg">
          <h4 className="font-medium text-sm">How it works</h4>
          <ol className="text-xs text-muted-foreground mt-2 space-y-1.5 list-decimal list-inside">
            <li>Create an auth provider connection with your API keys</li>
            <li>When creating a source connection, select the auth provider</li>
            <li>
              Users authenticate via OAuth through the provider's secure flow
            </li>
            <li>Tokens are securely stored and automatically refreshed</li>
          </ol>
        </div>

        <div className="p-3 bg-muted rounded-lg">
          <h4 className="font-medium text-sm">Getting Started</h4>
          <div className="text-xs text-muted-foreground mt-2 space-y-2">
            <p>
              <span className="font-medium text-foreground">Composio:</span>{" "}
              Sign up at{" "}
              <a
                href="https://platform.composio.dev"
                target="_blank"
                rel="noopener noreferrer"
                className="text-primary hover:underline"
              >
                platform.composio.dev
              </a>{" "}
              and get your API key from the dashboard.
            </p>
            <p>
              <span className="font-medium text-foreground">Pipedream:</span>{" "}
              Get your Client ID and Secret from{" "}
              <a
                href="https://pipedream.com/settings/api"
                target="_blank"
                rel="noopener noreferrer"
                className="text-primary hover:underline"
              >
                pipedream.com/settings/api
              </a>
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
