import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { SyncCard } from "@/components/sync";
import { apiClient } from "@/lib/api";
import { Skeleton } from "@/components/ui/skeleton";

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

interface SyncGridViewProps {
  syncs?: Sync[];
}

export function SyncGridView({ syncs: propSyncs }: SyncGridViewProps) {
  const [syncs, setSyncs] = useState<Sync[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    // If syncs are provided as props, use them
    if (propSyncs) {
      setSyncs(propSyncs);
      setIsLoading(false);
      return;
    }

    // Otherwise fetch them from the API
    const fetchSyncs = async () => {
      try {
        setIsLoading(true);
        // Update the API call to include source_connection information
        const response = await apiClient.get("/sync/?with_source_connection=true");
        if (response.ok) {
          const data = await response.json();
          console.log("Syncs with source connections:", data);
          setSyncs(data);
        } else {
          console.error("Failed to fetch syncs:", await response.text());
          setSyncs([]);
        }
      } catch (error) {
        console.error("Error fetching syncs:", error);
        setSyncs([]);
      } finally {
        setIsLoading(false);
      }
    };

    fetchSyncs();
  }, [propSyncs]);

  const handleViewDetails = (syncId: string) => {
    navigate(`/sync/${syncId}`);
  };

  const handleChat = (syncId: string) => {
    navigate(`/chat?syncId=${syncId}`);
  };

  if (isLoading) {
    return (
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {[...Array(6)].map((_, index) => (
          <div key={index} className="h-[380px]">
            <Skeleton className="w-full h-full rounded-lg" />
          </div>
        ))}
      </div>
    );
  }

  if (syncs.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center p-10 rounded-lg bg-muted/30">
        <h3 className="text-lg font-medium mb-2">No syncs found</h3>
        <p className="text-sm text-muted-foreground mb-4">
          Create your first sync to start integrating your data.
        </p>
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
      {syncs.map((sync) => (
        <SyncCard
          key={sync.id}
          syncId={sync.id}
          syncName={sync.name}
          sourceConnectionShortName={sync.source_connection?.short_name || "default-icon"}
          status={sync.status || "inactive"}
          onViewDetails={() => handleViewDetails(sync.id)}
          onChat={() => handleChat(sync.id)}
        />
      ))}
    </div>
  );
}
