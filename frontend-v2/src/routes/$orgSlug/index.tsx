import { createFileRoute, Link, useParams } from "@tanstack/react-router";
import {
  ArrowRight,
  Cable,
  FolderOpen,
  Key,
  Plus,
  ShieldCheck,
  Webhook,
} from "lucide-react";

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
import { useOrg } from "@/lib/org-context";

export const Route = createFileRoute("/$orgSlug/")({
  component: DashboardPage,
});

// Sidebar content components for the dashboard
function DashboardDocs() {
  return <DocsContent docPath="welcome.mdx" />;
}

function DashboardCode() {
  return (
    <div className="space-y-4">
      <h3 className="text-base font-semibold">Quick Start</h3>
      <p className="text-muted-foreground text-sm">
        Get started with the Airweave SDK:
      </p>
      <pre className="bg-muted overflow-auto rounded-lg p-3 text-xs">
        <code>{`import { Airweave } from '@airweave/sdk';

const client = new Airweave({
  apiKey: process.env.AIRWEAVE_API_KEY
});

// Create a collection
const collection = await client.collections.create({
  name: 'My Knowledge Base'
});

// Sync data from a source
await client.sync({
  collection: collection.id,
  source: 'notion'
});

// Search your data
const results = await client.search({
  collection: collection.id,
  query: 'your search query'
});`}</code>
      </pre>
    </div>
  );
}

function DashboardHelp() {
  return (
    <div className="space-y-4">
      <h3 className="text-base font-semibold">Getting Started</h3>
      <p className="text-muted-foreground text-sm">
        Welcome to Airweave! Here's how to get started:
      </p>
      <div className="space-y-3">
        <div className="bg-muted rounded-lg p-3">
          <h4 className="text-sm font-medium">1. Create a Collection</h4>
          <p className="text-muted-foreground mt-1 text-xs">
            Collections are searchable knowledge bases for your data.
          </p>
        </div>
        <div className="bg-muted rounded-lg p-3">
          <h4 className="text-sm font-medium">2. Connect a Source</h4>
          <p className="text-muted-foreground mt-1 text-xs">
            Connect Notion, Slack, or other sources to sync your data.
          </p>
        </div>
        <div className="bg-muted rounded-lg p-3">
          <h4 className="text-sm font-medium">3. Search & Query</h4>
          <p className="text-muted-foreground mt-1 text-xs">
            Use the API or MCP to search across all your connected sources.
          </p>
        </div>
      </div>
    </div>
  );
}

function DashboardPage() {
  const { orgSlug } = useParams({ from: "/$orgSlug/" });
  const { organization } = useOrg();

  useRightSidebarContent({
    docs: <DashboardDocs />,
    code: <DashboardCode />,
    help: <DashboardHelp />,
  });

  const quickActions = [
    {
      title: "Collections",
      description: "Create and manage searchable knowledge bases",
      icon: FolderOpen,
      path: "collections" as const,
      action: "New Collection",
    },
    {
      title: "API Keys",
      description: "Generate keys for programmatic access",
      icon: Key,
      path: "api-keys" as const,
      action: "Create Key",
    },
    {
      title: "Webhooks",
      description: "Receive real-time event notifications",
      icon: Webhook,
      path: "webhooks" as const,
      action: "Add Webhook",
    },
    {
      title: "Auth Providers",
      description: "Configure OAuth for source connections",
      icon: ShieldCheck,
      path: "auth-providers" as const,
      action: "Add Provider",
    },
  ];

  return (
    <div className="space-y-8 p-6">
      {/* Welcome Section */}
      <div className="space-y-2">
        <h1 className="text-3xl font-bold tracking-tight">
          Welcome to Airweave
          {organization && (
            <span className="text-muted-foreground ml-2 text-xl font-normal">
              — {organization.name}
            </span>
          )}
        </h1>
        <p className="text-muted-foreground text-lg">
          Make any app searchable for your agent. Sync data from various sources
          with minimal configuration.
        </p>
      </div>

      {/* Quick Actions */}
      <div className="space-y-4">
        <h2 className="text-xl font-semibold">Quick Actions</h2>
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          {quickActions.map((item) => (
            <Card
              key={item.path}
              className="group transition-shadow hover:shadow-md"
            >
              <CardHeader className="pb-3">
                <div className="flex items-start justify-between">
                  <div className="bg-primary/10 rounded-lg p-2">
                    <item.icon className="text-primary size-5" />
                  </div>
                  <Button variant="ghost" size="sm" asChild>
                    <Link to={`/$orgSlug/${item.path}`} params={{ orgSlug }}>
                      {item.action}
                      <ArrowRight className="ml-1 size-4 transition-transform group-hover:translate-x-0.5" />
                    </Link>
                  </Button>
                </div>
                <CardTitle className="text-lg">{item.title}</CardTitle>
              </CardHeader>
              <CardContent>
                <CardDescription>{item.description}</CardDescription>
              </CardContent>
            </Card>
          ))}
        </div>
      </div>

      {/* Getting Started CTA */}
      <Card className="from-primary/5 to-primary/10 border-primary/20 bg-gradient-to-br">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Plus className="size-5" />
            Get Started
          </CardTitle>
          <CardDescription>
            Create your first collection to start syncing and searching your
            data.
          </CardDescription>
        </CardHeader>
        <CardContent className="flex gap-3">
          <Button asChild>
            <Link to="/$orgSlug/collections" params={{ orgSlug }}>
              <FolderOpen className="mr-2 size-4" />
              Create Collection
            </Link>
          </Button>
          <Button variant="outline" asChild>
            <Link to="/$orgSlug/logs" params={{ orgSlug }}>
              <Cable className="mr-2 size-4" />
              View Logs
            </Link>
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}
