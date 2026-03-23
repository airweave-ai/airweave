import { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Key, Plus } from "lucide-react";
import { toast } from "sonner";
import { useAPIKeysStore } from "@/lib/stores/apiKeys";
import { useOrganizationContext } from "@/hooks/use-organization-context";

export const ApiKeyCard = () => {
  const { canManageOrganization } = useOrganizationContext();
  const canManage = canManageOrganization();
  const [isCreating, setIsCreating] = useState(false);

  const {
    apiKeys,
    isLoading,
    fetchAPIKeys,
    createAPIKey
  } = useAPIKeysStore();

  useEffect(() => {
    if (canManage) {
      fetchAPIKeys();
    }
  }, [canManage, fetchAPIKeys]);

  const handleCreateAPIKey = async () => {
    setIsCreating(true);
    try {
      await createAPIKey();
      toast.success("API key created successfully");
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : "Failed to create API key";
      toast.error(errorMessage);
    } finally {
      setIsCreating(false);
    }
  };

  const displayPrefix = (prefix: string | null) => {
    if (!prefix) return "????????" + "****".repeat(6);
    return prefix + "****".repeat(6);
  };

  // Get the most recent API key
  const latestApiKey = apiKeys.length > 0 ? apiKeys[0] : null;

  return (
    <div className="bg-card border border-border rounded-lg overflow-hidden shadow-sm">
      <div className="p-5">
        <div className="flex items-center mb-1">
          <Key className="h-4 w-4 mr-1.5 text-muted-foreground" />
          <h3 className="text-sm font-medium">API Key</h3>
        </div>
        <p className="text-xs text-muted-foreground mb-4">Store your API keys securely</p>

        {!canManage ? (
          <div className="text-center py-2">
            <p className="text-xs text-muted-foreground">
              Only admins and owners can manage API keys
            </p>
          </div>
        ) : isLoading ? (
          <div className="flex items-center justify-center py-4">
            <div className="text-xs text-muted-foreground">Loading...</div>
          </div>
        ) : latestApiKey ? (
          <>
            <div className="flex items-center">
              <Input
                value={displayPrefix(latestApiKey.key_prefix)}
                className="text-xs font-mono h-9 bg-background border-border"
                readOnly
              />
            </div>
            <div className="mt-2 text-right">
              <Link
                to="/api-keys"
                className="text-xs text-primary hover:underline"
              >
                Need another API key?
              </Link>
            </div>
          </>
        ) : (
          <div className="text-center py-2">
            <p className="text-xs text-muted-foreground mb-3">No API keys yet</p>
            <Button
              size="sm"
              onClick={handleCreateAPIKey}
              disabled={isCreating}
              className="h-8 px-3 text-xs"
            >
              {isCreating ? (
                "Creating..."
              ) : (
                <>
                  <Plus className="h-3 w-3 mr-1" />
                  Create your first API key
                </>
              )}
            </Button>
          </div>
        )}
      </div>
    </div>
  );
};

export default ApiKeyCard;
