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
      <h3 className="text-base font-semibold">Collections API</h3>
      <p className="text-muted-foreground text-sm">
        Create and manage collections programmatically:
      </p>
      <pre className="bg-muted overflow-auto rounded-lg p-3 text-xs">
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
      <h3 className="text-base font-semibold">About Collections</h3>
      <p className="text-muted-foreground text-sm">
        Collections are searchable knowledge bases made up of synced data from
        one or more source connections.
      </p>
      <div className="space-y-3">
        <div className="bg-muted rounded-lg p-3">
          <h4 className="text-sm font-medium">Key Features</h4>
          <ul className="text-muted-foreground mt-1 space-y-1 text-xs">
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
        <Plus className="mr-2 size-4" />
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
          <Plus className="mr-2 size-4" />
          New Collection
        </Button>
      </EmptyState>
    </div>
  );
}
