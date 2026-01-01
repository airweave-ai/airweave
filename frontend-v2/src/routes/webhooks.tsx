import { createFileRoute } from "@tanstack/react-router";
import { Plus, Webhook } from "lucide-react";

import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { usePageHeader } from "@/components/ui/page-header";
import { useRightSidebarContent } from "@/components/ui/right-sidebar";

export const Route = createFileRoute("/webhooks")({ component: WebhooksPage });

function WebhooksDocs() {
  return (
    <div className="space-y-4">
      <h3 className="font-semibold text-base">Webhooks</h3>
      <p className="text-sm text-muted-foreground">
        Webhooks allow you to receive real-time notifications when events occur
        in your Airweave account.
      </p>
      <div className="space-y-2">
        <h4 className="font-medium text-sm">Supported Events</h4>
        <ul className="text-sm text-muted-foreground space-y-1">
          <li>Sync completed</li>
          <li>Sync failed</li>
          <li>New entities added</li>
          <li>Connection status changed</li>
        </ul>
      </div>
    </div>
  );
}

function WebhooksCode() {
  return (
    <div className="space-y-4">
      <h3 className="font-semibold text-base">Webhook Payload</h3>
      <p className="text-sm text-muted-foreground">
        Example webhook payload structure:
      </p>
      <pre className="bg-muted p-3 rounded-lg text-xs overflow-auto">
        <code>{`{
  "event": "sync.completed",
  "timestamp": "2024-01-15T10:30:00Z",
  "data": {
    "collection_id": "col_abc123",
    "source_connection_id": "src_xyz789",
    "entities_processed": 150,
    "duration_ms": 4500
  }
}`}</code>
      </pre>
    </div>
  );
}

function WebhooksHelp() {
  return (
    <div className="space-y-4">
      <h3 className="font-semibold text-base">Setting Up Webhooks</h3>
      <p className="text-sm text-muted-foreground">
        Webhooks are HTTP callbacks that receive POST requests when events
        occur.
      </p>
      <div className="p-3 bg-muted rounded-lg">
        <h4 className="font-medium text-sm">Requirements</h4>
        <ul className="text-xs text-muted-foreground mt-1 space-y-1">
          <li>HTTPS endpoint required</li>
          <li>Must respond with 2xx status</li>
          <li>Timeout: 30 seconds</li>
        </ul>
      </div>
    </div>
  );
}

function WebhooksPage() {
  usePageHeader({
    title: "Webhooks",
    description: "Receive real-time event notifications",
    actions: (
      <Button>
        <Plus className="size-4 mr-2" />
        Add Webhook
      </Button>
    ),
  });

  useRightSidebarContent({
    docs: <WebhooksDocs />,
    code: <WebhooksCode />,
    help: <WebhooksHelp />,
  });

  return (
    <div className="p-6">
      <EmptyState
        icon={<Webhook />}
        title="Add your first webhook"
        description="Get notified when sync jobs complete, fail, or when new data is available."
      >
        <Button variant="outline">
          <Plus className="size-4 mr-2" />
          Add Webhook
        </Button>
      </EmptyState>
    </div>
  );
}
