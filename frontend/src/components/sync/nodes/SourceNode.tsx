import { memo, useEffect, useState } from "react";
import { Handle, NodeProps, Position } from "reactflow";
import { getAppIconUrl } from "@/lib/utils/icons";
import { apiClient } from "@/lib/api";
import { Connection } from "@/components/sync/dag";
import { cn } from "@/lib/utils";
import { toast } from "@/components/ui/use-toast";
import { useTheme } from "@/lib/theme-provider";

export const SourceNode = memo(({ data, selected, ...props }: NodeProps) => {
  const [connection, setConnection] = useState<Connection | null>(null);
  const { resolvedTheme } = useTheme();

  useEffect(() => {
    const fetchConnection = async () => {
      if (!data.connection_id) return;

      try {
        const resp = await apiClient.get(`/connections/detail/${data.connection_id}`);
        if (!resp.ok) throw new Error("Failed to fetch connection details");
        const connData = await resp.json();
        setConnection(connData);
      } catch (error) {
        console.error("Error fetching connection:", error);
        toast({
          variant: "destructive",
          title: "Failed to load connection details",
          description: "Please try refreshing the page",
        });
      }
    };

    fetchConnection();
  }, [data.connection_id]);

  return (
    <div className="w-20 h-20">
      <div
        className={cn(
          "w-full h-full flex items-center justify-center bg-background/80 backdrop-blur-sm",
          "border-2 transition-colors duration-200 cursor-pointer",
          "border-muted-foreground/50 hover:border-primary rounded-lg rounded-l-2xl",
          selected ? "border-primary shadow-sm shadow-primary/20" : ""
        )}
      >
        <Handle
          type="source"
          position={Position.Right}
          className="w-3 h-3 -mr-[3px] border border-background bg-muted-foreground"
        />
        <div className="w-16 h-16 flex items-center justify-center">
          <img
            src={getAppIconUrl(connection?.short_name || data.shortName, resolvedTheme)}
            alt={connection?.name || data.name}
            className="w-12 h-12 object-contain"
          />
        </div>
      </div>
      <div className="absolute -bottom-7 left-1/2 -translate-x-1/2 whitespace-nowrap">
        <span className="text-sm font-semibold text-foreground text-center">
          {connection?.name || data.name}
        </span>
      </div>
    </div>
  );
});

SourceNode.displayName = "SourceNode";
