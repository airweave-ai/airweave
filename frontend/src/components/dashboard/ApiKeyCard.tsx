import { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Check, Copy, Key, Plus } from "lucide-react";
import { toast } from "sonner";
import { useAPIKeysStore } from "@/lib/stores/apiKeys";

export const ApiKeyCard = () => {
  const [copySuccess, setCopySuccess] = useState(false);
  const [isCreating, setIsCreating] = useState(false);

  const {
    apiKeys,
    isLoading,
    fetchAPIKeys,
    createAPIKey
  } = useAPIKeysStore();

  useEffect(() => {
    fetchAPIKeys();
  }, [fetchAPIKeys]);

  const handleCopyApiKey = (key: string) => {
    if (key) {
      navigator.clipboard.writeText(key);
      setCopySuccess(true);
      toast.success("API key copied to clipboard");
      setTimeout(() => setCopySuccess(false), 2000);
    }
  };

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

  const maskApiKey = (key: string) => {
    if (!key) return "";
    const firstFour = key.substring(0, 4);
    const masked = Array(key.length - 4).fill("*").join("");
    return `${firstFour}${masked}`;
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

        {isLoading ? (
          <div className="flex items-center justify-center py-4">
            <div className="text-xs text-muted-foreground">Loading...</div>
          </div>
        ) : latestApiKey ? (
          <>
            <div className="flex items-center">
              <Input
                value={maskApiKey(latestApiKey.decrypted_key)}
                className="text-xs font-mono h-9 bg-background border-border"
                readOnly
              />
              <Button
                variant="ghost"
                size="icon"
                className="ml-1 h-9 w-9 relative"
                onClick={() => handleCopyApiKey(latestApiKey.decrypted_key)}
              >
                <div className="relative">
                  <Copy className={`h-3.5 w-3.5 transition-all duration-200 ${copySuccess ? 'opacity-0 scale-75' : 'opacity-100 scale-100'}`} />
                  <Check className={`h-3.5 w-3.5 absolute inset-0 transition-all duration-200 ${copySuccess ? 'opacity-100 scale-100' : 'opacity-0 scale-75'}`} />
                </div>
              </Button>
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
