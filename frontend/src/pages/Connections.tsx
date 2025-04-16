import { useState } from "react";
import { UnifiedDataSourceGrid } from "@/components/data-sources/UnifiedDataSourceGrid";
import { AddSourceWizard } from "@/components/sync/AddSourceWizard";
import { AsanaDialog } from "@/components/sync/AsanaDialog";
import { Button } from "@/components/ui/button";
import { useToast } from "@/components/ui/use-toast";
import { Plus } from "lucide-react";

const Connections = () => {
  const { toast } = useToast();
  const [refreshKey, setRefreshKey] = useState(0);

  // Function to force a refresh of the connections grid
  const refreshConnections = () => {
    setRefreshKey(prev => prev + 1);
  };

  const handleConnectionComplete = (connectionId: string) => {
    toast({
      title: "Connection Created",
      description: `Successfully created connection with ID: ${connectionId}`,
    });
    refreshConnections();
  };

  return (
    <div className="container mx-auto py-8 space-y-6">
      <div className="flex justify-between items-center">
        <h1 className="text-3xl font-bold tracking-tight">Data Sources</h1>
        <Button variant="outline" size="sm" onClick={refreshConnections}>
          <Plus className="mr-2 h-4 w-4" />
          Refresh Sources
        </Button>
      </div>

      <p className="text-muted-foreground">
        Connect your data sources to sync with your vector database.
      </p>

      <div className="mt-6">
        <UnifiedDataSourceGrid
          key={refreshKey}
          mode="manage"
          renderSourceDialog={(source, options) => {
            // Special handling for Asana connections
            if (source.short_name === "asana") {
              return (
                <AsanaDialog
                  open={options.isOpen}
                  onOpenChange={options.onOpenChange}
                  onComplete={options.onComplete ?
                    (connectionId) => {
                      options.onComplete?.(connectionId);
                      handleConnectionComplete(connectionId);
                    } : undefined
                  }
                  shortName={source.short_name}
                  name={source.name}
                  connections={options.connections}
                />
              );
            }

            // Default handling for other sources
            return (
              <AddSourceWizard
                open={options.isOpen}
                onOpenChange={options.onOpenChange}
                onComplete={options.onComplete ?
                  (connectionId) => {
                    options.onComplete?.(connectionId);
                    handleConnectionComplete(connectionId);
                  } : undefined
                }
                shortName={source.short_name}
                name={source.name}
              />
            );
          }}
        />
      </div>
    </div>
  );
};

export default Connections;
