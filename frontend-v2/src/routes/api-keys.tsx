import { createFileRoute } from "@tanstack/react-router";
import { Key, Plus } from "lucide-react";

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

export const Route = createFileRoute("/api-keys")({ component: ApiKeysPage });

function ApiKeysDocs() {
  return <DocsContent docPath="quickstart.mdx" />;
}

function ApiKeysCode() {
  return (
    <div className="space-y-4">
      <h3 className="font-semibold text-base">Using API Keys</h3>
      <p className="text-sm text-muted-foreground">
        Authenticate your requests with your API key:
      </p>
      <pre className="bg-muted p-3 rounded-lg text-xs overflow-auto">
        <code>{`import { AirweaveSDK } from '@airweave/sdk';

const client = new AirweaveSDK({
  apiKey: 'YOUR_API_KEY',
  baseUrl: 'https://api.airweave.ai'
});

// Or use directly in headers
fetch('https://api.airweave.ai/collections', {
  headers: {
    'x-api-key': 'YOUR_API_KEY'
  }
});`}</code>
      </pre>
    </div>
  );
}

function ApiKeysHelp() {
  return (
    <div className="space-y-4">
      <h3 className="font-semibold text-base">API Key Security</h3>
      <p className="text-sm text-muted-foreground">
        Keep your API keys secure and never expose them in client-side code.
      </p>
      <div className="space-y-3">
        <div className="p-3 bg-muted rounded-lg">
          <h4 className="font-medium text-sm">Best Practices</h4>
          <ul className="text-xs text-muted-foreground mt-1 space-y-1">
            <li>Store keys in environment variables</li>
            <li>Rotate keys periodically</li>
            <li>Use different keys for dev/prod</li>
          </ul>
        </div>
      </div>
    </div>
  );
}

function ApiKeysPage() {
  useRightSidebarContent({
    docs: <ApiKeysDocs />,
    code: <ApiKeysCode />,
    help: <ApiKeysHelp />,
  });

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold">API Keys</h1>
          <p className="text-muted-foreground">
            Manage your API keys for programmatic access
          </p>
        </div>
        <Button>
          <Plus className="size-4 mr-2" />
          Create API Key
        </Button>
      </div>

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        <Card className="border-dashed">
          <CardHeader className="text-center">
            <div className="mx-auto w-12 h-12 rounded-full bg-muted flex items-center justify-center mb-2">
              <Key className="size-6 text-muted-foreground" />
            </div>
            <CardTitle className="text-lg">Create your first API key</CardTitle>
            <CardDescription>
              API keys allow you to authenticate requests to the Airweave API.
            </CardDescription>
          </CardHeader>
          <CardContent className="text-center">
            <Button variant="outline">
              <Plus className="size-4 mr-2" />
              Create API Key
            </Button>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
