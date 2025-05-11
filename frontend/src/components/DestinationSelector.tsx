import { useEffect, useState } from "react";
import {
  Card,
  CardHeader,
  CardTitle,
  CardDescription,
  CardContent,
  CardFooter,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Loader2, Check, CirclePlus } from "lucide-react";
import { useNavigate } from "react-router-dom";

import { useToast } from "@/components/ui/use-toast";
import { getDestinationIconUrl } from "@/lib/utils/icons";
import { apiClient } from "@/lib/api";
import { cn } from "@/lib/utils";

interface Destination {
  id: string;
  name: string;
  description: string | null;
  short_name: string;
  auth_type: string | null;
}

interface ConfigField {
  name: string;
  title: string;
  description: string | null;
  type: string;
}

interface DestinationWithConfig extends Destination {
  auth_fields?: {
    fields: ConfigField[];
  };
}

interface Connection {
  id: string;
  name: string;
  status: "active" | "inactive" | "error";
  modified_at: string;
  short_name: string;
}

interface ConnectionSelection {
  connectionId: string;
  isNative?: boolean;
}

interface DestinationSelectorProps {
  onComplete: (details: ConnectionSelection, metadata: { name: string; shortName: string }) => void;
}

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
    fields: ConfigField[];
  };
}

/**
 * Example endpoint for listing existing "destination" connections:
 *   GET /connections/list/destination
 * Returns an array of objects matching the Connection interface above.
 */

