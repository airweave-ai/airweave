import { memo } from "react";
import { Handle, NodeProps, Position } from "reactflow";
import { Box } from "lucide-react";
import { cn } from "@/lib/utils";

interface EntityNodeData {
  name: string;
  entityDefinitionId: string;
  config?: Record<string, any>;
}

interface EntityNodeProps {
  data: EntityNodeData;
}

export const EntityNode = memo(({ data, selected, ...props }: NodeProps) => {
  return (
    <div className="w-20 h-20 flex items-center justify-center">
      <div className="w-10 h-10">
        <div
          className={cn(
            "w-full h-full flex items-center justify-center rounded-2xl bg-muted/40 backdrop-blur-sm",
            "transition-colors duration-200",
            selected ? "bg-muted/90" : "bg-muted/80"
          )}
        >
          <Handle
            type="target"
            position={Position.Left}
            className="opacity-0 w-0 h-0"
            style={{ left: -6 }}
          />
          <Box className="w-6 h-6 text-muted-foreground" />
          <Handle
            type="source"
            position={Position.Right}
            className="opacity-0 w-0 h-0"
            style={{ right: -6 }}
          />
        </div>
        <div className="absolute -bottom-3 left-1/2 -translate-x-1/2 whitespace-nowrap">
          <span className="text-xs font-light text-foreground text-center">{data.name}</span>
        </div>
      </div>
    </div>
  );
});

EntityNode.displayName = "EntityNode";
