import { createFileRoute } from "@tanstack/react-router";
import { Plus, ShieldCheck } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
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
  useRightSidebarContent({
    docs: <AuthProvidersDocs />,
    code: <AuthProvidersCode />,
    help: <AuthProvidersHelp />,
  });

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold">Auth Providers</h1>
          <p className="text-muted-foreground">
            Manage OAuth and authentication providers
          </p>
        </div>
        <Button>
          <Plus className="size-4 mr-2" />
          Add Provider
        </Button>
      </div>

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        <Card className="border-dashed">
          <CardHeader className="text-center">
            <div className="mx-auto w-12 h-12 rounded-full bg-muted flex items-center justify-center mb-2">
              <ShieldCheck className="size-6 text-muted-foreground" />
            </div>
            <CardTitle className="text-lg">Configure auth providers</CardTitle>
            <CardDescription>
              Auth providers enable secure OAuth connections to external
              services.
            </CardDescription>
          </CardHeader>
          <CardContent className="text-center">
            <Button variant="outline">
              <Plus className="size-4 mr-2" />
              Add Provider
            </Button>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
