import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Key, Copy, Loader2, Plus, Trash2, RotateCw, CheckCircle2 } from "lucide-react";
import { toast } from "sonner";
import { format, differenceInDays } from "date-fns";
import { cn } from "@/lib/utils";
import { useAPIKeysStore, type APIKey } from "@/lib/stores/apiKeys";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

const EXPIRATION_PRESETS = [
  { days: 30, label: "30 days" },
  { days: 60, label: "60 days" },
  { days: 90, label: "90 days", recommended: true },
  { days: 180, label: "180 days" },
  { days: 365, label: "365 days" },
];

export function APIKeysSettings() {
  const {
    apiKeys,
    isLoading,
    error,
    fetchAPIKeys,
    createAPIKey,
    rotateAPIKey,
    deleteAPIKey
  } = useAPIKeysStore();

  const [createDialogOpen, setCreateDialogOpen] = useState(false);
  const [selectedExpiration, setSelectedExpiration] = useState(90);
  const [creating, setCreating] = useState(false);
  const [newlyCreatedKey, setNewlyCreatedKey] = useState<APIKey | null>(null);
  const [copiedKey, setCopiedKey] = useState<string | null>(null);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [keyToDelete, setKeyToDelete] = useState<APIKey | null>(null);
  const [deleting, setDeleting] = useState(false);
  const [rotatingKeyId, setRotatingKeyId] = useState<string | null>(null);

  useEffect(() => {
    fetchAPIKeys();
  }, [fetchAPIKeys]);

  const handleCreateClick = () => {
    setSelectedExpiration(90);
    setCreateDialogOpen(true);
  };

  const handleConfirmCreate = async () => {
    setCreating(true);
    try {
      const newKey = await createAPIKey(selectedExpiration);
      setNewlyCreatedKey(newKey);
      setCreateDialogOpen(false);
      toast.success("API key created successfully");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to create API key");
    } finally {
      setCreating(false);
    }
  };

  const handleCopyKey = (key: string) => {
    navigator.clipboard.writeText(key).then(
      () => {
        setCopiedKey(key);
        toast.success("Copied to clipboard");
        setTimeout(() => setCopiedKey(null), 2000);
      },
      () => toast.error("Failed to copy")
    );
  };

  const handleRotateKey = async (apiKey: APIKey) => {
    setRotatingKeyId(apiKey.id);
    try {
      const newKey = await rotateAPIKey(apiKey.id);
      toast.success("Key rotated successfully");
      setNewlyCreatedKey(newKey);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to rotate key");
    } finally {
      setRotatingKeyId(null);
    }
  };

  const handleDeleteKey = async () => {
    if (!keyToDelete) return;
    setDeleting(true);
    try {
      await deleteAPIKey(keyToDelete.id);
      toast.success("API key deleted");
      if (newlyCreatedKey && newlyCreatedKey.id === keyToDelete.id) {
        setNewlyCreatedKey(null);
      }
      setDeleteDialogOpen(false);
      setKeyToDelete(null);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to delete key");
    } finally {
      setDeleting(false);
    }
  };

  const maskKey = (key: string) => {
    if (!key || key.length < 8) return key;
    return `${key.substring(0, 8)}${"•".repeat(32)}`;
  };

  const getDaysRemaining = (expirationDate: string) => {
    try {
      return differenceInDays(new Date(expirationDate), new Date());
    } catch {
      return 0;
    }
  };

  const getStatusColor = (daysRemaining: number) => {
    if (daysRemaining < 0) return "text-red-500";
    if (daysRemaining <= 7) return "text-amber-500";
    return "text-slate-500 dark:text-slate-400";
  };

  if (isLoading && apiKeys.length === 0) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="h-6 w-6 animate-spin text-slate-400" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold tracking-tight text-slate-900 dark:text-slate-50">API Keys</h2>
          <p className="text-sm text-slate-600 dark:text-slate-400 mt-0.5">
            Manage access tokens for programmatic integration
          </p>
        </div>
        <Button
          onClick={handleCreateClick}
          size="default"
          className="h-9 gap-2 px-3 bg-slate-800 hover:bg-slate-700 dark:bg-slate-200 dark:hover:bg-slate-300 text-slate-50 dark:text-slate-900 font-medium"
        >
          <Plus className="h-4 w-4" />
          Create key
        </Button>
      </div>

      {/* New Key Display */}
      {newlyCreatedKey && newlyCreatedKey.decrypted_key && (
        <div className="rounded-lg border border-slate-200 dark:border-slate-800 p-4">
          <div className="flex items-start justify-between gap-4 mb-3">
            <div className="space-y-0.5">
              <p className="text-xs font-medium text-slate-700 dark:text-slate-300">Your new API key</p>
              <p className="text-xs text-slate-500 dark:text-slate-400">
                Copy and save it now — you won't see it again
              </p>
            </div>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setNewlyCreatedKey(null)}
              className="h-6 text-xs text-slate-500 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-300"
            >
              Dismiss
            </Button>
          </div>
          <div className="flex items-center gap-2">
            <code className="flex-1 text-xs font-mono px-3 py-2 rounded-md bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-800 text-slate-900 dark:text-slate-100">
              {newlyCreatedKey.decrypted_key}
            </code>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => handleCopyKey(newlyCreatedKey.decrypted_key)}
              className="h-[34px] gap-2 text-xs bg-slate-100 hover:bg-slate-200 dark:bg-slate-800 dark:hover:bg-slate-700"
            >
              {copiedKey === newlyCreatedKey.decrypted_key ? (
                <CheckCircle2 className="h-3.5 w-3.5" />
              ) : (
                <Copy className="h-3.5 w-3.5" />
              )}
              Copy
            </Button>
          </div>
        </div>
      )}

      {/* Error State */}
      {error && (
        <div className="rounded-lg border border-red-200 dark:border-red-900/50 bg-red-50 dark:bg-red-900/10 px-4 py-3 text-sm text-red-600 dark:text-red-400">
          {error}
        </div>
      )}

      {/* Keys List */}
      {apiKeys.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-16 text-center">
          <div className="rounded-full bg-slate-100 dark:bg-slate-800 p-4 mb-4">
            <Key className="h-6 w-6 text-slate-400" />
          </div>
          <p className="text-sm font-medium mb-1">No API keys yet</p>
          <p className="text-sm text-slate-500 dark:text-slate-400 mb-4">
            Create your first key to start using the API
          </p>
          <Button onClick={handleCreateClick} size="sm" variant="outline">
            <Plus className="h-4 w-4 mr-2" />
            Create key
          </Button>
        </div>
      ) : (
        <div className="space-y-3">
          {apiKeys.map((apiKey) => {
            const daysRemaining = getDaysRemaining(apiKey.expiration_date);
            const isExpired = daysRemaining < 0;
            const isExpiringSoon = daysRemaining >= 0 && daysRemaining <= 7;

            return (
              <div
                key={apiKey.id}
                className={cn(
                  "rounded-lg border bg-white dark:bg-slate-900/50",
                  isExpired
                    ? "border-red-200 dark:border-red-900/50"
                    : "border-slate-200 dark:border-slate-800"
                )}
              >
                <div className="p-4">
                  <div className="flex items-start justify-between gap-4">
                    {/* Key Info */}
                    <div className="flex-1 min-w-0 space-y-3">
                      <div className="flex items-center gap-3">
                        <code className="text-xs font-mono font-medium">
                          {maskKey(apiKey.decrypted_key)}
                        </code>
                        {isExpired && (
                          <span className="inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400">
                            Expired
                          </span>
                        )}
                        {isExpiringSoon && !isExpired && (
                          <span className="inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400">
                            Expiring soon
                          </span>
                        )}
                      </div>
                      <div className="flex items-center gap-4 text-xs text-slate-500 dark:text-slate-400">
                        <span>Created {format(new Date(apiKey.created_at), "MMM d, yyyy")}</span>
                        <span className="text-slate-300 dark:text-slate-700">•</span>
                        <span className={getStatusColor(daysRemaining)}>
                          {isExpired
                            ? `Expired ${Math.abs(daysRemaining)} day${Math.abs(daysRemaining) === 1 ? "" : "s"} ago`
                            : `Expires in ${daysRemaining} day${daysRemaining === 1 ? "" : "s"}`}
                        </span>
                      </div>
                    </div>

                    {/* Actions */}
                    <div className="flex items-center gap-1">
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => handleCopyKey(apiKey.decrypted_key)}
                        className="h-8 w-8 text-slate-500 hover:text-slate-900 dark:hover:text-slate-100"
                        title="Copy key"
                      >
                        {copiedKey === apiKey.decrypted_key ? (
                          <CheckCircle2 className="h-4 w-4" />
                        ) : (
                          <Copy className="h-4 w-4" />
                        )}
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => handleRotateKey(apiKey)}
                        disabled={rotatingKeyId === apiKey.id}
                        className="h-8 w-8 text-slate-500 hover:text-slate-900 dark:hover:text-slate-100"
                        title="Rotate key"
                      >
                        {rotatingKeyId === apiKey.id ? (
                          <Loader2 className="h-4 w-4 animate-spin" />
                        ) : (
                          <RotateCw className="h-4 w-4" />
                        )}
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => {
                          setKeyToDelete(apiKey);
                          setDeleteDialogOpen(true);
                        }}
                        className="h-8 w-8 text-slate-500 hover:text-red-600 dark:hover:text-red-500"
                        title="Delete key"
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </div>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Create Dialog */}
      <Dialog open={createDialogOpen} onOpenChange={setCreateDialogOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader className="space-y-2">
            <DialogTitle className="text-xl font-semibold">Create API key</DialogTitle>
            <DialogDescription className="text-slate-500 dark:text-slate-400">
              Choose how long this key should remain valid
            </DialogDescription>
          </DialogHeader>

          <div className="py-6 space-y-2">
            {EXPIRATION_PRESETS.map((preset) => (
              <button
                key={preset.days}
                onClick={() => setSelectedExpiration(preset.days)}
                className={cn(
                  "w-full flex items-center justify-between px-4 py-3.5 rounded-lg border text-left transition-colors",
                  selectedExpiration === preset.days
                    ? "border-primary bg-primary/5 dark:bg-primary/10"
                    : "border-slate-200 dark:border-slate-800"
                )}
              >
                <span className={cn(
                  "text-sm font-medium",
                  selectedExpiration === preset.days
                    ? "text-slate-900 dark:text-slate-50"
                    : "text-slate-700 dark:text-slate-300"
                )}>{preset.label}</span>
                {preset.recommended && (
                  <span className="text-xs px-2 py-0.5 rounded-md bg-blue-500/10 text-blue-600 dark:text-blue-400 font-medium">
                    Recommended
                  </span>
                )}
              </button>
            ))}
          </div>

          <DialogFooter className="gap-2">
            <Button
              variant="outline"
              onClick={() => setCreateDialogOpen(false)}
              disabled={creating}
              className="flex-1 sm:flex-none"
            >
              Cancel
            </Button>
            <Button
              onClick={handleConfirmCreate}
              disabled={creating}
              className="flex-1 sm:flex-none bg-slate-800 hover:bg-slate-700 dark:bg-slate-200 dark:hover:bg-slate-300 text-slate-50 dark:text-slate-900"
            >
              {creating ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Creating...
                </>
              ) : (
                "Create key"
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete Dialog */}
      <Dialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Delete API key</DialogTitle>
            <DialogDescription>
              This action cannot be undone. Any applications using this key will lose access immediately.
            </DialogDescription>
          </DialogHeader>

          {keyToDelete && (
            <div className="my-4 rounded-lg border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-900/50 p-3">
              <code className="text-sm font-mono">
                {maskKey(keyToDelete.decrypted_key)}
              </code>
            </div>
          )}

          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setDeleteDialogOpen(false)}
              disabled={deleting}
            >
              Cancel
            </Button>
            <Button
              variant="destructive"
              onClick={handleDeleteKey}
              disabled={deleting}
            >
              {deleting ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Deleting...
                </>
              ) : (
                <>
                  <Trash2 className="mr-2 h-4 w-4" />
                  Delete key
                </>
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
