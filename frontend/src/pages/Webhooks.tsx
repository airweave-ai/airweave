import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ExternalLink, Loader2, Plus, RefreshCw } from "lucide-react";
import { cn } from "@/lib/utils";
import {
  useSubscriptions,
  useMessages,
  type Subscription,
  type Message,
} from "@/hooks/use-webhooks";
import {
  MessagesList,
  MessageDetail,
  WebhooksTab,
  CreateWebhookModal,
  EditWebhookModal,
} from "@/components/webhooks";

/**
 * Logs Tab - Split pane view showing webhook message logs
 */
function LogsTab() {
  const [selectedMessage, setSelectedMessage] = useState<Message | null>(null);
  const [searchQuery, setSearchQuery] = useState("");

  const { data: messages = [], isLoading, isFetching, refetch } = useMessages();

  // Filter messages
  const filteredMessages = messages.filter((msg) => {
    if (!searchQuery) return true;
    return (
      msg.event_type.toLowerCase().includes(searchQuery.toLowerCase()) ||
      msg.id.toLowerCase().includes(searchQuery.toLowerCase())
    );
  });

  // Auto-select first message
  useEffect(() => {
    if (filteredMessages.length > 0 && !selectedMessage) {
      setSelectedMessage(filteredMessages[0]);
    }
  }, [filteredMessages, selectedMessage]);

  return (
    <div className="flex h-[calc(100vh-240px)] min-h-[400px] border rounded-lg overflow-hidden">
      {/* Left - List */}
      <div className="w-[380px] shrink-0 border-r">
        <MessagesList
          messages={filteredMessages}
          selectedId={selectedMessage?.id ?? null}
          onSelect={setSelectedMessage}
          isLoading={isLoading}
          searchQuery={searchQuery}
          onSearchChange={setSearchQuery}
        />
      </div>

      {/* Right - Detail */}
      <div className="flex-1 flex flex-col">
        <div className="flex items-center justify-end px-3 py-1.5 border-b">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => refetch()}
            disabled={isFetching}
            className="h-7 px-2 text-xs text-muted-foreground"
          >
            <RefreshCw className={cn("size-3 mr-1.5", isFetching && "animate-spin")} />
            Refresh
          </Button>
        </div>
        <div className="flex-1 overflow-hidden">
          <MessageDetail message={selectedMessage} />
        </div>
      </div>
    </div>
  );
}

/**
 * Webhooks Page - Main page for webhooks and message logs
 */
const WebhooksPage = () => {
  const {
    data: subscriptions = [],
    isLoading: isLoadingSubscriptions,
    error,
  } = useSubscriptions();

  const [createModalOpen, setCreateModalOpen] = useState(false);
  const [selectedSubscriptionId, setSelectedSubscriptionId] = useState<string | null>(null);
  const [editModalOpen, setEditModalOpen] = useState(false);
  const [activeTab, setActiveTab] = useState("webhooks");

  const handleSubscriptionClick = (subscription: Subscription) => {
    setSelectedSubscriptionId(subscription.id);
    setEditModalOpen(true);
  };

  if (isLoadingSubscriptions) {
    return (
      <div className="flex items-center justify-center h-[50vh]">
        <Loader2 className="size-5 animate-spin text-muted-foreground/40" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center h-[50vh]">
        <p className="text-xs text-destructive">
          {error instanceof Error ? error.message : "Failed to load"}
        </p>
      </div>
    );
  }

  return (
    <div className="mx-auto w-full max-w-[1800px] px-6 py-6 pb-8">
      {/* Header */}
      <div className="flex items-center justify-between mb-1">
        <h1 className="text-2xl sm:text-3xl font-bold">
          Webhooks
          <span className="ml-2 text-[10px] font-medium text-muted-foreground/60 uppercase tracking-wide align-middle">beta</span>
        </h1>
        <Button onClick={() => setCreateModalOpen(true)} size="sm" className="h-8">
          <Plus className="mr-1.5 size-3.5" />
          Add subscription
        </Button>
      </div>
      <p className="text-sm text-muted-foreground mb-4">
        Get notified when syncs complete or fail.{" "}
        <a
          href="https://docs.airweave.ai/webhooks/overview"
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center text-primary hover:underline"
        >
          Learn more
          <ExternalLink className="ml-1 size-3" />
        </a>
      </p>

      {/* Tabs */}
      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList className="h-8 p-0.5 bg-muted/50 mb-3">
          <TabsTrigger value="webhooks" className="h-7 text-xs px-3">
            Subscriptions
            {subscriptions.length > 0 && (
              <span className="ml-1.5 text-[10px] text-muted-foreground">
                {subscriptions.length}
              </span>
            )}
          </TabsTrigger>
          <TabsTrigger value="logs" className="h-7 text-xs px-3">
            Logs
          </TabsTrigger>
        </TabsList>

        <TabsContent value="webhooks" className="mt-0">
          <WebhooksTab
            subscriptions={subscriptions}
            onEdit={handleSubscriptionClick}
            onCreateClick={() => setCreateModalOpen(true)}
          />
        </TabsContent>

        <TabsContent value="logs" className="mt-0">
          <LogsTab />
        </TabsContent>
      </Tabs>

      {/* Modals */}
      <CreateWebhookModal open={createModalOpen} onOpenChange={setCreateModalOpen} />
      <EditWebhookModal
        subscriptionId={selectedSubscriptionId}
        open={editModalOpen}
        onOpenChange={setEditModalOpen}
      />
    </div>
  );
};

export default WebhooksPage;
