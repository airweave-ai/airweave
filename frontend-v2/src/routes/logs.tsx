import { createFileRoute } from "@tanstack/react-router";
import { Cable, Search } from "lucide-react";

import { EmptyState } from "@/components/ui/empty-state";
import { Input } from "@/components/ui/input";
import { usePageHeader } from "@/components/ui/page-header";
import { useRightSidebarContent } from "@/components/ui/right-sidebar";

export const Route = createFileRoute("/logs")({ component: LogsPage });

function LogsDocs() {
  return (
    <div className="space-y-4">
      <h3 className="text-base font-semibold">Sync Logs</h3>
      <p className="text-muted-foreground text-sm">
        View and monitor all synchronization activity across your collections
        and source connections.
      </p>
      <div className="space-y-2">
        <h4 className="text-sm font-medium">Log Types</h4>
        <ul className="text-muted-foreground space-y-1 text-sm">
          <li>Sync started/completed events</li>
          <li>Entity processing details</li>
          <li>Error and warning messages</li>
          <li>Performance metrics</li>
        </ul>
      </div>
    </div>
  );
}

function LogsCode() {
  return (
    <div className="space-y-4">
      <h3 className="text-base font-semibold">Logs API</h3>
      <p className="text-muted-foreground text-sm">
        Access logs programmatically:
      </p>
      <pre className="bg-muted overflow-auto rounded-lg p-3 text-xs">
        <code>{`// Get sync job status
const job = await client.syncJobs.get(jobId);

console.log(job.status);
console.log(job.entities_processed);
console.log(job.started_at);
console.log(job.completed_at);`}</code>
      </pre>
    </div>
  );
}

function LogsHelp() {
  return (
    <div className="space-y-4">
      <h3 className="text-base font-semibold">Understanding Logs</h3>
      <p className="text-muted-foreground text-sm">
        Logs help you track the health and status of your data synchronization.
      </p>
      <div className="bg-muted rounded-lg p-3">
        <h4 className="text-sm font-medium">Tip</h4>
        <p className="text-muted-foreground mt-1 text-xs">
          Use filters to narrow down logs by collection, source, or time range.
        </p>
      </div>
    </div>
  );
}

function LogsPage() {
  usePageHeader({
    title: "Logs",
    description: "Monitor synchronization activity",
    actions: (
      <div className="relative w-64">
        <Search className="text-muted-foreground absolute top-2.5 left-2.5 size-4" />
        <Input placeholder="Search logs..." className="pl-9" />
      </div>
    ),
  });

  useRightSidebarContent({
    docs: <LogsDocs />,
    code: <LogsCode />,
    help: <LogsHelp />,
  });

  return (
    <div className="p-6">
      <EmptyState
        icon={<Cable />}
        title="No logs yet"
        description="Logs will appear here once you start syncing data from your connected sources."
      />
    </div>
  );
}
