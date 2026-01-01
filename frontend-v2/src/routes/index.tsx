import { createFileRoute, Link } from "@tanstack/react-router";
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

export const Route = createFileRoute("/")({ component: DashboardPage });

// Sidebar content components for the dashboard
function DashboardDocs() {
  return <DocsContent docPath="welcome.mdx" />;
}

function DashboardCode() {
  return (
    <div className="space-y-4">
      <h3 className="font-semibold text-base">Quick Start</h3>
      <p className="text-sm text-muted-foreground">
        Get started with the Airweave SDK:
      </p>
      <pre className="bg-muted p-3 rounded-lg text-xs overflow-auto">
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
      <h3 className="font-semibold text-base">Getting Started</h3>
      <p className="text-sm text-muted-foreground">
        Welcome to Airweave! Here's how to get started:
      </p>
      <div className="space-y-3">
        <div className="p-3 bg-muted rounded-lg">
          <h4 className="font-medium text-sm">1. Create a Collection</h4>
          <p className="text-xs text-muted-foreground mt-1">
            Collections are searchable knowledge bases for your data.
          </p>
        </div>
        <div className="p-3 bg-muted rounded-lg">
          <h4 className="font-medium text-sm">2. Connect a Source</h4>
          <p className="text-xs text-muted-foreground mt-1">
            Connect Notion, Slack, or other sources to sync your data.
          </p>
        </div>
        <div className="p-3 bg-muted rounded-lg">
          <h4 className="font-medium text-sm">3. Search & Query</h4>
          <p className="text-xs text-muted-foreground mt-1">
            Use the API or MCP to search across all your connected sources.
          </p>
        </div>
      </div>
    </div>
  );
}

const quickActions = [
  {
    title: "Collections",
    description: "Create and manage searchable knowledge bases",
    icon: FolderOpen,
    href: "/collections",
    action: "New Collection",
  },
  {
    title: "API Keys",
    description: "Generate keys for programmatic access",
    icon: Key,
    href: "/api-keys",
    action: "Create Key",
  },
  {
    title: "Webhooks",
    description: "Receive real-time event notifications",
    icon: Webhook,
    href: "/webhooks",
    action: "Add Webhook",
  },
  {
    title: "Auth Providers",
    description: "Configure OAuth for source connections",
    icon: ShieldCheck,
    href: "/auth-providers",
    action: "Add Provider",
  },
];

function DashboardPage() {
  useRightSidebarContent({
    docs: <DashboardDocs />,
    code: <DashboardCode />,
    help: <DashboardHelp />,
  });

  return (
    <div className="p-6 space-y-8">
      {/* Welcome Section */}
      <div className="space-y-2">
        <h1 className="text-3xl font-bold tracking-tight">
          Welcome to Airweave
        </h1>
        <p className="text-muted-foreground text-lg">
          Make any app searchable for your agent. Sync data from various sources
          with minimal configuration.
        </p>
      </div>

      {/* Quick Actions */}
      <div className="space-y-4">
        <h2 className="text-xl font-semibold">Quick Actions</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {quickActions.map((item) => (
            <Card
              key={item.href}
              className="group hover:shadow-md transition-shadow"
            >
              <CardHeader className="pb-3">
                <div className="flex items-start justify-between">
                  <div className="p-2 rounded-lg bg-primary/10">
                    <item.icon className="size-5 text-primary" />
                  </div>
                  <Button variant="ghost" size="sm" asChild>
                    <Link to={item.href}>
                      {item.action}
                      <ArrowRight className="ml-1 size-4 group-hover:translate-x-0.5 transition-transform" />
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
      <Card className="bg-gradient-to-br from-primary/5 to-primary/10 border-primary/20">
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
            <Link to="/collections">
              <FolderOpen className="mr-2 size-4" />
              Create Collection
            </Link>
          </Button>
          <Button variant="outline" asChild>
            <Link to="/logs">
              <Cable className="mr-2 size-4" />
              View Logs
            </Link>
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}
