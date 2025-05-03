import { useEffect, useState } from "react";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Plus } from "lucide-react";
import { DestinationManagementDialog } from "@/components/destination/DestinationManagementDialog";
import { AddDestinationWizard } from "@/components/destination/AddDestinationWizard";
import { toast } from "sonner";
import { getDestinationIconUrl } from "@/lib/utils/icons";
import { apiClient } from "@/lib/api";

interface DestinationDetails {
  name: string;
  description: string;
  short_name: string;
  class_name: string;
  auth_type: string;
  auth_config_class: string;
  id: string;
  created_at: string;
  modified_at: string;
  auth_fields: {
    fields: {
      name: string;
      title: string;
      description: string;
      type: string;
    }[];
  };
}

interface Connection {
  id: string;
  name: string;
  status: string;
  short_name: string;
  integration_type: string;
  integration_credential_id: string;
}

const Destinations = () => {
  const [connections, setConnections] = useState<Connection[]>([]);
  const [destinationDetails, setDestinationDetails] = useState<Record<string, DestinationDetails>>({});
  const [selectedConnection, setSelectedConnection] = useState<Connection | null>(null);
  const [isManageOpen, setIsManageOpen] = useState(false);
  const [isAddOpen, setIsAddOpen] = useState(false);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    fetchConnections();
  }, []);

  const fetchDestinationDetails = async (shortName: string) => {
    try {
      const resp = await apiClient.get(`/destinations/detail/${shortName}`);
      if (!resp.ok) throw new Error("Failed to fetch destination details");
      const data = await resp.json();
      setDestinationDetails(prev => ({ ...prev, [shortName]: data }));
    } catch (error) {
      console.error(`Failed to fetch details for ${shortName}:`, error);
    }
  };

  const fetchConnections = async () => {
    try {
      setIsLoading(true);
      const resp = await apiClient.get("/connections/list/destination");
      if (!resp.ok) throw new Error("Failed to fetch destinations");
      const data = await resp.json();
      setConnections(data);

      // Fetch details for each connection
      data.forEach((conn: Connection) => {
        fetchDestinationDetails(conn.short_name);
      });
    } catch (error) {
      toast.error("Failed to load destinations");
    } finally {
      setIsLoading(false);
    }
  };

  const handleCardClick = (connection: Connection) => {
    setSelectedConnection(connection);
    setIsManageOpen(true);
  };

  const handleAddComplete = () => {
    fetchConnections();
    setIsAddOpen(false);
  };

  const handleManageClose = () => {
    setIsManageOpen(false);
    setSelectedConnection(null);
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    });
  };

  return (
    <div className="container mx-auto py-6 space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold">Vector Databases</h1>
          <p className="text-muted-foreground">
            Manage your vector database connections
          </p>
        </div>
        <Button onClick={() => setIsAddOpen(true)}>
          <Plus className="mr-2 h-4 w-4" /> Add Database
        </Button>
      </div>

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {/* Native Airweave Card */}
        <Card className="relative overflow-hidden">
          <CardHeader>
            <div className="flex items-center justify-between">
              <div className="flex items-center space-x-4">
                <img
                  src={getDestinationIconUrl("weaviate_native")}
                  alt="Airweave icon"
                  className="w-8 h-8"
                />
                <div>
                  <CardTitle>Native Weaviate</CardTitle>
                  <CardDescription>Built-in vector store</CardDescription>
                </div>
              </div>
              <Badge variant="default">Connected</Badge>
            </div>
          </CardHeader>
          <CardContent>
            <div className="grid gap-2 text-sm">
              <div className="flex justify-between">
                <span className="text-muted-foreground">Type</span>
                <span>Airweave-Weaviate</span>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Dynamic Connection Cards */}
        {connections.map((connection) => {
          const details = destinationDetails[connection.short_name];
          return (
            <Card
              key={connection.id}
              className="relative overflow-hidden cursor-pointer hover:shadow-md transition-shadow"
              onClick={() => handleCardClick(connection)}
            >
              <CardHeader>
                <div className="flex items-center justify-between">
                  <div className="flex items-center space-x-4">
                    <img
                      src={getDestinationIconUrl(connection.short_name)}
                      alt={`${connection.name} icon`}
                      className="w-8 h-8"
                    />
                    <div>
                      <CardTitle>{connection.name}</CardTitle>
                      <CardDescription>
                        {details?.description || connection.short_name}
                      </CardDescription>
                    </div>
                  </div>
                  <Badge variant={connection.status === "ACTIVE" ? "default" : "secondary"}>
                    {connection.status.toLowerCase()}
                  </Badge>
                </div>
              </CardHeader>
              <CardContent>
                <div className="grid gap-2 text-sm">
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Type</span>
                    <span className="font-medium">{details?.class_name || connection.integration_type}</span>
                  </div>


                  {details?.created_at && (
                    <div className="flex justify-between pt-2 mt-2">
                      <span className="text-muted-foreground">Created</span>
                      <span className="text-xs text-muted-foreground">
                        {formatDate(details.created_at)}
                      </span>
                    </div>
                  )}
                </div>
              </CardContent>
            </Card>
          );
        })}
      </div>

      {selectedConnection && (
        <DestinationManagementDialog
          open={isManageOpen}
          onOpenChange={handleManageClose}
          connection={selectedConnection}
          onDelete={fetchConnections}
        />
      )}

      <AddDestinationWizard
        open={isAddOpen}
        onOpenChange={setIsAddOpen}
        onComplete={handleAddComplete}
      />
    </div>
  );
};

export default Destinations;
