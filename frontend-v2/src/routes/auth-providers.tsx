import { createFileRoute } from "@tanstack/react-router";
import { Plus, ShieldCheck } from "lucide-react";

import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { usePageHeader } from "@/components/ui/page-header";
import { useRightSidebarContent } from "@/components/ui/right-sidebar";
import { DocsContent } from "@/hooks/use-docs-content";

export const Route = createFileRoute("/auth-providers")({
  component: AuthProvidersPage,
});

function AuthProvidersDocs() {
  return <DocsContent docPath="auth-providers/overview.mdx" />;
}

function AuthProvidersCode() {
  return (
    <div className="space-y-4">
      <h3 className="font-semibold text-base">Auth Provider Setup</h3>
      <p className="text-sm text-muted-foreground">
        Configure authentication for your source connections:
      </p>
      <pre className="bg-muted p-3 rounded-lg text-xs overflow-auto">
        <code>{`// Using OAuth flow
const connection = await client.sourceConnections.create({
  name: 'My Notion Connection',
  short_name: 'notion',
  collection_id: collection.readable_id,
  authentication: {
    oauth: {
      provider: 'composio',
      // OAuth flow handled automatically
    }
  }
});

// Using direct credentials
const connection = await client.sourceConnections.create({
  name: 'My Stripe Connection',
  short_name: 'stripe',
  collection_id: collection.readable_id,
  authentication: {
    credentials: {
      api_key: 'sk_test_...'
    }
  }
});`}</code>
      </pre>
    </div>
  );
}

function AuthProvidersHelp() {
  return (
    <div className="space-y-4">
      <h3 className="font-semibold text-base">About Auth Providers</h3>
      <p className="text-sm text-muted-foreground">
        Auth providers help manage OAuth connections to external services.
      </p>
      <div className="space-y-3">
        <div className="p-3 bg-muted rounded-lg">
          <h4 className="font-medium text-sm">Supported Providers</h4>
          <ul className="text-xs text-muted-foreground mt-1 space-y-1">
            <li>Composio - Multi-app OAuth</li>
            <li>Pipedream - Workflow automation</li>
            <li>Direct OAuth - Native flows</li>
          </ul>
        </div>
      </div>
    </div>
  );
}

function AuthProvidersPage() {
  usePageHeader({
    title: "Auth Providers",
    description: "Manage OAuth and authentication providers",
    actions: (
      <Button>
        <Plus className="size-4 mr-2" />
        Add Provider
      </Button>
    ),
  });

  useRightSidebarContent({
    docs: <AuthProvidersDocs />,
    code: <AuthProvidersCode />,
    help: <AuthProvidersHelp />,
  });

  return (
    <div className="p-6">
      <EmptyState
        icon={<ShieldCheck />}
        title="Configure auth providers"
        description="Auth providers enable secure OAuth connections to external services."
      >
        <Button variant="outline">
          <Plus className="size-4 mr-2" />
          Add Provider
        </Button>
      </EmptyState>
    </div>
  );
}
