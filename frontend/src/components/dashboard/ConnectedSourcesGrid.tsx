import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Settings2 } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { getAppIconUrl } from "@/lib/utils/icons";

const mockSources = [
  { id: "1", name: "Notion", type: "notion", status: "active", lastSync: "2h ago" },
  { id: "2", name: "Slack", type: "slack", status: "active", lastSync: "1h ago" },
  { id: "3", name: "Google Drive", type: "google_drive", status: "active", lastSync: "30m ago" },
];

export function ConnectedSourcesGrid() {
  const navigate = useNavigate();

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between">
        <CardTitle>Connected Sources</CardTitle>
        <Button 
          variant="outline" 
          size="sm"
          onClick={() => navigate("/sources")}
        >
          <Settings2 className="mr-2 h-4 w-4" />
          Configure Sources
        </Button>
      </CardHeader>
      <CardContent>
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {mockSources.map((source) => (
            <div
              key={source.id}
              className="flex items-center space-x-4 rounded-lg border p-4"
            >
              <img
                src={getAppIconUrl(source.type)}
                alt={source.name}
                className="h-8 w-8"
              />
              <div className="flex-1 space-y-1">
                <p className="text-sm font-medium leading-none">{source.name}</p>
                <p className="text-sm text-muted-foreground">
                  Last sync: {source.lastSync}
                </p>
              </div>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}