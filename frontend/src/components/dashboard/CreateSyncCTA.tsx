import { Button } from "@/components/ui/button";
import { useNavigate } from "react-router-dom";
import { Plus, RefreshCw } from "lucide-react";

export function CreateSyncCTA() {
  const navigate = useNavigate();

  const handleCreateSync = () => {
    navigate("/sync/create");
  };

  return (
    <div className="p-6 border rounded-lg bg-card text-card-foreground shadow-sm">
      <div className="flex flex-col items-center text-center space-y-4">
        <div className="rounded-full p-3 bg-primary/10">
          <RefreshCw className="h-6 w-6 text-primary" />
        </div>
        <h3 className="text-xl font-semibold">Create Your First Sync</h3>
        <p className="text-muted-foreground">
          Start by connecting a source to make your data searchable.
        </p>
        <Button onClick={handleCreateSync} className="mt-2">
          <Plus className="mr-2 h-4 w-4" />
          Create Sync
        </Button>
      </div>
    </div>
  );
}
