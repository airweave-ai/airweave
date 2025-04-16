import { useState } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Building2, Key, Copy, Eye, EyeOff } from "lucide-react";
import { toast } from "sonner";

interface ApiKey {
  id: string;
  name: string;
  key: string;
  createdAt: string;
}

export function OrganizationSettings() {
  const [apiKeys, setApiKeys] = useState<ApiKey[]>([
    {
      id: "1",
      name: "Production API Key",
      key: "sk_live_123456789abcdef",
      createdAt: "2024-01-01",
    },
  ]);
  const [showKey, setShowKey] = useState<Record<string, boolean>>({});
  const [newKeyName, setNewKeyName] = useState("");

  const handleCreateApiKey = () => {
    if (!newKeyName.trim()) {
      toast.error("Please enter a name for the API key");
      return;
    }

    const newKey: ApiKey = {
      id: Math.random().toString(36).substring(7),
      name: newKeyName,
      key: `sk_live_${Math.random().toString(36).substring(2)}`,
      createdAt: new Date().toISOString(),
    };

    setApiKeys([...apiKeys, newKey]);
    setNewKeyName("");
    toast.success("API key created successfully");
  };

  const handleCopyKey = (key: string) => {
    navigator.clipboard.writeText(key);
    toast.success("API key copied to clipboard");
  };

  const handleDeleteKey = (id: string) => {
    setApiKeys(apiKeys.filter((key) => key.id !== id));
    toast.success("API key deleted successfully");
  };

  const toggleKeyVisibility = (id: string) => {
    setShowKey((prev) => ({ ...prev, [id]: !prev[id] }));
  };

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <Building2 className="h-5 w-5 text-primary" />
            <CardTitle>Organization Details</CardTitle>
          </div>
          <CardDescription>
            Manage your organization settings and preferences
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          <div className="space-y-2">
            <Label>Organization Name</Label>
            <Input defaultValue="Acme Corp" />
          </div>
          <div className="space-y-2">
            <Label>Organization ID</Label>
            <Input value="org_1234567890" disabled />
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <Key className="h-5 w-5 text-primary" />
            <CardTitle>API Keys</CardTitle>
          </div>
          <CardDescription>
            Manage your API keys for authentication
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          <div className="space-y-4">
            <div className="flex gap-2">
              <Input
                placeholder="Enter API key name"
                value={newKeyName}
                onChange={(e) => setNewKeyName(e.target.value)}
              />
              <Button onClick={handleCreateApiKey}>Create New Key</Button>
            </div>

            <div className="space-y-4">
              {apiKeys.map((apiKey) => (
                <div
                  key={apiKey.id}
                  className="flex flex-col gap-2 p-4 border rounded-lg"
                >
                  <div className="flex items-center justify-between">
                    <div>
                      <h3 className="font-medium">{apiKey.name}</h3>
                      <p className="text-sm text-muted-foreground">
                        Created on {new Date(apiKey.createdAt).toLocaleDateString()}
                      </p>
                    </div>
                    <Button
                      variant="destructive"
                      size="sm"
                      onClick={() => handleDeleteKey(apiKey.id)}
                    >
                      Delete
                    </Button>
                  </div>
                  <div className="flex items-center gap-2">
                    <Input
                      type={showKey[apiKey.id] ? "text" : "password"}
                      value={apiKey.key}
                      readOnly
                      className="font-mono"
                    />
                    <Button
                      variant="outline"
                      size="icon"
                      onClick={() => toggleKeyVisibility(apiKey.id)}
                    >
                      {showKey[apiKey.id] ? (
                        <EyeOff className="h-4 w-4" />
                      ) : (
                        <Eye className="h-4 w-4" />
                      )}
                    </Button>
                    <Button
                      variant="outline"
                      size="icon"
                      onClick={() => handleCopyKey(apiKey.key)}
                    >
                      <Copy className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
