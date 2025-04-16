import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Settings2 } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { getDestinationIconUrl } from "@/lib/utils/icons";

const mockDestinations = [
  { id: "1", name: "Production Weaviate", type: "weaviate", status: "active", lastSync: "2h ago" },
  { id: "2", name: "Development Weaviate", type: "weaviate", status: "active", lastSync: "1h ago" },
];

export function ConnectedDestinationsGrid() {
  const navigate = useNavigate();

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between">
        <CardTitle>Connected Destinations</CardTitle>
        <Button
          variant="outline"
          size="sm"
          onClick={() => navigate("/destinations")}
        >
          <Settings2 className="mr-2 h-4 w-4" />
          Configure Destinations
        </Button>
      </CardHeader>
      <CardContent>
        <div className="grid gap-4 md:grid-cols-2">
          {mockDestinations.map((destination) => (
            <div
              key={destination.id}
              className="flex items-center space-x-4 rounded-lg border p-4"
            >
              <img
                src={getDestinationIconUrl(destination.type)}
                alt={destination.name}
                className="h-8 w-8"
              />
              <div className="flex-1 space-y-1">
                <p className="text-sm font-medium leading-none">{destination.name}</p>
                <p className="text-sm text-muted-foreground">
                  Last sync: {destination.lastSync}
                </p>
              </div>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}
