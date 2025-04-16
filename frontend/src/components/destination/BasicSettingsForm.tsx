import { Input } from "@/components/ui/input";
import { toast } from "sonner";

interface BasicSettingsFormProps {
  name: string;
  url?: string;
  apiKey?: string;
  requiresUrl?: boolean;
  onConfigChange: (config: { name: string; url?: string; apiKey?: string }) => void;
}

export function BasicSettingsForm({
  name,
  url,
  apiKey,
  requiresUrl,
  onConfigChange
}: BasicSettingsFormProps) {
  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <label className="text-sm font-medium">Name</label>
        <Input
          placeholder="Production Database"
          value={name}
          onChange={(e) =>
            onConfigChange({ name: e.target.value, url, apiKey })
          }
        />
      </div>
      {requiresUrl && (
        <div className="space-y-2">
          <label className="text-sm font-medium">URL</label>
          <Input
            type="url"
            placeholder="https://your-instance.example.com"
            value={url}
            onChange={(e) =>
              onConfigChange({ name, url: e.target.value, apiKey })
            }
          />
        </div>
      )}
      <div className="space-y-2">
        <label className="text-sm font-medium">API Key</label>
        <Input
          type="password"
          placeholder="Enter your API key"
          value={apiKey}
          onChange={(e) =>
            onConfigChange({ name, url, apiKey: e.target.value })
          }
        />
      </div>
    </div>
  );
}
