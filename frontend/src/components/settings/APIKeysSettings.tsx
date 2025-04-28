import { useState, useEffect } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Key, Copy, Loader2, AlertCircle, Clock, CalendarIcon, CheckCircle, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { format, differenceInDays } from "date-fns";
import { apiClient } from "@/lib/api";

interface APIKey {
  id: string;
  key_prefix: string;
  created_at: string;
  last_used_date: string | null;
  expiration_date: string;
  plain_key?: string;
}

export function APIKeysSettings() {
  const [apiKeys, setApiKeys] = useState<APIKey[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const [newlyCreatedKey, setNewlyCreatedKey] = useState<APIKey | null>(null);
  const [copySuccess, setCopySuccess] = useState<string | null>(null);

  useEffect(() => {
    fetchApiKeys();
  }, []);

  const fetchApiKeys = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await apiClient.get<APIKey[]>("/api-keys");

      if (!response.ok) {
        throw new Error(`API request failed with status ${response.status}`);
      }

      const data = await response.json();
      setApiKeys(Array.isArray(data) ? data : []);
    } catch (err) {
      console.error("Failed to fetch API keys:", err);
      setError(typeof err === 'object' && err !== null && 'message' in err
        ? String(err.message)
        : "Failed to load API keys. Please try again later.");
    } finally {
      setLoading(false);
    }
  };

  const handleCreateApiKey = async () => {
    setCreating(true);
    setError(null);

    try {
      // Create API key with default expiration (backend will handle this)
      const response = await apiClient.post<APIKey>("/api-keys", {});

      if (!response.ok) {
        throw new Error(`API request failed with status ${response.status}`);
      }

      const newKey = await response.json();

      if (!newKey || typeof newKey !== 'object' || !('id' in newKey)) {
        throw new Error("Invalid response from server");
      }

      setNewlyCreatedKey(newKey as APIKey);

      // Add to list but don't show the plain key in regular list
      const keyForList = { ...newKey } as APIKey;
      delete keyForList.plain_key;
      setApiKeys([keyForList, ...apiKeys]);

      toast.success("API key created successfully");
    } catch (err) {
      console.error("Failed to create API key:", err);
      setError(typeof err === 'object' && err !== null && 'message' in err
        ? String(err.message)
        : "Failed to create API key. Please try again.");
      toast.error(typeof err === 'object' && err !== null && 'message' in err
        ? String(err.message)
        : "Failed to create API key. Please try again.");
    } finally {
      setCreating(false);
    }
  };

  const handleCopyKey = (key: string) => {
    navigator.clipboard.writeText(key).then(
      () => {
        setCopySuccess(key);
        toast.success("API key copied to clipboard");
        setTimeout(() => setCopySuccess(null), 2000);
      },
      () => {
        toast.error("Failed to copy API key");
      }
    );
  };

  const handleDeleteKey = async (id: string) => {
    try {
      const response = await apiClient.delete("/api-keys", { id });

      if (!response.ok) {
        throw new Error(`API request failed with status ${response.status}`);
      }

      setApiKeys(apiKeys.filter((key) => key.id !== id));
      toast.success("API key deleted successfully");

      // If we just deleted the newly created key, clear that state
      if (newlyCreatedKey && newlyCreatedKey.id === id) {
        setNewlyCreatedKey(null);
      }
    } catch (err) {
      console.error("Failed to delete API key:", err);
      toast.error(typeof err === 'object' && err !== null && 'message' in err
        ? String(err.message)
        : "Failed to delete API key. Please try again.");
    }
  };

  const formatDate = (dateString: string, includeRelative: boolean = false) => {
    try {
      const date = new Date(dateString);
      if (isNaN(date.getTime())) return "Invalid date";

      const formattedDate = format(date, "PPP");

      if (includeRelative) {
        const now = new Date();
        const daysRemaining = differenceInDays(date, now);

        if (daysRemaining < 0) {
          return `${formattedDate} (Expired)`;
        } else if (daysRemaining === 0) {
          return `${formattedDate} (Today)`;
        } else if (daysRemaining === 1) {
          return `${formattedDate} (Tomorrow)`;
        } else {
          return `${formattedDate} (${daysRemaining} days remaining)`;
        }
      }

      return formattedDate;
    } catch (e) {
      console.error("Error formatting date:", e);
      return "Invalid date";
    }
  };

  const getExpirationStatus = (expirationDate: string) => {
    try {
      const date = new Date(expirationDate);
      const now = new Date();
      const daysRemaining = differenceInDays(date, now);

      if (daysRemaining < 0) {
        return { variant: "destructive", label: "Expired" };
      } else if (daysRemaining <= 7) {
        return { variant: "secondary", label: "Expiring soon" };
      } else {
        return { variant: "success", label: "Active" };
      }
    } catch (e) {
      return { variant: "outline", label: "Unknown" };
    }
  };

  return (
    <div className="space-y-6">
      <Card className="border-0 shadow-none bg-transparent">
        <CardHeader className="px-0 pt-0">
          <div className="flex items-center gap-2">
            <Key className="h-5 w-5 text-primary" />
            <CardTitle>API Keys</CardTitle>
          </div>
          <CardDescription>
            Create and manage API keys for authenticating with the Airweave API
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6 px-0">
          {/* Create new API key section */}
          <div className="pb-6 border-b border-border flex flex-col sm:flex-row sm:items-end justify-between gap-4">
            <div className="space-y-2">
              <h3 className="text-sm font-medium">Create New API Key</h3>
              <p className="text-xs text-muted-foreground">
                API keys will expire 180 days after creation
              </p>
            </div>
            <Button
              onClick={handleCreateApiKey}
              disabled={creating}
              size="sm"
              className="w-full sm:w-auto"
            >
              {creating ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Creating...
                </>
              ) : (
                <>
                  <Key className="mr-2 h-4 w-4" />
                  Create New Key
                </>
              )}
            </Button>
          </div>

          {/* Newly created key alert */}
          {newlyCreatedKey && newlyCreatedKey.plain_key && (
            <div className="my-4 rounded-lg border bg-primary/5 border-primary/20 p-4">
              <div className="flex items-start gap-3">
                <div className="p-2 rounded-full bg-primary/10">
                  <Key className="h-5 w-5 text-primary" />
                </div>
                <div className="space-y-4 flex-1">
                  <div>
                    <h4 className="font-medium mb-1">Your new API key has been created</h4>
                    <p className="text-sm text-muted-foreground">Copy this key now. You won't be able to see it again!</p>
                  </div>

                  <div className="flex items-stretch gap-2 mt-2">
                    <Input
                      type="text"
                      value={newlyCreatedKey.plain_key}
                      readOnly
                      className="font-mono bg-background border-primary/20 text-sm h-9"
                    />
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => handleCopyKey(newlyCreatedKey.plain_key || "")}
                      className="border-primary/20 hover:bg-primary/10 hover:text-primary"
                    >
                      {copySuccess === newlyCreatedKey.plain_key ? (
                        <CheckCircle className="h-4 w-4" />
                      ) : (
                        <Copy className="h-4 w-4" />
                      )}
                    </Button>
                  </div>

                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => setNewlyCreatedKey(null)}
                    className="mt-2"
                  >
                    I've saved the key
                  </Button>
                </div>
              </div>
            </div>
          )}

          {/* Error state */}
          {error && (
            <Alert variant="destructive" className="mb-4">
              <AlertCircle className="h-4 w-4" />
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}

          {/* Loading state */}
          {loading ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
            </div>
          ) : (
            <>
              {/* API Keys list */}
              <div className="space-y-4">
                <h3 className="text-sm font-medium">Your API Keys</h3>
                {apiKeys.length === 0 ? (
                  <div className="rounded-lg border border-dashed p-8 text-center">
                    <Key className="mx-auto h-8 w-8 text-muted-foreground opacity-50" />
                    <h3 className="mt-2 text-sm font-medium">No API keys</h3>
                    <p className="mt-1 text-sm text-muted-foreground">
                      You don't have any API keys yet. Create one to get started.
                    </p>
                  </div>
                ) : (
                  <div className="grid gap-3">
                    {apiKeys.map((apiKey) => {
                      const status = getExpirationStatus(apiKey.expiration_date);

                      return (
                        <div
                          key={apiKey.id}
                          className="group flex flex-col gap-4 p-4 border rounded-lg bg-card hover:border-primary/30 hover:bg-accent/50 transition-all duration-200"
                        >
                          <div className="flex-1 space-y-3">
                            <div className="flex items-start justify-between gap-2">
                              <div className="flex items-center gap-3">
                                <div className="p-1.5 rounded-full bg-primary/10">
                                  <Key className="h-4 w-4 text-primary" />
                                </div>
                                <div>
                                  <div className="flex items-center gap-2">
                                    <h4 className="font-medium text-sm">
                                      {apiKey.key_prefix}...
                                    </h4>
                                  </div>
                                </div>
                              </div>
                              <div className="flex items-center gap-2">
                                <Badge variant={status.variant as any} className="text-[10px] px-1.5 py-0">
                                  {status.label}
                                </Badge>
                                <Button
                                  variant="ghost"
                                  size="icon"
                                  className="text-muted-foreground hover:text-destructive h-7 w-7 opacity-60 group-hover:opacity-100"
                                  onClick={() => handleDeleteKey(apiKey.id)}
                                >
                                  <Trash2 className="h-4 w-4" />
                                </Button>
                              </div>
                            </div>
                            <div className="flex justify-between items-end">
                              <div className="text-xs text-muted-foreground space-y-1">
                                <div className="flex items-center gap-1.5">
                                  <CalendarIcon className="h-3 w-3" />
                                  <span>Created: {formatDate(apiKey.created_at)}</span>
                                </div>
                                {apiKey.last_used_date && (
                                  <div className="flex items-center gap-1.5">
                                    <CalendarIcon className="h-3 w-3" />
                                    <span>Last used: {formatDate(apiKey.last_used_date)}</span>
                                  </div>
                                )}
                              </div>
                              <div className="text-xs text-muted-foreground flex items-center gap-1.5">
                                <Clock className="h-3 w-3" />
                                <span>Expires: {formatDate(apiKey.expiration_date, true)}</span>
                              </div>
                            </div>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            </>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
