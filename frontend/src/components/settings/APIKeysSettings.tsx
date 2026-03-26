import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Key, Copy, Loader2, Plus, Trash2, RotateCw, CheckCircle2, Activity,
  ChevronDown, ChevronUp,
} from "lucide-react";
import { toast } from "sonner";
import { differenceInDays } from "date-fns";
import { formatBackendTimestamp } from "@/utils/dateTime";
import { cn } from "@/lib/utils";
import {
  useAPIKeysStore,
  type APIKey,
  type APIKeyUsageLogEntry,
  type APIKeyUsageStats,
} from "@/lib/stores/apiKeys";
import { useOrganizationContext } from "@/hooks/use-organization-context";
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
];

export function APIKeysSettings() {
  const { canManageOrganization } = useOrganizationContext();
  const canManage = canManageOrganization();
  const {
    apiKeys,
    isLoading,
    error,
    usageStats,
    usageLogs,
    usageLogsHasMore,
    fetchAPIKeys,
    createAPIKey,
    rotateAPIKey,
    deleteAPIKey,
    fetchUsageStats,
    fetchUsageLogs,
  } = useAPIKeysStore();

  const [createDialogOpen, setCreateDialogOpen] = useState(false);
  const [selectedExpiration, setSelectedExpiration] = useState(90);
  const [description, setDescription] = useState("");
  const [creating, setCreating] = useState(false);
  const [newlyCreatedKey, setNewlyCreatedKey] = useState<APIKey | null>(null);
  const [copiedKey, setCopiedKey] = useState<string | null>(null);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [keyToDelete, setKeyToDelete] = useState<APIKey | null>(null);
  const [deleting, setDeleting] = useState(false);
  const [rotateDialogOpen, setRotateDialogOpen] = useState(false);
  const [keyToRotate, setKeyToRotate] = useState<APIKey | null>(null);
  const [rotatingKeyId, setRotatingKeyId] = useState<string | null>(null);
  const [expandedKeyId, setExpandedKeyId] = useState<string | null>(null);
  const [loadingActivity, setLoadingActivity] = useState<string | null>(null);

  useEffect(() => {
    fetchAPIKeys(true);
  }, [fetchAPIKeys]);

  const handleCreateClick = () => {
    setSelectedExpiration(90);
    setDescription("");
    setCreateDialogOpen(true);
  };

  const handleConfirmCreate = async () => {
    setCreating(true);
    try {
      const desc = description.trim() || undefined;
      const newKey = await createAPIKey(selectedExpiration, desc);
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

  const handleRotateClick = (apiKey: APIKey) => {
    setKeyToRotate(apiKey);
    setRotateDialogOpen(true);
  };

  const handleConfirmRotate = async () => {
    if (!keyToRotate) return;
    setRotatingKeyId(keyToRotate.id);
    setRotateDialogOpen(false);
    try {
      const newKey = await rotateAPIKey(keyToRotate.id);
      toast.success("Key rotated successfully");
      setNewlyCreatedKey(newKey);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to rotate key");
    } finally {
      setRotatingKeyId(null);
      setKeyToRotate(null);
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

  const handleToggleActivity = async (apiKey: APIKey) => {
    if (expandedKeyId === apiKey.id) {
      setExpandedKeyId(null);
      return;
    }
    setExpandedKeyId(apiKey.id);
    setLoadingActivity(apiKey.id);
    try {
      await Promise.all([
        fetchUsageStats(apiKey.id),
        fetchUsageLogs(apiKey.id, 0, 20),
      ]);
    } catch {
      toast.error("Failed to load activity");
    } finally {
      setLoadingActivity(null);
    }
  };

  const handleLoadMoreLogs = async (keyId: string) => {
    const existing = usageLogs[keyId] || [];
    setLoadingActivity(keyId);
    try {
      await fetchUsageLogs(keyId, existing.length, 20);
    } catch {
      toast.error("Failed to load more logs");
    } finally {
      setLoadingActivity(null);
    }
  };

  const displayKeyPrefix = (apiKey: APIKey) => {
    if (apiKey.key_prefix) {
      return `${apiKey.key_prefix}${"*".repeat(24)}`;
    }
    return `${"?".repeat(8)}${"*".repeat(24)}`;
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
    if (daysRemaining <= 7) return "text-red-400";
    if (daysRemaining <= 30) return "text-orange-500";
    if (daysRemaining <= 60) return "text-amber-500";
    return "text-green-600 dark:text-green-400";
  };

  if (!canManage) {
    return (
      <div className="flex flex-col items-center justify-center py-16 text-center">
        <div className="rounded-full bg-slate-100 dark:bg-slate-800 p-4 mb-4">
          <Key className="h-6 w-6 text-slate-400" />
        </div>
        <p className="text-sm font-medium mb-1">API key management</p>
        <p className="text-sm text-slate-500 dark:text-slate-400">
          Only admins and owners can manage API keys
        </p>
      </div>
    );
  }

  const truncate = (str: string | null, len: number) => {
    if (!str) return "-";
    return str.length > len ? str.slice(0, len) + "..." : str;
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
              onClick={() => newlyCreatedKey.decrypted_key && handleCopyKey(newlyCreatedKey.decrypted_key)}
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
          {[...apiKeys].sort((a, b) => {
            const statusOrder = { active: 0, expired: 1, revoked: 2 };
            const aOrder = statusOrder[a.status] ?? 1;
            const bOrder = statusOrder[b.status] ?? 1;
            if (aOrder !== bOrder) return aOrder - bOrder;
            return new Date(b.created_at).getTime() - new Date(a.created_at).getTime();
          }).map((apiKey) => {
            const daysRemaining = getDaysRemaining(apiKey.expiration_date);
            const isExpired = daysRemaining < 0 || apiKey.status === "expired";
            const isRevoked = apiKey.status === "revoked";
            const isExpiringSoon = daysRemaining >= 0 && daysRemaining <= 7;
            const isExpanded = expandedKeyId === apiKey.id;
            const stats = usageStats[apiKey.id];
            const logs = usageLogs[apiKey.id] || [];

            return (
              <div
                key={apiKey.id}
                className={cn(
                  "rounded-lg border bg-white dark:bg-slate-900/50",
                  isExpired || isRevoked
                    ? "border-red-200 dark:border-red-900/50"
                    : "border-slate-200 dark:border-slate-800"
                )}
              >
                <div className="p-4">
                  <div className="flex items-start justify-between gap-4">
                    {/* Key Info */}
                    <div className="flex-1 min-w-0 space-y-3">
                      {apiKey.description && (
                        <p className="text-sm font-medium text-slate-900 dark:text-slate-100">
                          {apiKey.description}
                        </p>
                      )}
                      <div className="flex items-center gap-3">
                        <code className="text-xs font-mono font-medium">
                          {displayKeyPrefix(apiKey)}
                        </code>
                        {isExpired && (
                          <span className="inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400">
                            Expired
                          </span>
                        )}
                        {isRevoked && !isExpired && (
                          <span className="inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400">
                            Revoked
                          </span>
                        )}
                        {isExpiringSoon && !isExpired && !isRevoked && (
                          <span className="inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400">
                            Expiring soon
                          </span>
                        )}
                      </div>
                      <div className="flex items-center gap-4 text-xs text-slate-500 dark:text-slate-400">
                        <span>Created {formatBackendTimestamp(apiKey.created_at, "MMM d, yyyy 'at' h:mm a")}</span>
                        <span className="text-slate-300 dark:text-slate-700">•</span>
                        <span className={isRevoked ? "text-red-500" : getStatusColor(daysRemaining)}>
                          {isRevoked
                            ? `Revoked${apiKey.revoked_at ? ` ${formatBackendTimestamp(apiKey.revoked_at, "MMM d, yyyy 'at' h:mm a")}` : ""}`
                            : isExpired
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
                        onClick={() => handleToggleActivity(apiKey)}
                        className="h-8 w-8 text-slate-500 hover:text-slate-900 dark:hover:text-slate-100"
                        title="View activity"
                      >
                        {loadingActivity === apiKey.id ? (
                          <Loader2 className="h-4 w-4 animate-spin" />
                        ) : isExpanded ? (
                          <ChevronUp className="h-4 w-4" />
                        ) : (
                          <Activity className="h-4 w-4" />
                        )}
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => handleRotateClick(apiKey)}
                        disabled={rotatingKeyId === apiKey.id || isRevoked || isExpired}
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

                {/* Activity Panel */}
                {isExpanded && (
                  <div className="border-t border-slate-200 dark:border-slate-800 px-4 py-3 space-y-3">
                    {loadingActivity === apiKey.id && !stats ? (
                      <div className="flex items-center justify-center py-4">
                        <Loader2 className="h-4 w-4 animate-spin text-slate-400" />
                      </div>
                    ) : stats && stats.total_requests > 0 ? (
                      <>
                        {/* Stats summary */}
                        <div className="flex items-center gap-6 text-xs text-slate-600 dark:text-slate-400">
                          <span>
                            <span className="font-medium text-slate-900 dark:text-slate-100">{stats.total_requests}</span> request{stats.total_requests === 1 ? "" : "s"}
                          </span>
                          <span>
                            <span className="font-medium text-slate-900 dark:text-slate-100">{stats.unique_ips}</span> unique IP{stats.unique_ips === 1 ? "" : "s"}
                          </span>
                          {stats.last_used && (
                            <span>
                              Last used {formatBackendTimestamp(stats.last_used, "MMM d, yyyy HH:mm")}
                            </span>
                          )}
                        </div>

                        {/* Log entries */}
                        {logs.length > 0 && (
                          <div className="overflow-x-auto">
                            <table className="w-full text-xs">
                              <thead>
                                <tr className="text-left text-slate-500 dark:text-slate-400 border-b border-slate-100 dark:border-slate-800">
                                  <th className="pb-2 pr-4 font-medium">Timestamp</th>
                                  <th className="pb-2 pr-4 font-medium">Endpoint</th>
                                  <th className="pb-2 pr-4 font-medium">IP</th>
                                  <th className="pb-2 font-medium">User Agent</th>
                                </tr>
                              </thead>
                              <tbody>
                                {logs.map((log) => (
                                  <tr key={log.id} className="border-b border-slate-50 dark:border-slate-800/50">
                                    <td className="py-1.5 pr-4 text-slate-600 dark:text-slate-400 whitespace-nowrap">
                                      {formatBackendTimestamp(log.timestamp, "MMM d HH:mm:ss")}
                                    </td>
                                    <td className="py-1.5 pr-4 font-mono text-slate-700 dark:text-slate-300">
                                      {truncate(log.endpoint, 40)}
                                    </td>
                                    <td className="py-1.5 pr-4 font-mono text-slate-600 dark:text-slate-400">
                                      {log.ip_address}
                                    </td>
                                    <td className="py-1.5 text-slate-500 dark:text-slate-500">
                                      {truncate(log.user_agent, 50)}
                                    </td>
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                          </div>
                        )}

                        {/* Load more */}
                        {usageLogsHasMore[apiKey.id] && (
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => handleLoadMoreLogs(apiKey.id)}
                            disabled={loadingActivity === apiKey.id}
                            className="text-xs"
                          >
                            {loadingActivity === apiKey.id ? (
                              <Loader2 className="h-3 w-3 animate-spin mr-1" />
                            ) : (
                              <ChevronDown className="h-3 w-3 mr-1" />
                            )}
                            Load more
                          </Button>
                        )}
                      </>
                    ) : (
                      <p className="text-xs text-slate-500 dark:text-slate-400 py-2">
                        No activity recorded yet
                      </p>
                    )}
                  </div>
                )}
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
          </DialogHeader>

          <div className="py-6 space-y-4">
            <div className="space-y-2">
              <label className="text-sm font-medium text-slate-700 dark:text-slate-300">
                Description (optional)
              </label>
              <Input
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="e.g. Production backend, CI pipeline"
                maxLength={255}
                className="text-sm"
              />
              <span className="text-xs text-slate-400">{description.length}/255</span>
            </div>

            <div className="space-y-2">
              <label className="text-sm font-medium text-slate-700 dark:text-slate-300">
                Choose how long this key should remain valid
              </label>
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
              {keyToDelete.description && (
                <p className="text-sm font-medium mb-1">{keyToDelete.description}</p>
              )}
              <code className="text-sm font-mono">
                {displayKeyPrefix(keyToDelete)}
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

      {/* Rotate Confirmation Dialog */}
      <Dialog open={rotateDialogOpen} onOpenChange={setRotateDialogOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Rotate API key</DialogTitle>
            <DialogDescription>
              A new key will be created and the current key will be immediately revoked.
              Make sure your integrations are ready to use the new key.
            </DialogDescription>
          </DialogHeader>

          {keyToRotate && (
            <div className="my-4 rounded-lg border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-900/50 p-3">
              {keyToRotate.description && (
                <p className="text-sm font-medium mb-1">{keyToRotate.description}</p>
              )}
              <code className="text-sm font-mono">
                {displayKeyPrefix(keyToRotate)}
              </code>
            </div>
          )}

          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setRotateDialogOpen(false)}
            >
              Cancel
            </Button>
            <Button
              onClick={handleConfirmRotate}
              className="bg-slate-800 hover:bg-slate-700 dark:bg-slate-200 dark:hover:bg-slate-300 text-slate-50 dark:text-slate-900"
            >
              <RotateCw className="mr-2 h-4 w-4" />
              Rotate key
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
