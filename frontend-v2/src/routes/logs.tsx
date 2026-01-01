import { createFileRoute } from "@tanstack/react-router";
import { Cable, Search } from "lucide-react";

import { Input } from "@/components/ui/input";
import { useRightSidebarContent } from "@/components/ui/right-sidebar";

export const Route = createFileRoute("/logs")({ component: LogsPage });

function LogsDocs() {
  return (
    <div className="space-y-4">
      <h3 className="font-semibold text-base">Sync Logs</h3>
      <p className="text-sm text-muted-foreground">
        View and monitor all synchronization activity across your collections
        and source connections.
      </p>
      <div className="space-y-2">
        <h4 className="font-medium text-sm">Log Types</h4>
        <ul className="text-sm text-muted-foreground space-y-1">
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
      <h3 className="font-semibold text-base">Logs API</h3>
      <p className="text-sm text-muted-foreground">
        Access logs programmatically:
      </p>
      <pre className="bg-muted p-3 rounded-lg text-xs overflow-auto">
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
      <h3 className="font-semibold text-base">Understanding Logs</h3>
      <p className="text-sm text-muted-foreground">
        Logs help you track the health and status of your data synchronization.
      </p>
      <div className="p-3 bg-muted rounded-lg">
        <h4 className="font-medium text-sm">Tip</h4>
        <p className="text-xs text-muted-foreground mt-1">
          Use filters to narrow down logs by collection, source, or time range.
        </p>
      </div>
    </div>
  );
}

function LogsPage() {
  useRightSidebarContent({
    docs: <LogsDocs />,
    code: <LogsCode />,
    help: <LogsHelp />,
  });

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold">Logs</h1>
          <p className="text-muted-foreground">
            Monitor synchronization activity
          </p>
        </div>
        <div className="relative w-64">
          <Search className="absolute left-2.5 top-2.5 size-4 text-muted-foreground" />
          <Input placeholder="Search logs..." className="pl-9" />
        </div>
      </div>

      <div className="flex flex-col items-center justify-center py-16 text-center">
        <div className="w-16 h-16 rounded-full bg-muted flex items-center justify-center mb-4">
          <Cable className="size-8 text-muted-foreground" />
        </div>
        <h2 className="text-lg font-semibold mb-2">No logs yet</h2>
        <p className="text-muted-foreground max-w-sm">
          Logs will appear here once you start syncing data from your connected
          sources.
        </p>
      </div>
    </div>
  );
}
