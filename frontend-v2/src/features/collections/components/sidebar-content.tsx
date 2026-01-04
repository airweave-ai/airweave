import { DocsContent } from "@/hooks/use-docs-content";

export function CollectionsDocs() {
  return <DocsContent docPath="concepts.mdx" />;
}

export function CollectionsCode() {
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

export function CollectionsHelp() {
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
