import React, { useEffect, useState } from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from "@/components/ui/select";
import { apiClient } from "@/lib/api";
import { Label } from "@/components/ui/label";
import { getAppIconUrl } from "@/lib/utils/icons";
import { format } from "date-fns";
import { Database } from "lucide-react";
import { useTheme } from "@/lib/theme-provider";

interface SyncInfo {
  id: string;
  name: string;
  description?: string;
  status?: string;
  modified_at: string;
  source_connection?: {
    short_name: string;
    name: string;
  };
}

interface CreateChatDialogProps {
  open: boolean;
  preselectedSyncId?: string;
  onOpenChange: (open: boolean) => void;
  onChatCreated: (newChatId: string) => void;
}

export function CreateChatDialog({
  open,
  preselectedSyncId,
  onOpenChange,
  onChatCreated
}: CreateChatDialogProps) {
  const [syncs, setSyncs] = useState<SyncInfo[]>([]);
  const [syncId, setSyncId] = useState<string>("");
  const [chatName, setChatName] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const { resolvedTheme } = useTheme();

  // Reset and load data when dialog opens
  useEffect(() => {
    if (open) {
      void loadSyncs();
      setChatName("");
    }
  }, [open]);

  // Set preselected sync after syncs are loaded
  useEffect(() => {
    if (preselectedSyncId && syncs.length > 0) {
      setSyncId(preselectedSyncId);
    }
  }, [preselectedSyncId, syncs]);

  async function loadSyncs() {
    try {
      setIsLoading(true);
      const resp = await apiClient.get("/sync", {
        with_source_connection: "true",
        skip: 0,
        limit: 100
      });

      const syncData = await resp.json();

      // Filter active syncs and sort by modified_at desc
      const processedSyncs = syncData
        .filter((sync: any) => sync.status === 'active')
        .map((sync: any) => ({
          id: sync.id,
          name: sync.name || `Sync ${sync.id}`,
          description: sync.description,
          status: sync.status,
          modified_at: sync.modified_at,
          source_connection: sync.source_connection
        }))
        .sort((a: SyncInfo, b: SyncInfo) =>
          new Date(b.modified_at).getTime() - new Date(a.modified_at).getTime()
        );

      setSyncs(processedSyncs);
    } catch (err) {
      console.error("Failed to load syncs: ", err);
    } finally {
      setIsLoading(false);
    }
  }

  async function handleCreateChat() {
    if (!syncId) return;

    try {
      setIsLoading(true);
      const resp = await apiClient.post("/chat", {
        name: chatName || "New Chat",
        sync_id: syncId,
        model_name: "gpt-4o-mini",
        model_settings: {
          temperature: 0.7,
          max_tokens: 1000,
        },
      });
      const chatData = await resp.json();
      onChatCreated(chatData.id);
      onOpenChange(false);
    } catch (err) {
      console.error("Failed to create chat: ", err);
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[800px]">
        <DialogHeader className="mb-6">
          <DialogTitle>Create New Chat</DialogTitle>
          <DialogDescription>Select a sync and provide optional details, then create your chat.</DialogDescription>
        </DialogHeader>
        <div className="space-y-8">
          <div className="space-y-2">
            <Label className="text-sm font-medium mb-2.5">Chat Name</Label>
            <Input
              value={chatName}
              onChange={(e) => setChatName(e.target.value)}
              className="h-11"
              placeholder="New Chat"
            />
          </div>
          <div>
            <Label className="text-sm font-medium mb-5">Sync</Label>
            <Select onValueChange={setSyncId} value={syncId}>
              <SelectTrigger className="w-full h-auto py-4 px-4">
                {syncId ? (
                  <div className="flex-1 space-y-2">
                    {syncs.find(s => s.id === syncId) && (
                      <>
                        <div className="flex items-center gap-2">
                          <img
                            src={getAppIconUrl(
                              syncs.find(s => s.id === syncId)?.source_connection?.short_name || 'default',
                              resolvedTheme
                            )}
                            className="h-5 w-5"
                            alt="Source"
                          />
                          <span className="font-medium">
                            {syncs.find(s => s.id === syncId)?.name}
                          </span>
                        </div>
                        <div className="flex gap-4 text-xs text-muted-foreground">
                          <span className="font-mono">{syncId}</span>
                          <span>
                            Modified: {format(
                              new Date(syncs.find(s => s.id === syncId)?.modified_at || ''),
                              'MMM d, yyyy HH:mm'
                            )}
                          </span>
                        </div>
                      </>
                    )}
                  </div>
                ) : (
                  <div className="text-left text-muted-foreground">
                    <p className="font-medium">Select a sync</p>
                    <p className="text-xs mt-0.5">Choose a data source to chat with</p>
                  </div>
                )}
              </SelectTrigger>
              <SelectContent className="max-h-[400px]">
                {syncs.length === 0 && !isLoading && (
                  <SelectItem value="no-syncs" disabled className="py-4">
                    No syncs available
                  </SelectItem>
                )}
                {syncs.map((s) => (
                  <SelectItem key={s.id} value={s.id} className="py-4">
                    <div className="space-y-2">
                      <div className="flex items-center gap-2">
                        <img
                          src={getAppIconUrl(s.source_connection?.short_name || 'default', resolvedTheme)}
                          className="h-5 w-5"
                          alt={s.source_connection?.name || 'Source'}
                        />
                        <span className="font-medium">{s.name}</span>
                      </div>
                      {s.description && (
                        <p className="text-sm text-muted-foreground">
                          {s.description}
                        </p>
                      )}
                      <div className="flex gap-4 text-xs text-muted-foreground">
                        <span className="font-mono">{s.id}</span>
                        <span>Modified: {format(new Date(s.modified_at), 'MMM d, yyyy HH:mm')}</span>
                      </div>
                    </div>
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>
        <div className="mt-8 flex justify-end space-x-2">
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button
            onClick={handleCreateChat}
            disabled={!syncId || isLoading}
          >
            {isLoading ? "Creating..." : "Create"}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
