import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { createFileRoute } from "@tanstack/react-router";
import { CheckCircle2, Copy, Key, Loader2, Trash2 } from "lucide-react";
import { useState } from "react";

import {
  AlertDialog,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { useRightSidebarContent } from "@/components/ui/right-sidebar";
import { DocsContent } from "@/hooks/use-docs-content";
import { deleteApiKey, fetchApiKeys, type APIKey } from "@/lib/api";
import { useAuth0 } from "@/lib/auth-provider";

export const Route = createFileRoute("/api-keys")({ component: ApiKeysPage });

// Helper functions
function maskKey(key: string): string {
  if (!key || key.length < 8) return key;
  return `${key.substring(0, 8)}${"•".repeat(32)}`;
}

function getDaysRemaining(expirationDate: string): number {
  try {
    const expDate = new Date(expirationDate);
    const now = new Date();
    const diffTime = expDate.getTime() - now.getTime();
    return Math.ceil(diffTime / (1000 * 60 * 60 * 24));
  } catch {
    return 0;
  }
}

function getStatusColor(daysRemaining: number): string {
  if (daysRemaining < 0) return "text-red-500";
  if (daysRemaining <= 7) return "text-amber-500";
  return "text-muted-foreground";
}

function formatDate(dateString: string): string {
  try {
    return new Date(dateString).toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
      year: "numeric",
    });
  } catch {
    return dateString;
  }
}

function ApiKeysDocs() {
  return <DocsContent docPath="quickstart.mdx" />;
}

function ApiKeysCode() {
  return (
    <div className="space-y-4">
      <h3 className="font-semibold text-base">Using API Keys</h3>
      <p className="text-sm text-muted-foreground">
        Authenticate your requests with your API key:
      </p>
      <pre className="bg-muted p-3 rounded-lg text-xs overflow-auto">
        <code>{`import { AirweaveSDK } from '@airweave/sdk';

const client = new AirweaveSDK({
  apiKey: 'YOUR_API_KEY',
  baseUrl: 'https://api.airweave.ai'
});

// Or use directly in headers
fetch('https://api.airweave.ai/collections', {
  headers: {
    'x-api-key': 'YOUR_API_KEY'
  }
});`}</code>
      </pre>
    </div>
  );
}

function ApiKeysHelp() {
  return (
    <div className="space-y-4">
      <h3 className="font-semibold text-base">API Key Security</h3>
      <p className="text-sm text-muted-foreground">
        Keep your API keys secure and never expose them in client-side code.
      </p>
      <div className="space-y-3">
        <div className="p-3 bg-muted rounded-lg">
          <h4 className="font-medium text-sm">Best Practices</h4>
          <ul className="text-xs text-muted-foreground mt-1 space-y-1">
            <li>Store keys in environment variables</li>
            <li>Rotate keys periodically</li>
            <li>Use different keys for dev/prod</li>
          </ul>
        </div>
      </div>
    </div>
  );
}

