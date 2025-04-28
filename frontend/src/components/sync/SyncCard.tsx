import { useState, useEffect } from "react";
import { Card, CardContent, CardFooter } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Database } from "lucide-react";
import { CodeBlock } from "@/components/ui/code-block";
import { apiClient } from "@/lib/api";
import { getAppIconUrl } from "@/lib/utils/icons";
import { useTheme } from "@/lib/theme-provider";
import { useNavigate } from "react-router-dom";
import { cn } from "@/lib/utils";

interface SyncCardProps {
  syncId: string;
  syncName: string;
  sourceConnectionShortName: string;
  status: string;
  onViewDetails?: () => void;
}

export function SyncCard({
  syncId,
  syncName,
  sourceConnectionShortName,
  status,
  onViewDetails,
}: SyncCardProps) {
  const [entityCount, setEntityCount] = useState<number | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const { resolvedTheme } = useTheme();
  const navigate = useNavigate();

  useEffect(() => {
    const fetchEntityCount = async () => {
      try {
        setIsLoading(true);
        const response = await apiClient.get(`/entities/count-by-sync/${syncId}`);
        if (response.ok) {
          const data = await response.json();
          setEntityCount(data.count);
        } else {
          console.error("Failed to fetch entity count:", await response.text());
        }
      } catch (error) {
        console.error("Error fetching entity count:", error);
      } finally {
        setIsLoading(false);
      }
    };

    fetchEntityCount();
  }, [syncId]);

  const getStatusBadge = (status: string) => {
    const statusUpper = status.toUpperCase();

    if (statusUpper === "ACTIVE") {
      return (
        <div className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-xs font-normal bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400">
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 dark:bg-emerald-400"></span>
          {statusUpper}
        </div>
      );
    }

    let variant: "default" | "secondary" | "destructive" = "secondary";
    if (statusUpper === "ERROR") variant = "destructive";

    return (
      <Badge
        variant={variant}
        className="text-xs px-1.5 py-0 h-5 font-normal"
      >
        {statusUpper}
      </Badge>
    );
  };

  const handleViewDetails = () => {
    if (onViewDetails) {
      onViewDetails();
    } else {
      navigate(`/syncs/${syncId}`);
    }
  };

  // Basic search query example for the code block
  const searchCode = `curl -G ${window.location.origin}/search/ \\
 -d sync_id="${syncId}" \\
 -d query="Your search query here"`;

  return (
    <Card className="w-full min-h-[240px] flex flex-col overflow-hidden border-border/70 relative rounded-xl dark:bg-slate-900/50 hover:bg-white dark:hover:bg-slate-900/70 transition-colors">
      <div className="p-4 pb-2 flex justify-between">
        <div>
          <div className="flex items-center gap-3">
            <h3 className="text-lg font-semibold">{syncName}</h3>
            {getStatusBadge(status)}
          </div>
          <div className="mt-1">
            <code className="text-xs text-muted-foreground font-mono bg-muted px-1.5 py-0.5 rounded-sm">
              {syncId}
            </code>
          </div>
        </div>
        <div className="w-8 h-8 rounded-full flex items-center justify-center">
          <img
            src={getAppIconUrl(sourceConnectionShortName, resolvedTheme)}
            alt={sourceConnectionShortName}
            className="w-8 h-8"
          />
        </div>
      </div>

      <CardContent className="flex-1 p-4 pt-2 space-y-3">
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <Database className="h-4 w-4" />
          <span>
            {isLoading
              ? "Loading..."
              : entityCount !== null
                ? `${entityCount.toLocaleString()} entities`
                : "No entities"}
          </span>
        </div>

        <CodeBlock
          code={searchCode}
          language="bash"
          badgeText="REST"
          badgeColor="bg-emerald-600 hover:bg-emerald-600"
          title="Search API"
        />
      </CardContent>

      <CardFooter className="p-4 pt-2 flex justify-center border-t border-border/10">
        <Button
          onClick={handleViewDetails}
          variant="outline"
          size="sm"
          className="px-6 text-foreground hover:bg-accent hover:text-accent-foreground transition-colors rounded-md text-xs"
        >
          View details
        </Button>
      </CardFooter>
    </Card>
  );
}