export const DestinationSelector = ({ onComplete }: DestinationSelectorProps) => {
  const [destinations, setDestinations] = useState<DestinationDetails[]>([]);
  const [connections, setConnections] = useState<Connection[]>([]);
  // For storing config form states
  const [selectedDestination, setSelectedDestination] = useState<DestinationDetails | null>(null);
  const [showConfig, setShowConfig] = useState(false);
  const [configValues, setConfigValues] = useState<Record<string, string>>({});
  const [authenticationFields, setAuthenticationFields] = useState<ConfigField[]>([]);
  const [isConnecting, setIsConnecting] = useState(false);
  const { toast } = useToast();
  const navigate = useNavigate();

  // Simplified data fetching - just like in Destinations.tsx
  useEffect(() => {
    const fetchData = async () => {
      try {
        // 1. Get connections
        const connResp = await apiClient.get("/connections/list/destination");
        if (connResp.ok) {
          const connData = await connResp.json();
          setConnections(connData);
        }

        // 2. Get destinations
        const destResp = await apiClient.get("/destinations/list");
        if (destResp.ok) {
          const destData = await destResp.json();
          setDestinations(destData);
        }
      } catch (err) {
        console.error("Error fetching data:", err);
        toast({
          variant: "destructive",
          title: "Failed to load vector databases",
          description: "Please try again later",
        });
      }
    };

    fetchData();
  }, []);

  /**
   * When user clicks "Add new connection" or chooses to configure a new one,
   * we fetch config fields for that destination's short_name.
   */
  const handleAddNewConnection = async (dest: DestinationDetails) => {
    try {
      const response = await apiClient.get(`/destinations/detail/${dest.short_name}`);
      if (!response.ok) throw new Error("Failed to fetch destination details");
      const data: DestinationWithConfig = await response.json();

      setSelectedDestination(dest);
      setAuthenticationFields(data.auth_fields?.fields || []);
      setConfigValues({});
      setShowConfig(true);
    } catch (err) {
      console.error("Error fetching destination details:", err);
      toast({
        variant: "destructive",
        title: "Failed to load configuration",
        description: "Please try again later",
      });
    }
  };

  /**
   * Submit the final selection - keeping the same API signature as before
   */
  const handleSubmitSelections = () => {
    // Only use Native Weaviate
    onComplete(
      {
        connectionId: "native",
        isNative: true
      },
      {
        name: "Native Qdrant",
        shortName: "qdrant_native"
      }
    );
  };

  /**
   * Actually connect a new instance for the currently selected destination.
   */
  const handleConnect = async () => {
    if (!selectedDestination) return;

    const missingFields = authenticationFields.filter((field) => !configValues[field.name]);
    if (missingFields.length > 0) {
      toast({
        variant: "destructive",
        title: "Missing required fields",
        description: `Please fill in: ${missingFields.map((f) => f.title).join(", ")}`,
      });
      return;
    }

    setIsConnecting(true);
    try {
      const response = await apiClient.post(
        `/connections/connect/destination/${selectedDestination.short_name}`,
        configValues
      );

      if (!response.ok) throw new Error("Failed to connect");

      const data = await response.json();

      setShowConfig(false);
      toast({
        title: "Connection added",
        description: "Connection successfully configured",
      });
    } catch (err) {
      toast({
        variant: "destructive",
        title: "Connection failed",
        description: "Please check your credentials and try again",
      });
    } finally {
      setIsConnecting(false);
    }
  };

  /**
   * Render the native instances separately
   */
  const renderNativeInstances = () => {
    return (
      <div className="grid gap-4 sm:grid-cols-2 max-w-2xl">
        {/* Qdrant Native - Actually selected */}
        <Card
          className="flex flex-col justify-between border-primary border-2 bg-gradient-to-br from-background to-muted/50"
        >
          <CardHeader>
            <div className="flex items-center justify-between">
              <div className="flex items-center space-x-3">
                <img
                  src={getDestinationIconUrl("qdrant")}
                  alt="Qdrant icon"
                  className="w-8 h-8"
                />
                <div>
                  <CardTitle>Native Qdrant</CardTitle>
                  <CardDescription>Built-in vector database</CardDescription>
                </div>
              </div>
              <Check className="h-5 w-5 text-primary" />
            </div>
          </CardHeader>
          <CardContent className="flex-grow">
            <p className="text-sm text-muted-foreground">
              Use the built-in Qdrant instance for optimal performance and seamless integration.
            </p>
          </CardContent>
          <CardFooter>
            <Button
              className="w-full"
              variant="default"
              disabled
            >
              Selected
            </Button>
          </CardFooter>
        </Card>
      </div>
    );
  };

  /**
   * Group connections by destination type and render them as separate cards
   */
  const renderDestinationGroup = (dest: DestinationDetails) => {
    // Skip native instances as they're rendered separately
    if (dest.short_name === "qdrant_native" || dest.short_name === "neo4j_native") return null;

    const destConnections = connections
      .filter((c) => c.short_name === dest.short_name)
      .filter((c) => c.status === "active")
      .sort((a, b) => new Date(b.modified_at).getTime() - new Date(a.modified_at).getTime());

    return (
      <div key={dest.short_name} className="space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <img
              src={getDestinationIconUrl(dest.short_name)}
              alt={`${dest.name} icon`}
              className="w-6 h-6"
            />
            <h3 className="font-semibold text-lg">{dest.name}</h3>
          </div>
        </div>

        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {/* Existing connections */}
          {destConnections.map((conn) => (
            <Card
              key={conn.id}
              className="flex flex-col justify-between transition-colors bg-muted/5 hover:border-primary/50"
            >
              <CardHeader>
                <div className="flex items-center justify-between">
                  <CardTitle>{conn.name}</CardTitle>
                  {conn.status === "active" && (
                    <Check className="h-4 w-4 text-primary" />
                  )}
                </div>
                <CardDescription>
                  {conn.status === "active" ? "Connected" : "Connection Error"}
                </CardDescription>
              </CardHeader>
              <CardContent className="flex-grow">
                <p className="text-sm text-muted-foreground">
                  Last modified: {new Date(conn.modified_at).toLocaleDateString()}
                </p>
              </CardContent>
              <CardFooter>
                <Button
                  className="w-full"
                  variant="secondary"
                  onClick={() => navigate("/destinations")}
                >
                  View Connection
                </Button>
              </CardFooter>
            </Card>
          ))}

          {/* Modified "Add New Instance" card */}
          <Card className="flex flex-col justify-between border-dashed hover:border-primary/50 transition-colors bg-gradient-to-br from-background to-muted/20">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <CirclePlus className="h-7 w-7" />
                Add New Connection
              </CardTitle>
              <CardDescription>Set up a new {dest.name} instance</CardDescription>
            </CardHeader>
            <CardContent className="flex-grow">
              <p className="text-sm text-muted-foreground">
                Configure a new connection in the destinations page to add it to your vector database collection.
              </p>
            </CardContent>
            <CardFooter>
              <Button
                variant="outline"
                className="w-full"
                onClick={() => navigate("/destinations")}
              >
                Go to Destinations
              </Button>
            </CardFooter>
          </Card>
        </div>
      </div>
    );
  };

  // If we are showing config form, show that in a single card
  if (showConfig && selectedDestination) {
    return (
      <div className="max-w-md mx-auto">
        <Card>
          <CardHeader>
            <div className="flex items-center space-x-4">
              <img
                src={getDestinationIconUrl(selectedDestination.short_name)}
                alt={`${selectedDestination.name} icon`}
                className="w-8 h-8"
              />
              <div>
                <CardTitle>{selectedDestination.name}</CardTitle>
                <CardDescription>Configure your connection</CardDescription>
              </div>
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            {authenticationFields.map((field) => (
              <div key={field.name} className="space-y-2">
                <label className="text-sm font-medium">
                  {field.title}
                  {field.description && (
                    <span className="text-xs text-muted-foreground ml-2">
                      ({field.description})
                    </span>
                  )}
                </label>
                <Input
                  type={field.type === "string" ? "text" : field.type}
                  value={configValues[field.name] || ""}
                  onChange={(e) =>
                    setConfigValues((prev) => ({
                      ...prev,
                      [field.name]: e.target.value,
                    }))
                  }
                  placeholder={`Enter ${field.title.toLowerCase()}`}
                />
              </div>
            ))}
          </CardContent>
          <CardFooter className="flex justify-between">
            <Button
              variant="outline"
              onClick={() => {
                setShowConfig(false);
                setSelectedDestination(null);
              }}
            >
              Back
            </Button>
            <Button onClick={handleConnect} disabled={isConnecting}>
              {isConnecting ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Connecting
                </>
              ) : (
                "Connect"
              )}
            </Button>
          </CardFooter>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-8">
      {/* Native instances at top */}
      <div>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-xl font-bold">Native Databases</h2>
          <Button size="lg" onClick={handleSubmitSelections}>
            Continue
          </Button>
        </div>
        {renderNativeInstances()}
      </div>

      {/* Other destinations */}
      <div className="space-y-8">
        <h2 className="text-xl font-bold">External Connections</h2>
        {destinations
          .filter(dest => dest.short_name !== "weaviate_native" && dest.short_name !== "neo4j_native")
          .sort((a, b) => a.name.localeCompare(b.name))
          .map(renderDestinationGroup)}
      </div>
    </div>
  );
};