function ApiKeyItem({
  apiKey,
  onDeleteClick,
}: {
  apiKey: APIKey;
  onDeleteClick: (apiKey: APIKey) => void;
}) {
  const [copiedKey, setCopiedKey] = useState<string | null>(null);

  const daysRemaining = getDaysRemaining(apiKey.expiration_date);
  const isExpired = daysRemaining < 0;
  const isExpiringSoon = daysRemaining >= 0 && daysRemaining <= 7;

  const handleCopyKey = (key: string) => {
    navigator.clipboard.writeText(key).then(
      () => {
        setCopiedKey(key);
        setTimeout(() => setCopiedKey(null), 2000);
      },
      () => {
        console.error("Failed to copy key");
      },
    );
  };

  return (
    <div
      className={`rounded-lg border bg-card ${
        isExpired ? "border-red-200 dark:border-red-900/50" : ""
      }`}
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
            <div className="flex items-center gap-4 text-xs text-muted-foreground">
              <span>Created {formatDate(apiKey.created_at)}</span>
              <span className="text-muted-foreground/50">•</span>
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
              className="size-8"
              title="Copy key"
            >
              {copiedKey === apiKey.decrypted_key ? (
                <CheckCircle2 className="size-4" />
              ) : (
                <Copy className="size-4" />
              )}
            </Button>
            <Button
              variant="ghost"
              size="icon"
              onClick={() => onDeleteClick(apiKey)}
              className="size-8 text-muted-foreground hover:text-red-600 dark:hover:text-red-500"
              title="Delete key"
            >
              <Trash2 className="size-4" />
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}

function ApiKeysPage() {
  const { getAccessTokenSilently } = useAuth0();
  const queryClient = useQueryClient();
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [keyToDelete, setKeyToDelete] = useState<APIKey | null>(null);

  useRightSidebarContent({
    docs: <ApiKeysDocs />,
    code: <ApiKeysCode />,
    help: <ApiKeysHelp />,
  });

  const {
    data: apiKeys,
    isLoading,
    error,
  } = useQuery({
    queryKey: ["api-keys"],
    queryFn: async () => {
      const token = await getAccessTokenSilently();
      return fetchApiKeys(token);
    },
  });

  const deleteMutation = useMutation({
    mutationFn: async (keyId: string) => {
      const token = await getAccessTokenSilently();
      return deleteApiKey(token, keyId);
    },
    onMutate: async (keyId) => {
      // Cancel any outgoing refetches
      await queryClient.cancelQueries({ queryKey: ["api-keys"] });

      // Snapshot the previous value
      const previousKeys = queryClient.getQueryData<APIKey[]>(["api-keys"]);

      // Optimistically update to the new value
      queryClient.setQueryData<APIKey[]>(["api-keys"], (old) =>
        old?.filter((key) => key.id !== keyId),
      );

      // Close dialog immediately for better UX
      setDeleteDialogOpen(false);
      setKeyToDelete(null);

      // Return a context object with the snapshotted value
      return { previousKeys };
    },
    onError: (_err, _keyId, context) => {
      // If the mutation fails, use the context returned from onMutate to roll back
      if (context?.previousKeys) {
        queryClient.setQueryData(["api-keys"], context.previousKeys);
      }
    },
    onSettled: () => {
      // Always refetch after error or success to ensure sync with server
      queryClient.invalidateQueries({ queryKey: ["api-keys"] });
    },
  });

  const handleDeleteClick = (apiKey: APIKey) => {
    setKeyToDelete(apiKey);
    setDeleteDialogOpen(true);
  };

  const handleConfirmDelete = () => {
    if (keyToDelete) {
      deleteMutation.mutate(keyToDelete.id);
    }
  };

  // Loading state
  if (isLoading) {
    return (
      <div className="p-6">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-2xl font-bold">API Keys</h1>
            <p className="text-muted-foreground">
              Manage your API keys for programmatic access
            </p>
          </div>
        </div>
        <div className="flex items-center justify-center py-20">
          <Loader2 className="size-6 animate-spin text-muted-foreground" />
        </div>
      </div>
    );
  }

  // Error state
  if (error) {
    return (
      <div className="p-6">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-2xl font-bold">API Keys</h1>
            <p className="text-muted-foreground">
              Manage your API keys for programmatic access
            </p>
          </div>
        </div>
        <div className="rounded-lg border border-red-200 dark:border-red-900/50 bg-red-50 dark:bg-red-900/10 px-4 py-3 text-sm text-red-600 dark:text-red-400">
          {error instanceof Error ? error.message : "Failed to load API keys"}
        </div>
      </div>
    );
  }

  // Empty state
  if (!apiKeys || apiKeys.length === 0) {
    return (
      <div className="p-6">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-2xl font-bold">API Keys</h1>
            <p className="text-muted-foreground">
              Manage your API keys for programmatic access
            </p>
          </div>
        </div>
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          <Card className="border-dashed">
            <CardHeader className="text-center">
              <div className="mx-auto size-12 rounded-full bg-muted flex items-center justify-center mb-2">
                <Key className="size-6 text-muted-foreground" />
              </div>
              <CardTitle className="text-lg">No API keys yet</CardTitle>
              <CardDescription>
                Create your first key to start using the API programmatically.
              </CardDescription>
            </CardHeader>
            <CardContent className="text-center">
              <p className="text-sm text-muted-foreground">
                API key creation coming soon
              </p>
            </CardContent>
          </Card>
        </div>
      </div>
    );
  }

  // Keys list
  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold">API Keys</h1>
          <p className="text-muted-foreground">
            Manage your API keys for programmatic access
          </p>
        </div>
      </div>

      <div className="space-y-3">
        {apiKeys.map((apiKey) => (
          <ApiKeyItem
            key={apiKey.id}
            apiKey={apiKey}
            onDeleteClick={handleDeleteClick}
          />
        ))}
      </div>

      {/* Delete Confirmation Dialog */}
      <AlertDialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <AlertDialogContent className="sm:max-w-md">
          <AlertDialogHeader>
            <AlertDialogTitle>Delete API key</AlertDialogTitle>
            <AlertDialogDescription>
              This action cannot be undone. Any applications using this key will
              lose access immediately.
            </AlertDialogDescription>
          </AlertDialogHeader>

          {keyToDelete && (
            <div className="my-4 rounded-lg border bg-muted p-3">
              <code className="text-sm font-mono">
                {maskKey(keyToDelete.decrypted_key)}
              </code>
            </div>
          )}

          <AlertDialogFooter>
            <Button
              variant="outline"
              onClick={() => setDeleteDialogOpen(false)}
              disabled={deleteMutation.isPending}
            >
              Cancel
            </Button>
            <Button
              variant="destructive"
              onClick={handleConfirmDelete}
              disabled={deleteMutation.isPending}
            >
              {deleteMutation.isPending ? (
                <>
                  <Loader2 className="mr-2 size-4 animate-spin" />
                  Deleting...
                </>
              ) : (
                <>
                  <Trash2 className="mr-2 size-4" />
                  Delete key
                </>
              )}
            </Button>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
