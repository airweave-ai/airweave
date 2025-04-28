import { useState, useEffect } from "react";
import { DashboardStats } from "@/components/dashboard/DashboardStats";
import { ConnectedSourcesGrid } from "@/components/dashboard/ConnectedSourcesGrid";
import { ConnectedDestinationsGrid } from "@/components/dashboard/ConnectedDestinationsGrid";
import { ChatCTA } from "@/components/dashboard/ChatCTA";
import { DocsCard } from "@/components/dashboard/DocsCard";
import { Button } from "@/components/ui/button";
import { MessageSquare, Plus, Table } from "lucide-react";
import { SyncGridView, ResourceCards, SyncTableComponent } from "@/components/dashboard";
import { CreateSyncCTA } from "@/components/dashboard/CreateSyncCTA";
import { apiClient } from "@/lib/api";
import { useTheme } from "@/lib/theme-provider";
import { useNavigate } from "react-router-dom";

interface Sync {
  id: string;
  name: string;
  status?: string;
  source_connection?: {
    short_name: string;
    name: string;
  };
  created_at: string;
  modified_at: string;
}

const Dashboard = () => {
  const [syncs, setSyncs] = useState<Sync[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const { resolvedTheme } = useTheme();
  const navigate = useNavigate();

  // Determine which logo to use based on theme
  const logoSrc = resolvedTheme === "dark" ? "/logo-and-lettermark-light.svg" : "/logo-and-lettermark.svg";

  useEffect(() => {
    const fetchSyncs = async () => {
      setIsLoading(true);
      try {
        const response = await apiClient.get("/sync/?with_source_connection=true");
        if (response.ok) {
          const data = await response.json();
          setSyncs(data);
        } else {
          // If we get an error, assume no syncs
          console.error("Failed to fetch syncs:", await response.text());
          setSyncs([]);
        }
      } catch (error) {
        console.error("Failed to fetch syncs", error);
        setSyncs([]);
      } finally {
        setIsLoading(false);
      }
    };

    fetchSyncs();
  }, []);

  const handleCreateSync = () => {
    navigate("/sync/create");
  };

  if (isLoading) {
    return (
      <div className="container mx-auto pb-8">
        <div className="flex justify-between items-center">
          <div>
            <h2 className="text-3xl font-bold tracking-tight">Dashboard</h2>
            <p className="text-muted-foreground">
              Overview of your knowledge
            </p>
          </div>
        </div>
        <div className="h-64 flex items-center justify-center">
          <div className="animate-pulse">Loading...</div>
        </div>
      </div>
    );
  }

  if (syncs.length === 0) {
    // Empty state with centered CTA
    return (
      <div className="container mx-auto pb-8">
        <div className="h-[calc(100vh-200px)] flex flex-col items-center justify-center">
          <div className="text-center mb-8">
            <div className="flex flex-row items-center justify-center gap-3 mb-2">
              <h2 className="text-3xl font-bold tracking-tight">Welcome to</h2>
              <img
                src={logoSrc}
                alt="Airweave"
                className="h-10"
              />
            </div>
            <p className="text-muted-foreground">
              Let's get you started.
            </p>
          </div>
          <div className="w-full max-w-3xl">
            <CreateSyncCTA />
          </div>
        </div>
      </div>
    );
  }

  // Regular dashboard content when syncs exist
  return (
    <div className="container mx-auto pb-8">
      <div className="space-y-8">
        <div className="flex justify-between items-center">
          <div>
            <h2 className="text-3xl font-bold tracking-tight">Your Syncs</h2>
            <p className="text-muted-foreground">
              Overview of your knowledge
            </p>
          </div>
          <div className="flex gap-2">
            <Button
              onClick={handleCreateSync}
              size="sm"
              className="rounded-lg px-3 py-0.5 bg-blue-500 hover:bg-blue-600 text-white font-medium transition-all"
            >
              <Plus className="mr-1.5 h-3.5 w-3.5" />
              Create Sync
            </Button>
          </div>
        </div>

        <SyncGridView syncs={syncs} />

        <div>
          <SyncTableComponent showBorder maxHeight="500px" />
        </div>


        <div>
          <h3 className="text-2xl font-semibold mb-4">Resources</h3>
          <ResourceCards />
        </div>
      </div>
    </div>
  );
}

export default Dashboard;
