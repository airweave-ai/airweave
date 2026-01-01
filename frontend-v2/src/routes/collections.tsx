import { createFileRoute } from "@tanstack/react-router";
import { FolderOpen, Plus } from "lucide-react";

import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { usePageHeader } from "@/components/ui/page-header";
import { useRightSidebarContent } from "@/components/ui/right-sidebar";
import { DocsContent } from "@/hooks/use-docs-content";

export const Route = createFileRoute("/collections")({
  component: CollectionsPage,
});

function CollectionsDocs() {
  return <DocsContent docPath="concepts.mdx" />;
}

function CollectionsCode() {
  return (
    <div className="space-y-4">
      <h3 className="font-semibold text-base">Collections API</h3>
      <p className="text-sm text-muted-foreground">
        Create and manage collections programmatically:
      </p>
      <pre className="bg-muted p-3 rounded-lg text-xs overflow-auto">
        <code>{`import { Airweave } from '@airweave/sdk';

const client = new Airweave({
  apiKey: process.env.AIRWEAVE_API_KEY
});

// Create a collection
const collection = await client.collections.create({
  name: 'My Collection'
});

// Search the collection
const results = await client.collections.search(
  collection.readable_id,
  { query: 'your search query' }
);`}</code>
      </pre>
    </div>
  );
}

function CollectionsHelp() {
  return (
    <div className="space-y-4">
      <h3 className="font-semibold text-base">About Collections</h3>
      <p className="text-sm text-muted-foreground">
        Collections are searchable knowledge bases made up of synced data from
        one or more source connections.
      </p>
      <div className="space-y-3">
        <div className="p-3 bg-muted rounded-lg">
          <h4 className="font-medium text-sm">Key Features</h4>
          <ul className="text-xs text-muted-foreground mt-1 space-y-1">
            <li>Unified search across multiple sources</li>
            <li>Vector embeddings for semantic search</li>
            <li>Real-time data synchronization</li>
          </ul>
        </div>
      </div>
    </div>
  );
}

function CollectionsPage() {
  usePageHeader({
    title: "Collections",
    description: "Manage your searchable knowledge bases",
    actions: (
      <Button>
        <Plus className="size-4 mr-2" />
        New Collection
      </Button>
    ),
  });

  useRightSidebarContent({
    docs: <CollectionsDocs />,
    code: <CollectionsCode />,
    help: <CollectionsHelp />,
  });

  return (
    <div className="p-6">
      <EmptyState
        icon={<FolderOpen />}
        title="Create your first collection"
        description="Collections help you organize and search your data from multiple sources."
      >
        <Button variant="outline">
          <Plus className="size-4 mr-2" />
          New Collection
        </Button>
      </EmptyState>
    </div>
  );
}
