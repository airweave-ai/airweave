import { useEffect } from "react";
import { Link } from "react-router-dom";
import { Key, AlertTriangle } from "lucide-react";
import { differenceInDays } from "date-fns";
import { useAPIKeysStore } from "@/lib/stores/apiKeys";
import { useOrganizationContext } from "@/hooks/use-organization-context";

export const ApiKeyCard = () => {
  const { canManageOrganization } = useOrganizationContext();
  const canManage = canManageOrganization();
  const { apiKeys, isLoading, fetchAPIKeys } = useAPIKeysStore();

  useEffect(() => {
    if (canManage) {
      fetchAPIKeys();
    }
  }, [canManage, fetchAPIKeys]);

  const activeKeys = apiKeys.filter((k) => k.status === "active");
  const expiringSoon = activeKeys.some((k) => {
    try {
      return differenceInDays(new Date(k.expiration_date), new Date()) <= 14;
    } catch {
      return false;
    }
  });

  return (
    <div className="bg-card border border-border rounded-lg overflow-hidden shadow-sm">
      <div className="p-5">
        <div className="flex items-center mb-1">
          <Key className="h-4 w-4 mr-1.5 text-muted-foreground" />
          <h3 className="text-sm font-medium">API Keys</h3>
        </div>
        <p className="text-xs text-muted-foreground mb-4">Manage access tokens for the API</p>

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
        ) : activeKeys.length > 0 ? (
          <div className="space-y-3">
            <p className="text-sm font-medium">
              {activeKeys.length} active key{activeKeys.length === 1 ? "" : "s"}
            </p>
            {expiringSoon && (
              <div className="flex items-center gap-1.5 text-amber-600 dark:text-amber-400">
                <AlertTriangle className="h-3.5 w-3.5" />
                <span className="text-xs font-medium">Expiring soon</span>
              </div>
            )}
          </div>
        ) : (
          <p className="text-xs text-muted-foreground">No API keys yet</p>
        )}

        <div className="mt-3">
          <Link
            to="/api-keys"
            className="text-xs text-primary hover:underline"
          >
            Manage API keys
          </Link>
        </div>
      </div>
    </div>
  );
};

export default ApiKeyCard;
